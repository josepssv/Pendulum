"""
Sample-Based Instrument Engine for Pendulum Polyphony.
Loads acoustic instrument samples from assets/samples/<instrument_name>/,
performs low-latency polyphonic playback with controllable decay/damping,
and renders high-fidelity studio stereo WAV audio for export.
Supports user-added custom instruments by simply dropping folders of WAV/MP3 files.
"""

import os
import re
import time
import threading
import numpy as np
import soundfile as sf
import pygame
from typing import Dict, List, Optional, Tuple
try:
    from scipy.signal import correlate
except ImportError:
    correlate = None

SAMPLE_RATE = 44100
DEFAULT_SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "samples")

NOTE_REGEX = re.compile(r"^([A-Ga-g])([#sSbB]?)(-?\d+)$")
PREFIXED_NOTE_REGEX = re.compile(r"^(.+?)[_\-\s]+([A-Ga-g][#sSbB]?[0-8])$")

def parse_note_name_to_midi(name_str: str) -> Optional[int]:
    """
    Parses strings like 'C4', 'A#3', 'Eb5', 'Db2', 'Fs4', '60' into MIDI note numbers.
    """
    cleaned = os.path.splitext(os.path.basename(name_str))[0].strip()
    if cleaned.isdigit():
        midi_val = int(cleaned)
        if 0 <= midi_val <= 127:
            return midi_val

    m = NOTE_REGEX.match(cleaned)
    if not m:
        return None

    letter = m.group(1).upper()
    accidental = m.group(2).lower()
    octave = int(m.group(3))

    semitones = {
        'C': 0, 'D': 2, 'E': 4, 'F': 5,
        'G': 7, 'A': 9, 'B': 11
    }
    if letter not in semitones:
        return None

    base = semitones[letter]
    if accidental in ('#', 's'):
        base += 1
    elif accidental == 'b':
        base -= 1

    # Standard MIDI: C4 is 60 -> (4 + 1) * 12 + 0 = 60
    midi_note = (octave + 1) * 12 + base
    return midi_note if 0 <= midi_note <= 127 else None


def parse_prefixed_note(name_str: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Parses either pure note names ('C4.wav' -> (None, 60)) or
    instrument-prefixed note names ('flauta_C4.wav' -> ('flauta', 60)).
    """
    pure_midi = parse_note_name_to_midi(name_str)
    if pure_midi is not None:
        return None, pure_midi

    cleaned = os.path.splitext(os.path.basename(name_str))[0].strip()
    m = PREFIXED_NOTE_REGEX.match(cleaned)
    if not m:
        return None, None

    prefix = m.group(1).strip().lower()
    note_part = m.group(2)
    midi_note = parse_note_name_to_midi(note_part)
    if midi_note is None or not prefix:
        return None, None
    return prefix, midi_note


class InstrumentBank:
    """
    Holds loaded audio waveforms for a single instrument.
    Handles pitch-shifting, sustained crossfade looping, and drum mappings.
    """
    def __init__(self, name: str, folder_path: str):
        self.name = name
        self.folder_path = folder_path
        lower_name = name.lower()
        self.is_mix = ("mix" in lower_name)
        self.is_drums = ("drum" in lower_name or "perc" in lower_name) and not self.is_mix
        self.is_sustained = any(
            k in lower_name for k in (
                "organ", "organo", "harmonium", "hammond",
                "drone", "pad", "ambient", "paisaje",
                "choir", "cathedral", "catedral"
            )
        )
        self._loaded = False
        # Dict[int, np.ndarray]: midi_pitch -> 1D float32 audio (mono or left channel)
        self.pitched_samples: Dict[int, np.ndarray] = {}
        # Dict[str, Dict[int, np.ndarray]]: 'melodic:<prefix>' -> {midi_pitch -> audio}
        self.pitched_groups: Dict[str, Dict[int, np.ndarray]] = {}
        # Dict[str, np.ndarray]: drum_type -> 1D float32 audio
        self.drum_samples: Dict[str, np.ndarray] = {}
        self.default_sample: Optional[np.ndarray] = None
        self.custom_pendulum_map: Dict[int, str] = {}
        self._pitch_cache: Dict[Tuple[str, int], np.ndarray] = {}
        self._lock = threading.RLock()
        self._detect_bank_metadata()

    def _detect_bank_metadata(self):
        """Lightweight filename-only scan so startup does not decode every bank up front."""
        if not os.path.exists(self.folder_path):
            return
        valid_exts = ('.wav', '.mp3', '.ogg', '.flac')
        files = [f for f in os.listdir(self.folder_path) if os.path.splitext(f)[1].lower() in valid_exts]
        drum_keywords = ('openhat', 'hihat', 'kick', 'boom', 'snare', 'clap', 'ride', 'crash', 'rim', 'tom', 'tink', 'hat')
        if not self.is_mix:
            if any(k in self.name.lower() for k in ("drum", "perc", "bateria", "beat", "kit", "sub-tom")) or \
               any(any(k in os.path.splitext(f)[0].lower() for k in drum_keywords) for f in files):
                self.is_drums = True
            else:
                for f in files:
                    prefix, midi_p = parse_prefixed_note(f)
                    if midi_p is not None and prefix:
                        self.is_mix = True
                        break

    def ensure_loaded(self):
        """Lazy-loads waveforms on first use."""
        if not self._loaded:
            with self._lock:
                if not self._loaded:
                    self.load_samples()
                    self._loaded = True

    def load_samples(self):
        if not os.path.exists(self.folder_path):
            return
        self._pitch_cache.clear()

        valid_exts = ('.wav', '.mp3', '.ogg', '.flac')
        files = [f for f in os.listdir(self.folder_path) if os.path.splitext(f)[1].lower() in valid_exts]

        drum_keywords = ('openhat', 'hihat', 'kick', 'boom', 'snare', 'clap', 'ride', 'crash', 'rim', 'tom', 'tink', 'hat')
        if not self.is_mix:
            if any(k in self.name.lower() for k in ("drum", "perc", "bateria", "beat", "kit", "sub-tom")) or \
               any(any(k in os.path.splitext(f)[0].lower() for k in drum_keywords) for f in files):
                self.is_drums = True

        for fname in sorted(files):
            fpath = os.path.join(self.folder_path, fname)
            try:
                data, sr = sf.read(fpath, dtype='float32')
                # Convert stereo to mono float32 for clean panning & pitch-shifting
                if data.ndim > 1:
                    data = np.mean(data, axis=1)

                # Resample to SAMPLE_RATE if needed
                if sr != SAMPLE_RATE and len(data) > 0:
                    new_len = int(round(len(data) * SAMPLE_RATE / sr))
                    t_orig = np.linspace(0, 1, len(data), endpoint=False)
                    t_new = np.linspace(0, 1, new_len, endpoint=False)
                    data = np.interp(t_new, t_orig, data).astype(np.float32)

                # Normalize peak
                peak = np.max(np.abs(data))
                if peak > 1e-4:
                    data = (data / peak) * 0.95

                stem = os.path.splitext(fname)[0].lower()

                if self.is_mix:
                    prefix, midi_p = parse_prefixed_note(fname)
                    if midi_p is not None:
                        if prefix:
                            self.pitched_groups.setdefault(f"melodic:{prefix}", {})[midi_p] = data
                        else:
                            self.pitched_samples[midi_p] = data
                    else:
                        self.drum_samples[stem] = data
                        for d_key in drum_keywords:
                            if d_key in stem and d_key not in self.drum_samples:
                                self.drum_samples[d_key] = data
                                break
                elif self.is_drums:
                    # Register by full stem name to preserve multiple varieties
                    self.drum_samples[stem] = data
                    for d_key in ('openhat', 'hihat', 'kick', 'boom', 'snare', 'clap', 'ride', 'crash', 'rim', 'tom', 'tink', 'hat'):
                        if d_key in stem and d_key not in self.drum_samples:
                            self.drum_samples[d_key] = data
                            break
                else:
                    prefix, midi_p = parse_prefixed_note(fname)
                    if midi_p is not None:
                        if prefix:
                            self.pitched_groups.setdefault(f"melodic:{prefix}", {})[midi_p] = data
                        else:
                            self.pitched_samples[midi_p] = data
                    else:
                        # Fallback default sample if not note-named
                        if self.default_sample is None:
                            self.default_sample = data

                if self.default_sample is None and len(data) > 0:
                    self.default_sample = data

            except Exception as e:
                print(f"Error loading sample {fpath}: {e}")

        if self.pitched_groups:
            self.is_mix = True

        # If it was marked as pitched but only has drum/unnamed samples, keep default
        if not self.pitched_samples and not self.pitched_groups and self.default_sample is not None and not self.is_drums:
            self.pitched_samples[60] = self.default_sample

        self._loaded = True

    def _extend_sustained_audio(self, audio: np.ndarray, desired_len: int) -> np.ndarray:
        """
        Extends a sustained organ/pad sample cleanly past its natural length using
        FFT phase-aligned raised-cosine crossfade looping over its steady-state middle segment.
        """
        if not self.is_sustained or len(audio) >= desired_len or len(audio) < int(0.9 * SAMPLE_RATE):
            return audio

        start_idx = int(len(audio) * 0.20)
        end_idx = int(len(audio) * 0.68)
        if end_idx - start_idx <= 128:
            return audio

        rms = float(np.sqrt(np.mean(audio[start_idx:end_idx] * audio[start_idx:end_idx])))
        if rms <= 0.015:
            return audio

        xf = min(int(0.45 * SAMPLE_RATE), max(64, (end_idx - start_idx) // 3))

        # Phase-align loop start to the outgoing crossfade window via 4x coarse FFT + +-6 fine refinement
        best_start = start_idx
        match_len = min(4096, xf)
        max_shift = min(
            2205,
            max(0, start_idx - int(len(audio) * 0.10)),
            max(0, end_idx - xf - match_len - 1 - start_idx)
        )
        if correlate is not None and max_shift > 16 and match_len > 32:
            search_lo = start_idx - max_shift
            search_hi = start_idx + max_shift + match_len
            search_region = audio[search_lo:search_hi]
            tail_ref = audio[end_idx - xf : end_idx - xf + match_len]
            sr_dec = search_region[::4]
            tr_dec = tail_ref[::4]
            if len(sr_dec) >= len(tr_dec) and len(tr_dec) > 8:
                corr = correlate(sr_dec, tr_dec, mode='valid', method='fft')
                if len(corr) > 0:
                    coarse_start = search_lo + int(np.argmax(corr)) * 4
                    match_len_ref = min(1024, xf)
                    ref_fine = audio[end_idx - xf : end_idx - xf + match_len_ref]
                    fine_lo = max(search_lo, coarse_start - 6)
                    fine_hi = min(start_idx + max_shift, coarse_start + 6)
                    best_score = -1e30
                    for cand in range(fine_lo, fine_hi + 1):
                        seg = audio[cand : cand + match_len_ref]
                        if len(seg) == match_len_ref:
                            score = float(np.dot(seg, ref_fine))
                            if score > best_score:
                                best_score = score
                                best_start = cand

        loop_body = audio[best_start:end_idx]
        xf = min(xf, len(loop_body) // 3)
        if xf <= 16:
            return audio

        t_xf = np.linspace(0.0, 1.0, xf, dtype=np.float32)
        fade_in_w = 0.5 * (1.0 - np.cos(np.pi * t_xf))
        fade_out_w = 1.0 - fade_in_w

        out = np.empty(desired_len, dtype=np.float32)
        head_len = min(end_idx, desired_len)
        out[:head_len] = audio[:head_len]
        pos = end_idx

        tail_segment = loop_body[xf:]
        tail_len = len(tail_segment)
        while pos < desired_len:
            out[pos - xf : pos] = (
                out[pos - xf : pos] * fade_out_w
                + loop_body[:xf] * fade_in_w
            )
            copy_len = min(tail_len, desired_len - pos)
            out[pos : pos + copy_len] = tail_segment[:copy_len]
            pos += copy_len

        return out

    def get_voice_audio(self, pitch: int, duration: float, damping: float = 1.0, pendulum_index: Optional[int] = None) -> np.ndarray:
        """
        Retrieves or interpolates audio for a given pitch and note duration.
        damping: 1.0 = natural decay, < 1.0 = drier / staccato, > 1.0 = sustained.
        pendulum_index: if drums, routes each pendulum to its own dedicated percussion instrument.
        """
        self.ensure_loaded()
        raw_audio = None

        if self.is_mix:
            raw_audio = self._get_mix_audio(pitch, pendulum_index=pendulum_index)
        elif self.is_drums:
            raw_audio = self._get_drum_audio(pitch, pendulum_index=pendulum_index)
        else:
            raw_audio = self._get_pitched_audio(pitch)

        if raw_audio is None or len(raw_audio) == 0:
            # Fallback sine wave if no sample exists
            n_samples = int(duration * SAMPLE_RATE)
            t = np.linspace(0, duration, n_samples, endpoint=False)
            freq = 440.0 * (2.0 ** ((pitch - 69.0) / 12.0))
            return (np.sin(2 * np.pi * freq * t) * np.exp(-t * 6.0)).astype(np.float32)

        if self.is_sustained:
            effective_dur = max(0.08, min(14.0, float(duration) * float(damping)))
            if effective_dur <= 0.35:
                release_sec = min(0.18, effective_dur * 0.45)
            else:
                release_sec = min(1.8, max(0.28, effective_dur * 0.35 * min(1.5, float(damping))))
            desired_len = min(int(16.0 * SAMPLE_RATE), int((effective_dur + release_sec) * SAMPLE_RATE))

            if len(raw_audio) < desired_len:
                raw_audio = self._extend_sustained_audio(raw_audio, desired_len)

            out = raw_audio[:min(len(raw_audio), desired_len)].copy()
            attack_samples = min(int(0.008 * SAMPLE_RATE), len(out) // 4)
            if attack_samples > 0:
                out[:attack_samples] *= np.linspace(0.0, 1.0, attack_samples, dtype=np.float32)

            release_samples = min(int(release_sec * SAMPLE_RATE), len(out) // 2)
            if release_samples > 0:
                rel_t = np.linspace(0.0, 1.0, release_samples, dtype=np.float32)
                rel_env = (0.5 * (1.0 + np.cos(np.pi * rel_t))) ** 1.35
                out[-release_samples:] *= rel_env

            # RMS polyphonic headroom leveling across all sustained organ banks
            rms = float(np.sqrt(np.mean(out * out)))
            if rms > 1e-4:
                gain = min(1.35, 0.105 / rms)
                out = out * gain
                abs_out = np.abs(out)
                mask = abs_out > 0.26
                if np.any(mask):
                    out[mask] = np.sign(out[mask]) * (0.26 + 0.05 * np.tanh((abs_out[mask] - 0.26) / 0.10))
            return out

        # Apply acoustic note duration & damping envelope
        # If damping is small (e.g. 0.5), cuts tail early to ensure crisp dryness
        effective_dur = max(0.08, float(duration) * float(damping))
        target_len = int(effective_dur * SAMPLE_RATE)

        if len(raw_audio) > target_len:
            out = raw_audio[:target_len].copy()
            # Smooth exponential fade-out over last 15ms or 15% to eliminate clicks and ringing
            fade_samples = min(int(0.025 * SAMPLE_RATE), len(out) // 2)
            if fade_samples > 0:
                fade_env = np.linspace(1.0, 0.0, fade_samples) ** 1.5
                out[-fade_samples:] *= fade_env
            return out
        else:
            # Audio is naturally shorter than duration; apply smooth micro-fade at end
            out = raw_audio.copy()
            fade_samples = min(int(0.005 * SAMPLE_RATE), len(out) // 4)
            if fade_samples > 0:
                out[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples)
            return out

    def _get_pitched_audio(
        self,
        target_pitch: int,
        samples_dict: Optional[Dict[int, np.ndarray]] = None,
        cache_tag: str = "default"
    ) -> np.ndarray:
        samples = samples_dict if samples_dict is not None else self.pitched_samples
        if target_pitch in samples:
            return samples[target_pitch]

        cache_key = (cache_tag, target_pitch)
        with self._lock:
            if cache_key in self._pitch_cache:
                return self._pitch_cache[cache_key]

        if not samples:
            return self.default_sample if self.default_sample is not None else np.zeros(100, dtype=np.float32)

        # Find closest available root pitch
        available_pitches = list(samples.keys())
        closest_pitch = min(available_pitches, key=lambda p: abs(p - target_pitch))
        base_audio = samples[closest_pitch]

        # Semitone ratio: positive delta means target is higher (shorter buffer, faster playback)
        semitone_diff = target_pitch - closest_pitch
        pitch_ratio = 2.0 ** (semitone_diff / 12.0)

        # Resample base_audio to pitch_ratio
        new_len = max(64, int(round(len(base_audio) / pitch_ratio)))
        t_orig = np.linspace(0, 1, len(base_audio), endpoint=False)
        t_new = np.linspace(0, 1, new_len, endpoint=False)
        resampled = np.interp(t_new, t_orig, base_audio).astype(np.float32)

        with self._lock:
            if len(self._pitch_cache) >= 64:
                self._pitch_cache.pop(next(iter(self._pitch_cache)), None)
            self._pitch_cache[cache_key] = resampled
        return resampled

    def _get_sorted_drum_keys(self) -> List[str]:
        """Returns ordered drum sample keys for kit routing and UI listing."""
        if not self.drum_samples:
            return []
        kit_priority = ['boom', 'tom', 'snare', 'hihat', 'kick', 'clap', 'ride', 'tink', 'openhat']
        standard_kit = [k for k in kit_priority if k in self.drum_samples]
        if len(self.drum_samples) > len(standard_kit) + 1 or not standard_kit:
            avail_kit = sorted([k for k in self.drum_samples.keys() if k not in kit_priority])
            if not avail_kit:
                avail_kit = sorted(list(self.drum_samples.keys()))
            return avail_kit
        return standard_kit

    def _get_melodic_keys(self) -> List[str]:
        """Returns ordered melodic voice keys ('__melodic__' and 'melodic:<prefix>')."""
        keys = ["__melodic__"] if self.pitched_samples else []
        keys.extend(sorted(self.pitched_groups.keys()))
        return keys

    def _resolve_mix_voice_key(self, pendulum_index: Optional[int]) -> Optional[str]:
        """Resolves which melodic or percussion voice key a pendulum uses in mix mode."""
        if pendulum_index is not None and pendulum_index in self.custom_pendulum_map:
            return self.custom_pendulum_map[pendulum_index]

        melodic_keys = self._get_melodic_keys()
        drum_keys = self._get_sorted_drum_keys()

        if pendulum_index is not None and pendulum_index >= 0:
            if melodic_keys and drum_keys:
                if pendulum_index % 2 == 0:
                    return melodic_keys[(pendulum_index // 2) % len(melodic_keys)]
                return drum_keys[(pendulum_index // 2) % len(drum_keys)]
            if melodic_keys:
                return melodic_keys[pendulum_index % len(melodic_keys)]
            if drum_keys:
                return drum_keys[pendulum_index % len(drum_keys)]

        if melodic_keys:
            return melodic_keys[0]
        return drum_keys[0] if drum_keys else None

    def _get_mix_audio(self, pitch: int, pendulum_index: Optional[int] = None) -> np.ndarray:
        """Routes mixed banks between melodic pitched samples/groups and percussion samples."""
        v_key = self._resolve_mix_voice_key(pendulum_index)
        if v_key == "__melodic__":
            return self._get_pitched_audio(pitch)
        if v_key and v_key.startswith("melodic:") and v_key in self.pitched_groups:
            return self._get_pitched_audio(pitch, self.pitched_groups[v_key], cache_tag=v_key)
        if v_key and v_key in self.drum_samples:
            return self.drum_samples[v_key]
        return self._get_pitched_audio(pitch)

    def _get_drum_audio(self, pitch: int, pendulum_index: Optional[int] = None) -> np.ndarray:
        if not self.drum_samples:
            return self.default_sample if self.default_sample is not None else np.zeros(100, dtype=np.float32)

        # 0. Check custom user mapping for this specific pendulum
        if pendulum_index is not None and pendulum_index in self.custom_pendulum_map:
            c_key = self.custom_pendulum_map[pendulum_index]
            if c_key in self.drum_samples:
                return self.drum_samples[c_key]

        # Standard musical drum kit voice priority: Sub-bass (boom) and Tom first for optimal groove
        kit_priority = ['boom', 'tom', 'snare', 'hihat', 'kick', 'clap', 'ride', 'tink', 'openhat']
        standard_kit = [k for k in kit_priority if k in self.drum_samples]

        # If the bank has multiple distinct varieties (e.g. specialized snare/tamboril bank)
        if len(self.drum_samples) > len(standard_kit) + 1 or not standard_kit:
            avail_kit = sorted([k for k in self.drum_samples.keys() if k not in kit_priority])
            if not avail_kit:
                avail_kit = sorted(list(self.drum_samples.keys()))
        else:
            avail_kit = standard_kit if standard_kit else list(self.drum_samples.keys())

        # 1. If pendulum_index is explicitly provided, assign each pendulum its own percussive voice!
        if pendulum_index is not None and pendulum_index >= 0:
            target_key = avail_kit[pendulum_index % len(avail_kit)]
            return self.drum_samples[target_key]

        # 2. General MIDI Drum mapping (standard GM notes 35-57)
        gm_map = {
            35: 'boom', 36: 'kick',
            37: 'tink', 38: 'snare', 40: 'snare',
            39: 'clap',
            41: 'tom', 43: 'tom', 45: 'tom', 47: 'tom', 48: 'tom', 50: 'tom',
            42: 'hihat', 44: 'hihat',
            46: 'openhat',
            49: 'ride', 51: 'ride', 52: 'ride', 53: 'tink', 55: 'ride', 56: 'tink', 57: 'ride'
        }
        gm_note = pitch % 128
        if gm_note in gm_map:
            mapped_key = gm_map[gm_note]
            if mapped_key in self.drum_samples:
                return self.drum_samples[mapped_key]

        # 3. For any other pitch (e.g. scale degrees or solo keys), cycle across the available drum kit
        target_key = avail_kit[pitch % len(avail_kit)]
        return self.drum_samples[target_key]


class SampleEngine:
    """
    Central manager for all instrument sample banks.
    Auto-discovers new instrument folders in assets/samples/.
    Provides instant pygame.mixer playback and studio offline WAV rendering.
    """
    def __init__(self, samples_dir: str = DEFAULT_SAMPLES_DIR):
        self.samples_dir = samples_dir
        self.banks: Dict[str, InstrumentBank] = {}
        self.sound_cache: Dict[str, pygame.mixer.Sound] = {}
        self.decay_control: float = 1.0  # 1.0 = normal, 0.4 = very dry/staccato, 2.0 = long sustain
        self.reload_instruments()

    def reload_instruments(self):
        """Scans samples_dir and loads/reloads all instrument folders."""
        self.banks.clear()
        self.sound_cache.clear()
        os.makedirs(self.samples_dir, exist_ok=True)

        subdirs = [
            d for d in os.listdir(self.samples_dir)
            if os.path.isdir(os.path.join(self.samples_dir, d))
        ]

        for d in sorted(subdirs):
            folder = os.path.join(self.samples_dir, d)
            bank = InstrumentBank(name=d, folder_path=folder)
            self.banks[d] = bank

    def get_available_instruments(self) -> List[str]:
        """Returns sorted list of all available instruments."""
        if not self.banks:
            self.reload_instruments()
        insts = list(self.banks.keys())
        if not insts:
            # Fallback list if directory is empty
            return ["piano", "marimba", "celesta", "guitar-nylon", "harp", "drums"]
        return insts

    def get_bank(self, instrument: str, load: bool = True) -> Optional[InstrumentBank]:
        bank = self.banks.get(instrument)
        if bank is None:
            for k, b in self.banks.items():
                if k.lower() == instrument.lower():
                    bank = b
                    break
        if bank is not None and load:
            bank.ensure_loaded()
        return bank

    def set_pendulum_drum_voice(self, pendulum_index: int, voice_key: Optional[str], instrument: str = "drums"):
        bank = self.get_bank(instrument)
        if bank:
            if voice_key and voice_key != "auto":
                bank.custom_pendulum_map[pendulum_index] = voice_key
            else:
                bank.custom_pendulum_map.pop(pendulum_index, None)
            self.sound_cache.clear()

    def get_pendulum_drum_voice(self, pendulum_index: int, instrument: str = "drums") -> str:
        bank = self.get_bank(instrument)
        if bank and (bank.is_drums or bank.is_mix):
            if bank.is_mix:
                return bank._resolve_mix_voice_key(pendulum_index) or ""
            if pendulum_index in bank.custom_pendulum_map:
                return bank.custom_pendulum_map[pendulum_index]
            avail_kit = bank._get_sorted_drum_keys()
            if avail_kit:
                return avail_kit[pendulum_index % len(avail_kit)]
        return ""

    def get_available_drum_voices(self, instrument: str = "drums") -> List[str]:
        bank = self.get_bank(instrument)
        if bank and (bank.drum_samples or bank.is_mix):
            sorted_voices: List[str] = []
            if bank.is_mix:
                sorted_voices.extend(bank._get_melodic_keys())
            kit_priority = ['boom', 'tom', 'snare', 'hihat', 'kick', 'clap', 'ride', 'tink', 'openhat']
            for k in kit_priority:
                if k in bank.drum_samples and k not in sorted_voices:
                    sorted_voices.append(k)
            for k in sorted(bank.drum_samples.keys()):
                if k not in sorted_voices:
                    sorted_voices.append(k)
            return sorted_voices
        return ['boom', 'tom', 'snare', 'hihat', 'kick', 'clap', 'ride', 'tink', 'openhat']

    def get_sound(
        self,
        instrument: str,
        pitch: int,
        velocity: int = 100,
        duration: float = 0.8,
        pan: float = 0.0,
        pendulum_index: Optional[int] = None,
        apply_pan_vel: bool = True,
        decay: Optional[float] = None,
    ) -> Optional[pygame.mixer.Sound]:
        """
        Retrieves (or creates and caches) a pygame.mixer.Sound ready for instantaneous zero-latency playback.
        When apply_pan_vel=False, builds a centered raw buffer so velocity & panning can be applied
        in C via channel.set_volume(gain_l, gain_r) with near-100% cache hit rates.
        """
        bank = self.banks.get(instrument)
        if bank is None:
            # Check case-insensitive match
            for k, b in self.banks.items():
                if k.lower() == instrument.lower():
                    bank = b
                    break

        if bank is None:
            # Auto reload in case user just added a new folder
            self.reload_instruments()
            bank = self.banks.get(instrument)
            if bank is None and self.banks:
                bank = next(iter(self.banks.values()))

        if bank is not None:
            bank.ensure_loaded()

        q_dur = round(max(0.08, float(duration)), 2)
        if bank and bank.is_sustained and q_dur >= 1.5:
            q_dur = round(q_dur * 2.0) / 2.0
        eff_decay = self.decay_control if decay is None else max(0.2, min(3.0, float(decay)))
        q_decay = round(float(eff_decay), 1)
        q_p_idx = pendulum_index if (bank and (bank.is_drums or bank.is_mix) and pendulum_index is not None) else -1

        if apply_pan_vel:
            q_vel = max(20, min(127, int(round(velocity / 8.0) * 8)))
            q_pan = round(float(pan), 1)
            cache_key = f"{instrument}_{pitch}_{q_vel}_{q_dur}_{q_pan}_{q_decay}_{q_p_idx}"
        else:
            cache_key = f"{instrument}_{pitch}_{q_dur}_{q_decay}_{q_p_idx}_raw"

        if cache_key in self.sound_cache:
            return self.sound_cache[cache_key]

        if bank is None:
            return None

        # 1D audio sample (mono)
        mono_audio = bank.get_voice_audio(pitch, q_dur, damping=q_decay, pendulum_index=pendulum_index)

        if apply_pan_vel:
            vel_scale = (q_vel / 127.0) ** 1.3
            mono_audio = mono_audio * vel_scale
            # Constant power stereo panning: pan in [-1.0, +1.0]
            pan_angle = (q_pan + 1.0) * 0.25 * np.pi
            gain_left = float(np.cos(pan_angle))
            gain_right = float(np.sin(pan_angle))
            stereo = np.column_stack((mono_audio * gain_left, mono_audio * gain_right))
            stereo_int16 = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
            stereo_int16 = np.ascontiguousarray(stereo_int16)
        else:
            mono_i16 = np.clip(mono_audio * 32767.0, -32768, 32767).astype(np.int16)
            stereo_int16 = np.ascontiguousarray(np.column_stack((mono_i16, mono_i16)))

        try:
            snd = pygame.sndarray.make_sound(stereo_int16)
            if len(self.sound_cache) >= 256:
                self.sound_cache.pop(next(iter(self.sound_cache)), None)
            self.sound_cache[cache_key] = snd
            return snd
        except Exception as e:
            print(f"Error creating Sound object: {e}")
            return None

    def render_audio(
        self,
        events: list,
        total_duration: float,
        instrument: str = "piano",
        sample_rate: int = SAMPLE_RATE
    ) -> np.ndarray:
        """
        Renders a list of StrikeEvents into a studio 2-channel float32 numpy array.
        """
        bank = self.banks.get(instrument)
        if bank is None:
            for k, b in self.banks.items():
                if k.lower() == instrument.lower():
                    bank = b
                    break
        if bank is None and self.banks:
            bank = next(iter(self.banks.values()))
        if bank is not None:
            bank.ensure_loaded()

        rendered = []
        max_end_idx = int(max(0.1, float(total_duration)) * sample_rate)

        for ev in events:
            start_idx = max(0, int(ev.time * sample_rate))
            dur = max(0.08, float(ev.duration))
            p_idx = getattr(ev, 'pendulum_index', None)
            if not bank:
                continue
            mono_voice = bank.get_voice_audio(ev.pitch, dur, damping=self.decay_control, pendulum_index=p_idx)
            if mono_voice is None or len(mono_voice) == 0:
                continue
            vel_scale = (ev.velocity / 127.0) ** 1.3
            mono_voice = mono_voice * vel_scale

            pan_angle = (ev.pan + 1.0) * 0.25 * np.pi
            gain_l = float(np.cos(pan_angle))
            gain_r = float(np.sin(pan_angle))
            rendered.append((start_idx, mono_voice, gain_l, gain_r))
            end_idx = start_idx + len(mono_voice)
            if end_idx > max_end_idx:
                max_end_idx = end_idx

        buffer_len = max_end_idx + int(0.05 * sample_rate)
        stereo_audio = np.zeros((buffer_len, 2), dtype=np.float32)

        for start_idx, mono_voice, gain_l, gain_r in rendered:
            end_idx = min(buffer_len, start_idx + len(mono_voice))
            chunk_len = end_idx - start_idx
            if chunk_len > 0:
                stereo_audio[start_idx:end_idx, 0] += mono_voice[:chunk_len] * gain_l
                stereo_audio[start_idx:end_idx, 1] += mono_voice[:chunk_len] * gain_r

        # Normalize cleanly
        peak = np.max(np.abs(stereo_audio))
        if peak > 1e-4:
            target_peak = 10.0 ** (-1.0 / 20.0)  # -1 dBFS
            stereo_audio = (stereo_audio / peak) * target_peak

        return stereo_audio


# Global singleton instance for easy import across audio modules
_global_sample_engine: Optional[SampleEngine] = None

def get_sample_engine() -> SampleEngine:
    global _global_sample_engine
    if _global_sample_engine is None:
        _global_sample_engine = SampleEngine()
    return _global_sample_engine
