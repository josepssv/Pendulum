"""
Live Real-Time Audio Engine & Session Recorder
Allows instantaneous low-latency live sound synthesis and records user live improvisations.
"""

import time
import os
import math
import numpy as np
import pygame
import soundfile as sf
from typing import Any, Dict, List, Optional, Tuple
from audio_synth import synthesize_voice, render_audio, SAMPLE_RATE
from sample_engine import get_sample_engine
from midi_export import export_midi
from engine import StrikeEvent, midi_to_note_name


def _build_volume_envelope(
    points: List[Tuple[float, float]],
    n_samples: int,
    sample_rate: int = SAMPLE_RATE,
    ramp_sec: float = 0.025,
) -> np.ndarray:
    """Builds a smooth sample-level gain envelope from timestamped (t_sec, vol) points."""
    if n_samples <= 0:
        return np.zeros(0, dtype=np.float32)
    if not points:
        return np.ones(n_samples, dtype=np.float32)

    sorted_pts = sorted(points, key=lambda item: float(item[0]))
    init_v = max(0.0, min(1.0, float(sorted_pts[0][1])))
    env = np.full(n_samples, init_v, dtype=np.float32)
    ramp_samples = max(1, int(round(ramp_sec * sample_rate)))

    for t_sec, vol in sorted_pts[1:]:
        idx = int(round(max(0.0, float(t_sec)) * sample_rate))
        if idx >= n_samples:
            break
        target_v = max(0.0, min(1.0, float(vol)))
        start_v = float(env[idx])
        end_idx = min(n_samples, idx + ramp_samples)
        ramp_len = end_idx - idx
        if ramp_len > 1:
            env[idx:end_idx] = np.linspace(start_v, target_v, ramp_len, endpoint=True, dtype=np.float32)
        if end_idx < n_samples:
            env[end_idx:] = target_v
        elif ramp_len == 1:
            env[idx] = target_v

    return env


class BackingTrackManager:
    """
    Manages loading, low-latency playback via dedicated mixer channel,
    real-time volume control, and synchronized buffer slicing
    of an imported external WAV or MP3 backing track.
    """
    def __init__(self):
        self.filepath: Optional[str] = None
        self.filename: str = ""
        self.audio_data: Optional[np.ndarray] = None  # (samples, 2) float32 at SAMPLE_RATE
        self.sound: Optional[pygame.mixer.Sound] = None
        self.channel: Optional[pygame.mixer.Channel] = None
        self.duration: float = 0.0
        self.volume: float = 0.8
        self.loop: bool = True
        self.is_loaded: bool = False
        self.is_playing: bool = False
        self.play_start_time: float = 0.0
        self.accumulated_pos: float = 0.0
        self.on_volume_change = None

    def load(self, filepath: str) -> bool:
        try:
            data, sr = sf.read(filepath, dtype='float32')
            if data.ndim == 1:
                data = np.column_stack((data, data))
            elif data.ndim == 2 and data.shape[1] > 2:
                data = data[:, :2]

            # Resample to SAMPLE_RATE if needed
            if sr != SAMPLE_RATE:
                new_len = int(round(len(data) * SAMPLE_RATE / sr))
                t_orig = np.linspace(0, 1, len(data), endpoint=False)
                t_new = np.linspace(0, 1, new_len, endpoint=False)
                ch0 = np.interp(t_new, t_orig, data[:, 0])
                ch1 = np.interp(t_new, t_orig, data[:, 1])
                data = np.column_stack((ch0, ch1)).astype(np.float32)

            self.audio_data = data
            self.filepath = filepath
            self.filename = os.path.basename(filepath)
            self.duration = len(data) / float(SAMPLE_RATE)
            self.accumulated_pos = 0.0

            # Convert to int16 contiguous stereo array for pygame Sound
            int16_data = np.clip(data * 32767.0, -32768, 32767).astype(np.int16)
            int16_data = np.ascontiguousarray(int16_data)
            self.sound = pygame.sndarray.make_sound(int16_data)

            self.is_loaded = True
            if self.channel:
                self.channel.set_volume(self.volume)

            return True
        except Exception as e:
            print(f"Error loading backing track {filepath}: {e}")
            return False

    def unload(self):
        self.stop()
        self.filepath = None
        self.filename = ""
        self.audio_data = None
        self.sound = None
        self.duration = 0.0
        self.is_loaded = False
        self.is_playing = False
        self.accumulated_pos = 0.0

    def play(self, start_pos: float = 0.0, loop: Optional[bool] = None):
        if not self.is_loaded or self.sound is None or self.channel is None:
            return
        if loop is not None:
            self.loop = loop
        try:
            loops = -1 if self.loop else 0
            self.channel.set_volume(self.volume)
            self.channel.play(self.sound, loops=loops)
            self.is_playing = True
            self.play_start_time = time.time()
            self.accumulated_pos = start_pos
        except Exception as e:
            print(f"Error playing backing track: {e}")

    def pause(self):
        if not self.is_loaded or self.channel is None:
            return
        try:
            if self.is_playing:
                self.accumulated_pos += (time.time() - self.play_start_time)
                if self.duration > 0 and self.loop:
                    self.accumulated_pos %= self.duration
            self.channel.pause()
            self.is_playing = False
        except Exception:
            pass

    def unpause(self):
        if not self.is_loaded or self.channel is None or self.sound is None:
            return
        try:
            if not self.channel.get_busy():
                loops = -1 if self.loop else 0
                self.channel.set_volume(self.volume)
                self.channel.play(self.sound, loops=loops)
            else:
                self.channel.set_volume(self.volume)
                self.channel.unpause()
            self.is_playing = True
            self.play_start_time = time.time()
        except Exception:
            pass

    def stop(self):
        if not self.is_loaded or self.channel is None:
            return
        try:
            self.channel.stop()
            self.is_playing = False
            self.accumulated_pos = 0.0
        except Exception:
            pass

    def set_volume(self, vol: float):
        self.volume = max(0.0, min(1.0, float(vol)))
        if self.channel:
            try:
                self.channel.set_volume(self.volume)
            except Exception:
                pass
        if callable(self.on_volume_change):
            self.on_volume_change(self.volume)

    def get_current_pos(self) -> float:
        if not self.is_loaded:
            return 0.0
        if self.is_playing:
            cur = self.accumulated_pos + (time.time() - self.play_start_time)
            if self.duration > 0 and self.loop:
                cur %= self.duration
            return cur
        return self.accumulated_pos

    @staticmethod
    def slice_buffer(
        audio_data: Optional[np.ndarray],
        start_sec: float,
        duration_sec: float,
        loop: bool,
        sample_rate: int = SAMPLE_RATE,
    ) -> Optional[np.ndarray]:
        if audio_data is None or len(audio_data) == 0:
            return None
        target_len = int(round(duration_sec * sample_rate))
        if target_len <= 0:
            return np.zeros((0, 2), dtype=np.float32)
        out = np.zeros((target_len, 2), dtype=np.float32)
        total_samples = len(audio_data)

        start_sample = int(round(start_sec * sample_rate))
        if loop:
            start_sample %= total_samples

        pos = 0
        cur_src = start_sample
        while pos < target_len:
            if cur_src >= total_samples:
                if loop:
                    cur_src = 0
                else:
                    break
            chunk_len = min(target_len - pos, total_samples - cur_src)
            out[pos:pos + chunk_len] = audio_data[cur_src:cur_src + chunk_len]
            pos += chunk_len
            cur_src += chunk_len

        return out

    def extract_slice(
        self,
        start_sec: float,
        duration_sec: float,
        apply_volume: bool = True,
    ) -> Optional[np.ndarray]:
        out = self.slice_buffer(
            self.audio_data,
            start_sec=start_sec,
            duration_sec=duration_sec,
            loop=self.loop,
            sample_rate=SAMPLE_RATE,
        )
        if out is None:
            return None
        return out * float(self.volume) if apply_volume else out


class LiveRecorder:
    def __init__(self):
        self.is_recording = False
        self.start_wall_time = 0.0
        self.recorded_events: List[StrikeEvent] = []
        self.active_timbre = "chimes"
        self.tempo_bpm = 96.0
        self.time_signature = "4/4"
        self.backing_mgr: Optional[BackingTrackManager] = None
        self.backing_start_pos: float = 0.0
        self.master_volume_getter = None
        self.synth_vol_automation: List[Tuple[float, float]] = []
        self.backing_vol_automation: List[Tuple[float, float]] = []
        self.default_decay: float = 1.0

    def start(self, timbre: str = "chimes", bpm: float = 96.0, time_signature: str = "4/4",
              backing_track_mgr: Optional[BackingTrackManager] = None):
        self.is_recording = True
        self.start_wall_time = time.time()
        self.recorded_events = []
        self.active_timbre = timbre
        self.tempo_bpm = bpm
        self.time_signature = time_signature
        self.backing_mgr = backing_track_mgr
        if backing_track_mgr and backing_track_mgr.is_loaded:
            self.backing_start_pos = backing_track_mgr.get_current_pos()
        else:
            self.backing_start_pos = 0.0
        init_synth = (
            max(0.0, min(1.0, float(self.master_volume_getter())))
            if callable(self.master_volume_getter)
            else 1.0
        )
        init_backing = (
            max(0.0, min(1.0, float(backing_track_mgr.volume)))
            if backing_track_mgr
            else 1.0
        )
        self.synth_vol_automation = [(0.0, init_synth)]
        self.backing_vol_automation = [(0.0, init_backing)]
        self.default_decay = float(get_sample_engine().decay_control)

    def record_synth_volume(self, vol: float):
        if self.is_recording:
            t_sec = max(0.0, time.time() - self.start_wall_time)
            self.synth_vol_automation.append((t_sec, max(0.0, min(1.0, float(vol)))))

    def record_backing_volume(self, vol: float):
        if self.is_recording:
            t_sec = max(0.0, time.time() - self.start_wall_time)
            self.backing_vol_automation.append((t_sec, max(0.0, min(1.0, float(vol)))))

    def record_event(
        self,
        pitch: int,
        velocity: int,
        duration: float,
        pan: float,
        pendulum_index: int = 0,
        timbre: Optional[str] = None,
        decay: Optional[float] = None,
    ) -> Optional[StrikeEvent]:
        if not self.is_recording:
            return None
        t_sec = time.time() - self.start_wall_time
        ev = StrikeEvent(
            time=t_sec,
            pendulum_index=pendulum_index,
            pitch=pitch,
            velocity=velocity,
            duration=duration,
            pan=pan,
            timbre=timbre or self.active_timbre,
            decay=decay if decay is not None else self.default_decay,
        )
        self.recorded_events.append(ev)
        return ev

    def update_event_duration(self, event: Optional[StrikeEvent], actual_duration: float):
        """Updates note duration in real-time when a held key is released."""
        if event is not None and self.is_recording:
            event.duration = max(0.06, float(actual_duration))

    def elapsed_seconds(self) -> float:
        if not self.is_recording:
            return 0.0
        return time.time() - self.start_wall_time

    def prepare_stop(self, stop_time_sec: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Atomically stops recording on the caller thread and freezes an immutable session snapshot."""
        if not self.is_recording:
            return None

        self.is_recording = False
        elapsed_now = max(1.0, time.time() - self.start_wall_time)
        stop_sec = (
            min(elapsed_now, max(0.0, float(stop_time_sec)))
            if stop_time_sec is not None
            else elapsed_now
        )
        total_duration = max(1.0, elapsed_now)
        events_copy = [
            StrikeEvent(
                ev.time,
                ev.pendulum_index,
                ev.pitch,
                ev.velocity,
                ev.duration,
                ev.pan,
                timbre=getattr(ev, 'timbre', None) or self.active_timbre,
                decay=getattr(ev, 'decay', None),
            )
            for ev in self.recorded_events
        ]

        backing_audio = None
        backing_loop = True
        backing_start_pos = 0.0
        backing_filename = ""
        if self.backing_mgr and self.backing_mgr.is_loaded and self.backing_mgr.audio_data is not None:
            backing_audio = self.backing_mgr.audio_data
            backing_loop = bool(self.backing_mgr.loop)
            backing_start_pos = float(self.backing_start_pos)
            backing_filename = self.backing_mgr.filename or "backing_track"

        return {
            "total_duration": total_duration,
            "stop_time_sec": stop_sec,
            "events": events_copy,
            "synth_vol_automation": list(self.synth_vol_automation),
            "backing_vol_automation": list(self.backing_vol_automation),
            "active_timbre": self.active_timbre,
            "tempo_bpm": self.tempo_bpm,
            "time_signature": self.time_signature,
            "default_decay": self.default_decay,
            "backing_audio": backing_audio,
            "backing_loop": backing_loop,
            "backing_start_pos": backing_start_pos,
            "backing_filename": backing_filename,
        }

    def _render_events(
        self,
        events: List[StrikeEvent],
        total_duration: float,
        fallback_timbre: str,
        default_decay: float,
        sample_rate: int = SAMPLE_RATE,
    ) -> np.ndarray:
        """Renders recorded strike events with per-event timbre and decay without clipping final tails."""
        timbre_alias = {'chimes': 'celesta', 'pluck': 'guitar-nylon', 'percussion': 'drums'}
        sample_engine = get_sample_engine()

        rendered: List[Tuple[int, np.ndarray, float, float]] = []
        max_end_idx = int(max(1.0, float(total_duration)) * sample_rate)

        for ev in events:
            start_idx = max(0, int(ev.time * sample_rate))
            ev_timbre = getattr(ev, 'timbre', None) or fallback_timbre
            ev_decay = getattr(ev, 'decay', None)
            if ev_decay is None:
                ev_decay = default_decay
            target_inst = timbre_alias.get(ev_timbre.lower(), ev_timbre.lower())
            dur = max(0.08, float(ev.duration))

            bank = sample_engine.get_bank(target_inst, load=True)
            if bank is not None:
                p_idx = getattr(ev, 'pendulum_index', None)
                mono_voice = bank.get_voice_audio(
                    ev.pitch, dur, damping=float(ev_decay), pendulum_index=p_idx
                )
                vel_scale = (ev.velocity / 127.0) ** 1.3
                mono_voice = mono_voice * vel_scale
            else:
                mono_voice = synthesize_voice(
                    pitch=ev.pitch,
                    velocity=ev.velocity,
                    duration=dur,
                    timbre=ev_timbre,
                    sample_rate=sample_rate,
                )

            if mono_voice is None or len(mono_voice) == 0:
                continue

            pan_clamped = max(-1.0, min(1.0, float(ev.pan)))
            pan_angle = (pan_clamped + 1.0) * 0.25 * np.pi
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

        peak = float(np.max(np.abs(stereo_audio))) if len(stereo_audio) > 0 else 0.0
        if peak > 1e-4:
            target_peak = 10.0 ** (-1.0 / 20.0)
            stereo_audio = (stereo_audio / peak) * target_peak

        return stereo_audio

    def stop_and_save(
        self,
        base_folder: str = "exports",
        base_name: str = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        snap = snapshot if snapshot is not None else self.prepare_stop()
        if not snap:
            return {}

        events = snap['events']
        total_duration = snap['total_duration']
        stop_sec = snap.get('stop_time_sec')
        render_dur = float(stop_sec) if stop_sec is not None else float(total_duration)
        os.makedirs(base_folder, exist_ok=True)

        if not base_name:
            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            base_name = f"live_session_{timestamp_str}"

        wav_path = os.path.join(base_folder, f"{base_name}.wav")
        mid_path = os.path.join(base_folder, f"{base_name}.mid")

        # 1. Render recorded performance with per-event timbres and apply timestamped Master Sonido envelope
        live_audio = self._render_events(
            events=events,
            total_duration=render_dur,
            fallback_timbre=snap['active_timbre'],
            default_decay=snap['default_decay'],
            sample_rate=SAMPLE_RATE,
        )
        synth_env = _build_volume_envelope(snap['synth_vol_automation'], len(live_audio), SAMPLE_RATE)
        live_audio = live_audio * synth_env[:, np.newaxis]
        synth_peak = float(np.max(np.abs(live_audio))) if len(live_audio) > 0 else 0.0

        has_backing = False
        backing_name = ""
        if snap['backing_audio'] is not None:
            duration_to_extract = len(live_audio) / float(SAMPLE_RATE)
            backing_slice = BackingTrackManager.slice_buffer(
                snap['backing_audio'],
                start_sec=snap['backing_start_pos'],
                duration_sec=duration_to_extract,
                loop=snap['backing_loop'],
                sample_rate=SAMPLE_RATE,
            )
            if backing_slice is not None and len(backing_slice) > 0:
                backing_env = _build_volume_envelope(snap['backing_vol_automation'], len(backing_slice), SAMPLE_RATE)
                backing_slice = backing_slice * backing_env[:, np.newaxis]

                if stop_sec is not None:
                    fade_start = int(max(0.0, float(stop_sec)) * SAMPLE_RATE)
                    fade_len = int(0.8 * SAMPLE_RATE)
                    if fade_start < len(backing_slice):
                        fade_end = min(len(backing_slice), fade_start + fade_len)
                        ramp_n = fade_end - fade_start
                        if ramp_n > 0:
                            ramp = np.linspace(1.0, 0.0, ramp_n, dtype=np.float32)
                            backing_slice[fade_start:fade_end] *= ramp[:, np.newaxis]
                        if fade_end < len(backing_slice):
                            backing_slice[fade_end:] = 0.0

                mix_len = min(len(live_audio), len(backing_slice))
                mixed = np.zeros_like(live_audio)
                mixed[:mix_len] = live_audio[:mix_len] + backing_slice[:mix_len]
                if len(live_audio) > mix_len:
                    mixed[mix_len:] = live_audio[mix_len:]

                # Soft-clip / peak normalize if exceeds 0.98 to avoid digital harsh clipping
                peak = np.max(np.abs(mixed))
                if peak > 0.98:
                    target_peak = 10.0 ** (-0.5 / 20.0)  # ~0.944
                    mixed = (mixed / peak) * target_peak

                sf.write(wav_path, mixed, SAMPLE_RATE, subtype='PCM_16')
                has_backing = True
                backing_name = snap['backing_filename']

        if not has_backing:
            sf.write(wav_path, live_audio, SAMPLE_RATE, subtype='PCM_16')

        # 2. Export standard multi-track MIDI matching exact live performance timestamps
        export_midi(
            events=events,
            output_path=mid_path,
            tempo_bpm=snap['tempo_bpm'],
            multi_track=True,
            time_signature=snap['time_signature'],
        )

        synth_vols = [float(v) for _, v in snap['synth_vol_automation']] or [1.0]
        timbres_used = list(dict.fromkeys(
            (getattr(ev, 'timbre', None) or snap['active_timbre'])
            for ev in events
        ))

        return {
            "wav": wav_path,
            "midi": mid_path,
            "duration": len(live_audio) / float(SAMPLE_RATE),
            "events_count": len(events),
            "has_backing": has_backing,
            "backing_name": backing_name,
            "synth_vol_min": float(min(synth_vols)),
            "synth_vol_max": float(max(synth_vols)),
            "synth_peak": synth_peak,
            "timbres_used": timbres_used,
        }


class LiveAudioEngine:
    def __init__(self):
        self.initialized = False
        self.sample_cache: Dict[str, pygame.mixer.Sound] = {}
        self.active_sustained_voices: Dict[Tuple[int, int], pygame.mixer.Channel] = {}
        self.sustained_channel_order: List[pygame.mixer.Channel] = []
        self.recorder = LiveRecorder()
        self.backing_mgr = BackingTrackManager()
        self.active_timbre = "chimes"
        self.master_volume: float = 1.0
        self.note_channels: List[pygame.mixer.Channel] = []
        self.channel_base_gains: Dict[int, Tuple[float, float]] = {}
        self._next_channel_idx: int = 0
        self.recorder.master_volume_getter = lambda: self.master_volume
        self.backing_mgr.on_volume_change = self.recorder.record_backing_volume
        self._init_mixer()

    def _init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                # 1024 sample buffer (~23.2ms) prevents WASAPI/SDL2 underruns under polyphonic organ drones
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=1024)
            num_channels = 64
            pygame.mixer.set_num_channels(num_channels)
            # Channel 0 reserved exclusively for the backing track so find_channel() won't touch it
            pygame.mixer.set_reserved(1)
            self.backing_channel = pygame.mixer.Channel(0)
            self.backing_mgr.channel = self.backing_channel
            self.note_channels = [pygame.mixer.Channel(i) for i in range(1, num_channels)]
            self.channel_base_gains = {}
            self._next_channel_idx = 0
            self.initialized = True
        except Exception as e:
            print(f"Warning: Could not initialize low-latency audio mixer: {e}")
            self.initialized = False

    def set_timbre(self, timbre: str):
        if self.active_timbre != timbre:
            self.active_timbre = timbre
            # Pre-clear cache and voice tracking if switching timbre
            self.sample_cache.clear()
            self.active_sustained_voices.clear()
            self.sustained_channel_order.clear()

    def set_decay(self, decay_val: float):
        """Sets note decay/damping factor: < 1.0 = drier/staccato, > 1.0 = longer sustain."""
        sample_engine = get_sample_engine()
        sample_engine.decay_control = max(0.2, min(3.0, float(decay_val)))
        self.sample_cache.clear()

    def _get_sound(
        self,
        pitch: int,
        velocity: int,
        duration: float,
        pan: float,
        pendulum_index: Optional[int] = None,
        timbre: Optional[str] = None,
        decay: Optional[float] = None,
    ) -> pygame.mixer.Sound:
        eff_timbre = timbre or self.active_timbre
        # First attempt to load/retrieve from high-quality acoustic sample engine (centered raw for C-level pan/vel)
        try:
            # Map legacy timbre names if needed
            timbre_alias = {'chimes': 'celesta', 'pluck': 'guitar-nylon', 'percussion': 'drums'}
            target_inst = timbre_alias.get(eff_timbre.lower(), eff_timbre.lower())
            snd = get_sample_engine().get_sound(
                instrument=target_inst,
                pitch=pitch,
                velocity=velocity,
                duration=duration,
                pan=pan,
                pendulum_index=pendulum_index,
                apply_pan_vel=False,
                decay=decay,
            )
            if snd is not None:
                return snd
        except Exception as e:
            print(f"SampleEngine lookup fallback: {e}")

        # Quantize duration for fallback synthesis cache; velocity & pan applied on channel
        q_dur = round(max(0.08, float(duration)), 2)
        if ('organ' in eff_timbre.lower()) and q_dur >= 1.5:
            q_dur = round(q_dur * 2.0) / 2.0
        cache_key = f"{eff_timbre}_{pitch}_{q_dur}_raw"

        if cache_key in self.sample_cache:
            return self.sample_cache[cache_key]

        # Synthesize centered audio chunk at full scale
        voice = synthesize_voice(
            pitch=pitch,
            velocity=127,
            duration=q_dur,
            timbre=eff_timbre,
            sample_rate=SAMPLE_RATE
        )

        stereo = np.column_stack((voice, voice))
        # Convert float32 to int16 for pygame.sndarray
        stereo_int16 = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
        # Ensure contiguous memory layout
        stereo_int16 = np.ascontiguousarray(stereo_int16)

        snd = pygame.sndarray.make_sound(stereo_int16)
        if len(self.sample_cache) >= 256:
            self.sample_cache.pop(next(iter(self.sample_cache)), None)
        self.sample_cache[cache_key] = snd
        return snd

    def _find_free_note_channel(self) -> Tuple[Optional[int], Optional[pygame.mixer.Channel]]:
        """Finds an idle pre-allocated mixer channel (excluding reserved channel 0) round-robin."""
        n = len(self.note_channels)
        if n == 0:
            return None, None
        start = self._next_channel_idx % n
        for offset in range(n):
            idx = (start + offset) % n
            ch = self.note_channels[idx]
            if not ch.get_busy():
                self._next_channel_idx = (idx + 1) % n
                return idx, ch
        return None, None

    def set_master_volume(self, vol: float):
        """Sets master volume [0.0..1.0] for produced sounds and updates active note channels live."""
        self.master_volume = max(0.0, min(1.0, float(vol)))
        self.recorder.record_synth_volume(self.master_volume)
        if not self.initialized:
            return
        for slot_idx, ch in enumerate(self.note_channels):
            try:
                if ch.get_busy():
                    base_l, base_r = self.channel_base_gains.get(slot_idx, (1.0, 1.0))
                    ch.set_volume(
                        max(0.0, min(1.0, base_l * self.master_volume)),
                        max(0.0, min(1.0, base_r * self.master_volume)),
                    )
            except Exception:
                pass

    def play_note(
        self,
        pitch: int,
        velocity: int = 100,
        duration: float = 0.8,
        pan: float = 0.0,
        pendulum_index: int = 0,
        timbre: Optional[str] = None,
        decay: Optional[float] = None,
    ):
        """
        Plays a live musical note immediately with zero perceptible latency.
        Applies C-level stereo panning, dynamic polyphonic headroom, and smooth
        crossfade on repeated sustained organ pitches to eliminate clipping and comb-filtering.
        Returns a tuple of (channel, recorded_event).
        """
        if not self.initialized:
            return None, None

        eff_timbre = timbre or self.active_timbre
        eff_decay = (
            get_sample_engine().decay_control
            if decay is None
            else max(0.2, min(3.0, float(decay)))
        )

        ch = None
        try:
            timbre_alias = {'chimes': 'celesta', 'pluck': 'guitar-nylon', 'percussion': 'drums'}
            target_inst = timbre_alias.get(eff_timbre.lower(), eff_timbre.lower())
            bank = get_sample_engine().get_bank(target_inst, load=False)
            is_sustained = bool(bank and bank.is_sustained) or ('organ' in eff_timbre.lower())

            snd = self._get_sound(
                pitch,
                velocity,
                duration,
                pan,
                pendulum_index=pendulum_index,
                timbre=eff_timbre,
                decay=eff_decay,
            )

            vel_scale = (max(16, min(127, int(velocity))) / 127.0) ** 1.3
            pan_clamped = max(-1.0, min(1.0, float(pan)))
            pan_angle = (pan_clamped + 1.0) * 0.25 * np.pi
            poly_scale = 1.0

            if is_sustained:
                # Prune finished channels
                self.sustained_channel_order = [c for c in self.sustained_channel_order if c.get_busy()]
                self.active_sustained_voices = {
                    k: c for k, c in self.active_sustained_voices.items() if c.get_busy()
                }

                # Same-voice crossfade: prevent phase-offset comb-filtering on re-triggered note
                voice_key = (pendulum_index, pitch)
                old_ch = self.active_sustained_voices.pop(voice_key, None)
                if old_ch is not None:
                    if old_ch.get_busy():
                        old_ch.fadeout(320)
                    if old_ch in self.sustained_channel_order:
                        self.sustained_channel_order.remove(old_ch)

                # Max polyphony guard for sustained voices
                while len(self.sustained_channel_order) >= 14:
                    oldest = self.sustained_channel_order.pop(0)
                    if oldest.get_busy():
                        oldest.fadeout(400)

                # Dynamic headroom scaling inversely with sqrt(active voices / 2.2)
                n_active = len(self.sustained_channel_order) + 1
                poly_scale = max(0.38, min(1.0, 1.0 / math.sqrt(max(1.0, n_active / 2.2))))

            base_l = max(0.0, min(1.0, float(np.cos(pan_angle)) * vel_scale * poly_scale))
            base_r = max(0.0, min(1.0, float(np.sin(pan_angle)) * vel_scale * poly_scale))

            slot_idx, ch = self._find_free_note_channel()
            if ch is not None and slot_idx is not None:
                self.channel_base_gains[slot_idx] = (base_l, base_r)
                gain_l = max(0.0, min(1.0, base_l * self.master_volume))
                gain_r = max(0.0, min(1.0, base_r * self.master_volume))
                if self.master_volume <= 0.0:
                    ch.set_volume(0.0)
                ch.play(snd)
                ch.set_volume(gain_l, gain_r)
                if is_sustained:
                    self.active_sustained_voices[(pendulum_index, pitch)] = ch
                    self.sustained_channel_order.append(ch)
        except Exception:
            pass

        rec_ev = None
        if self.recorder.is_recording:
            rec_ev = self.recorder.record_event(
                pitch,
                velocity,
                duration,
                pan,
                pendulum_index,
                timbre=eff_timbre,
                decay=eff_decay,
            )

        return ch, rec_ev

    def has_active_notes(self) -> bool:
        """Returns True while any mixer note channel (excluding backing track) is still ringing."""
        if not self.initialized:
            return False
        try:
            return any(ch.get_busy() for ch in self.note_channels)
        except Exception:
            return False

    def stop_channel(
        self,
        channel: Optional[pygame.mixer.Channel],
        fadeout_ms: int = 80,
        timbre: Optional[str] = None,
    ):
        """Smoothly dampens/fades out a playing channel on key release."""
        if channel and self.initialized:
            try:
                eff_timbre = timbre or self.active_timbre
                timbre_alias = {'chimes': 'celesta', 'pluck': 'guitar-nylon', 'percussion': 'drums'}
                target_inst = timbre_alias.get(eff_timbre.lower(), eff_timbre.lower())
                bank = get_sample_engine().get_bank(target_inst, load=False)
                if (bank and bank.is_sustained) or ('organ' in eff_timbre.lower()):
                    fadeout_ms = max(fadeout_ms, 280)
                channel.fadeout(fadeout_ms)
            except Exception:
                pass
