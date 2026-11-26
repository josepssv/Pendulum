"""
Audio Synthesizer for Pendulum System
Generates high-fidelity stereo WAV files (.wav) from strike events
"""

import numpy as np
import soundfile as sf
from typing import List
from engine import StrikeEvent
from sample_engine import get_sample_engine

SAMPLE_RATE = 44100

def midi_to_freq(pitch: int) -> float:
    return 440.0 * (2.0 ** ((pitch - 69.0) / 12.0))

def synthesize_voice(
    pitch: int,
    velocity: int,
    duration: float,
    timbre: str = 'chimes',
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Synthesizes a single musical strike note according to the selected timbre and duration.
    Scales acoustic sustain and applies smooth dampening release at the end of note duration.
    Returns 1D numpy array of audio samples.
    """
    freq = midi_to_freq(pitch)
    dur = max(0.08, min(12.0, float(duration)))
    timbre_l = timbre.lower()
    is_organ = ('organ' in timbre_l or timbre_l in ('harmonium', 'hammond'))

    # Acoustic tail after key release / note dampening
    if is_organ:
        tail = min(1.6, max(0.35, dur * 0.35))
    elif timbre_l in ('chimes', 'celesta'):
        tail = min(0.35, max(0.08, dur * 0.15))
    elif timbre_l == 'drums':
        tail = 0.05
    else:
        tail = min(0.20, max(0.06, dur * 0.10))

    total_time = dur + tail
    n_samples = int(total_time * sample_rate)
    t = np.linspace(0, total_time, n_samples, endpoint=False)

    vel_scale = (velocity / 127.0) ** 1.65
    # Sustain scaling factor according to note duration
    sustain_factor = max(0.35, min(4.0, (dur / 0.85) ** 0.55))

    if timbre == 'marimba':
        # Marimba: warm resonant wood bar with fast transient
        # Partials: 1.0 (fundamental), 4.0 (2 octaves up), 10.0 (overtone)
        env = np.exp(-t * ((4.5 + freq * 0.005) / sustain_factor))
        # Transient thud
        thud_env = np.exp(-t * 80.0)
        signal = (
            1.0 * np.sin(2 * np.pi * freq * t) +
            0.35 * np.sin(2 * np.pi * freq * 4.0 * t) * np.exp(-t * 18.0) +
            0.12 * np.sin(2 * np.pi * freq * 10.0 * t) * np.exp(-t * 35.0) +
            0.08 * (np.random.rand(n_samples) * 2 - 1) * thud_env
        )
        audio = signal * env

    elif timbre == 'pluck':
        # Plucked string / Nylon guitar
        # Harmonic series with frequency-dependent dampening
        env = np.exp(-t * ((2.2 + freq * 0.003) / sustain_factor))
        signal = np.zeros(n_samples)
        for h in range(1, 8):
            h_amp = (1.0 / (h ** 1.4)) * np.exp(-t * (h * 1.8 / sustain_factor))
            signal += h_amp * np.sin(2 * np.pi * (freq * h) * t)
        audio = signal * env

    elif timbre == 'celesta':
        # Celesta / Warm Music Box
        env = np.exp(-t * (1.8 / sustain_factor))
        tremolo = 1.0 + 0.08 * np.sin(2 * np.pi * 5.0 * t)
        signal = (
            0.8 * np.sin(2 * np.pi * freq * t) +
            0.3 * np.sin(2 * np.pi * freq * 2.0 * t) +
            0.15 * np.sin(2 * np.pi * freq * 3.0 * t)
        ) * tremolo
        audio = signal * env

    elif timbre in ('drums', 'percussion'):
        # Synthesizes studio acoustic & electronic drum kit voices
        d_time = min(total_time, 0.45 if dur < 0.3 else 1.2)
        n_samples_drum = int(d_time * sample_rate)
        t_drum = np.linspace(0, d_time, n_samples_drum, endpoint=False)
        audio = np.zeros(n_samples_drum)

        # Classify drum sound by pitch or standard GM notes
        gm_note = pitch % 128
        if gm_note in (35, 36) or gm_note < 38:
            # BASS DRUM / KICK: Deep punch with rapid exponential pitch drop
            freq_env = 45.0 + 115.0 * np.exp(-t_drum * 35.0)
            phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
            body = np.sin(phase) * np.exp(-t_drum * (9.0 / sustain_factor))
            click = (np.random.rand(n_samples_drum) * 2 - 1) * np.exp(-t_drum * 120.0) * 0.25
            audio = body + click

        elif gm_note in (38, 40):
            # SNARE DRUM: Tonal body (~185 Hz) + crackling snappy noise
            snare_tone = np.sin(2 * np.pi * 185.0 * t_drum) * np.exp(-t_drum * 22.0) * 0.6
            noise = (np.random.rand(n_samples_drum) * 2 - 1) * np.exp(-t_drum * (14.0 / sustain_factor))
            hp_noise = np.diff(noise, prepend=0) * 1.8
            audio = snare_tone + hp_noise * 0.7

        elif gm_note in (42, 44, 46, 49, 51):
            # HI-HAT / CYMBAL: Crisp metallic high frequency burst
            is_open = (gm_note in (46, 49, 51))
            decay_rate = (12.0 if is_open else 60.0) / sustain_factor
            metallic = (
                np.sin(2 * np.pi * 3240 * t_drum) * 0.3 +
                np.sin(2 * np.pi * 5130 * t_drum) * 0.4 +
                np.sin(2 * np.pi * 7820 * t_drum) * 0.3
            )
            noise = (np.random.rand(n_samples_drum) * 2 - 1) * 0.7
            env = np.exp(-t_drum * decay_rate)
            audio = (metallic + noise) * env

        elif gm_note in (56, 75, 76):
            # WOODBLOCK / COWBELL: Resonant hollow percussive strike
            w_env = np.exp(-t_drum * (30.0 / sustain_factor))
            audio = (
                0.7 * np.sin(2 * np.pi * 840.0 * t_drum) +
                0.4 * np.sin(2 * np.pi * 2350.0 * t_drum)
            ) * w_env

        else:
            # TOMS / GENERAL PERCUSSION: Resonant tuned drum
            f_drum = max(55.0, freq * 0.5)
            f_env = f_drum * (1.0 + 0.8 * np.exp(-t_drum * 40.0))
            phase = 2 * np.pi * np.cumsum(f_env) / sample_rate
            body = np.sin(phase) * np.exp(-t_drum * (12.0 / sustain_factor))
            audio = body

        # Resize audio/time references for gating
        n_samples = n_samples_drum
        t = t_drum

    elif is_organ:
        # Multi-rank pipe organ fallback with slow detuned beating and velvety attack swell
        signal = np.zeros(n_samples)
        nyq = 0.45 * sample_rate
        ranks = [(0.5, 0.38), (1.0, 0.85), (2.0, 0.48), (3.0, 0.24), (4.0, 0.16), (6.0, 0.07)]
        for mult, amp in ranks:
            f_p = freq * mult
            if 18.0 <= f_p < nyq:
                signal += amp * np.sin(2 * np.pi * f_p * t)
                if mult in (1.0, 2.0):
                    signal += (amp * 0.45) * np.sin(2 * np.pi * (f_p * 1.0011) * t)
                    signal += (amp * 0.40) * np.sin(2 * np.pi * (f_p * 0.9990) * t)
        swell_samples = min(int(0.22 * sample_rate), n_samples // 3)
        if swell_samples > 0:
            swell_t = np.linspace(0.0, 1.0, swell_samples)
            signal[:swell_samples] *= 0.5 * (1.0 - np.cos(np.pi * swell_t))
        trem = 1.0 + 0.03 * np.sin(2 * np.pi * 0.22 * t)
        audio = signal * trem
        peak = np.max(np.abs(audio))
        if peak > 1e-5:
            audio = (audio / peak) * 0.36

    else:
        # Default: 'chimes' - Zen Chimes / Bells
        partials = [1.0, 2.76, 5.40, 8.93]
        weights = [0.85, 0.45, 0.22, 0.10]
        decay_rates = [1.2, 2.0, 3.8, 6.0]

        signal = np.zeros(n_samples)
        for p_ratio, weight, d_rate in zip(partials, weights, decay_rates):
            p_freq = freq * p_ratio
            if p_freq < sample_rate / 2:  # Avoid Nyquist aliasing
                signal += weight * np.sin(2 * np.pi * p_freq * t) * np.exp(-t * ((d_rate + freq * 0.001) / sustain_factor))
        audio = signal

    # Apply acoustic release gate damping after note duration ends
    gate = np.ones(n_samples)
    gate_idx = int(dur * sample_rate)
    if gate_idx < n_samples:
        t_after = t[gate_idx:] - dur
        release_rate = 4.5 if is_organ else 40.0
        gate[gate_idx:] = np.exp(-t_after * release_rate)
    audio = audio * gate

    # Anti-click smooth attack (3ms ramp)
    attack_samples = min(int(0.003 * sample_rate), len(audio) // 4)
    if attack_samples > 0:
        audio[:attack_samples] *= np.linspace(0.0, 1.0, attack_samples)

    # Anti-click smooth release at buffer end (3ms ramp)
    end_samples = min(int(0.003 * sample_rate), len(audio) // 4)
    if end_samples > 0:
        audio[-end_samples:] *= np.linspace(1.0, 0.0, end_samples)

    return audio * vel_scale


def render_audio(
    events: List[StrikeEvent],
    total_duration: float,
    timbre: str = 'piano',
    sample_rate: int = SAMPLE_RATE
) -> np.ndarray:
    """
    Renders all strike events into a high quality 2-channel (stereo) numpy array.
    Uses realistic acoustic sample bank by default, with algorithmic fallback.
    """
    # Map legacy timbre names to available sample banks
    timbre_alias = {
        'chimes': 'celesta',
        'pluck': 'guitar-nylon',
        'percussion': 'drums'
    }
    target_inst = timbre_alias.get(timbre.lower(), timbre.lower())

    sample_engine = get_sample_engine()
    avail = [inst.lower() for inst in sample_engine.get_available_instruments()]

    if target_inst in avail or any(target_inst in x for x in avail):
        # Render using studio sample banks
        return sample_engine.render_audio(
            events=events,
            total_duration=total_duration,
            instrument=target_inst,
            sample_rate=sample_rate
        )

    # Fallback to algorithmic synthesis if sample not available
    rendered = []
    max_end_idx = int(max(0.1, float(total_duration)) * sample_rate)

    for ev in events:
        start_idx = max(0, int(ev.time * sample_rate))
        voice = synthesize_voice(
            pitch=ev.pitch,
            velocity=ev.velocity,
            duration=ev.duration,
            timbre=timbre,
            sample_rate=sample_rate
        )
        if voice is None or len(voice) == 0:
            continue
        pan_angle = (ev.pan + 1.0) * 0.25 * np.pi
        gain_left = float(np.cos(pan_angle))
        gain_right = float(np.sin(pan_angle))
        rendered.append((start_idx, voice, gain_left, gain_right))
        end_idx = start_idx + len(voice)
        if end_idx > max_end_idx:
            max_end_idx = end_idx

    buffer_len = max_end_idx + int(0.05 * sample_rate)
    stereo_audio = np.zeros((buffer_len, 2), dtype=np.float32)

    for start_idx, voice, gain_left, gain_right in rendered:
        end_idx = min(buffer_len, start_idx + len(voice))
        chunk_len = end_idx - start_idx
        if chunk_len > 0:
            stereo_audio[start_idx:end_idx, 0] += voice[:chunk_len] * gain_left
            stereo_audio[start_idx:end_idx, 1] += voice[:chunk_len] * gain_right

    max_val = np.max(np.abs(stereo_audio))
    if max_val > 1e-5:
        target_peak = 10.0 ** (-1.0 / 20.0)  # ~0.891
        stereo_audio = (stereo_audio / max_val) * target_peak

    return stereo_audio


def export_wav(
    events: List[StrikeEvent],
    output_path: str,
    total_duration: float,
    timbre: str = 'chimes',
    sample_rate: int = SAMPLE_RATE
) -> str:
    """
    Renders simulation to stereo audio and saves to WAV file.
    """
    audio = render_audio(events, total_duration, timbre=timbre, sample_rate=sample_rate)
    sf.write(output_path, audio, sample_rate, subtype='PCM_16')
    return output_path
