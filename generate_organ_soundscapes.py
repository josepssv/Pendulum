"""
Synthesized Studio Organ Soundscape Bank Generator for Pendulum Polyphony.
Generates lush, sustained, cathedral-reverberated organ soundscape banks (.flac, 44.1 kHz, 16-bit mono)
into assets/samples/:
  - organ-cathedral   (16 notes C1..C6): Multi-rank principal pipe organ + Voix Céleste + hall reverb
  - organ-drone       (16 notes C1..C6): Deep evolving ambient drone organ with slow LFO harmonic drift
  - organ-glass       (19 notes C2..C7): Luminous glass-flute & shimmer overtone organ
  - organ-paisaje-mix (40 notes):        4-layer melodic mix bank (drone, catedral, cristal, armonio)
"""

import os
import shutil
import argparse
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, lfilter

SAMPLE_RATE = 44100
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "assets", "samples")

NOTE_SEMITONES = {
    'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11
}


def note_to_freq(note_name: str) -> float:
    """Converts a note label like 'C4', 'Gs2', 'Fs3' to frequency in Hz."""
    s = note_name.strip()
    letter = s[0].upper()
    rest = s[1:]
    acc = 0
    if rest.startswith(('s', 'S', '#')):
        acc = 1
        octave = int(rest[1:])
    elif rest.startswith('b'):
        acc = -1
        octave = int(rest[1:])
    else:
        octave = int(rest)
    midi = (octave + 1) * 12 + NOTE_SEMITONES[letter] + acc
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def _make_pink_noise(n_samples: int, rng: np.random.Generator) -> np.ndarray:
    """Generates smooth 1/f pink noise normalized to unit std."""
    white = rng.standard_normal(n_samples)
    # 3-pole Voss-McCartney / Paul Kellet IIR approximation
    b = np.array([0.049922035, -0.095993537, 0.050612699, -0.004408786], dtype=np.float64)
    a = np.array([1.0, -2.494956002, 2.017265875, -0.522189400], dtype=np.float64)
    pink = lfilter(b, a, white)
    std = np.std(pink)
    if std > 1e-8:
        pink /= std
    return pink


def _bandpass_noise(noise: np.ndarray, low_hz: float, high_hz: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Bandpass filters noise safely within Nyquist bounds."""
    nyq = 0.5 * sr
    lo = max(25.0, min(low_hz, nyq * 0.80))
    hi = max(lo + 40.0, min(high_hz, nyq * 0.90))
    sos = butter(2, [lo / nyq, hi / nyq], btype='band', output='sos')
    return sosfilt(sos, noise)


def _lowpass_filter(signal: np.ndarray, cutoff_hz: float, sr: int = SAMPLE_RATE, order: int = 2) -> np.ndarray:
    """Applies a gentle lowpass filter safely below Nyquist."""
    nyq = 0.5 * sr
    norm = min(0.88, max(0.02, cutoff_hz / nyq))
    sos = butter(order, norm, btype='low', output='sos')
    return sosfilt(sos, signal)


def _highpass_dc(signal: np.ndarray, cutoff_hz: float = 24.0, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Removes subsonic rumble and DC offset."""
    nyq = 0.5 * sr
    sos = butter(2, max(10.0, cutoff_hz) / nyq, btype='high', output='sos')
    return sosfilt(sos, signal)


def apply_cathedral_reverb(
    signal: np.ndarray,
    sr: int = SAMPLE_RATE,
    wet: float = 0.42,
    rt60: float = 3.5,
    damping: float = 0.30
) -> np.ndarray:
    """
    Fast damped Schroeder cathedral hall reverb using scipy.signal.lfilter.
    4 parallel lowpass-damped comb filters cascaded into 2 series allpass diffusers.
    Comb transfer function: H(z) = ((1-d)*z^-D) / (1 - d*z^-1 - g*(1-d)*z^-D)
    """
    x = np.asarray(signal, dtype=np.float64)
    if len(x) == 0:
        return x

    scale = sr / 44100.0
    # Prime tap delays at ~37.1 ms, 43.3 ms, 53.7 ms, 67.3 ms
    comb_delays = [max(32, int(round(d * scale))) for d in (1637, 1907, 2371, 2969)]
    allpass_delays = [max(16, int(round(d * scale))) for d in (227, 73)]

    d = float(np.clip(damping, 0.22, 0.40))
    rt = max(0.8, float(rt60))

    comb_sum = np.zeros_like(x, dtype=np.float64)
    for idx, D in enumerate(comb_delays):
        # Slight damping spread per tap for richer modal density
        d_tap = float(np.clip(d + (idx - 1.5) * 0.025, 0.18, 0.45))
        g = min(0.955, 10.0 ** (-3.0 * D / (rt * sr)))

        b = np.zeros(D + 1, dtype=np.float64)
        b[D] = 1.0 - d_tap

        a = np.zeros(D + 1, dtype=np.float64)
        a[0] = 1.0
        a[1] = -d_tap
        a[D] = -g * (1.0 - d_tap)

        comb_sum += lfilter(b, a, x)

    diffused = comb_sum / float(len(comb_delays))

    ap_gain = 0.68
    for M in allpass_delays:
        b_ap = np.zeros(M + 1, dtype=np.float64)
        b_ap[0] = -ap_gain
        b_ap[M] = 1.0

        a_ap = np.zeros(M + 1, dtype=np.float64)
        a_ap[0] = 1.0
        a_ap[M] = -ap_gain

        diffused = lfilter(b_ap, a_ap, diffused)

    wet_clamped = float(np.clip(wet, 0.0, 0.95))
    out = (1.0 - wet_clamped) * x + wet_clamped * diffused
    if not np.all(np.isfinite(out)):
        out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    return out


def _finalize_organ_note(signal: np.ndarray, sr: int = SAMPLE_RATE, fade_out_sec: float = 0.6) -> np.ndarray:
    """Applies DC removal, gentle tanh warmth, peak normalization (-1.5 dBFS), and clean tail fade."""
    y = _highpass_dc(signal, cutoff_hz=25.0, sr=sr)
    # Gentle warm soft-clip before normalization
    peak_pre = np.max(np.abs(y))
    if peak_pre > 1e-6:
        y = np.tanh((y / peak_pre) * 1.15)
    # Smooth tail fade-out over the last fade_out_sec
    fade_samples = min(int(fade_out_sec * sr), len(y) // 3)
    if fade_samples > 0:
        fade_t = np.linspace(0.0, 1.0, fade_samples)
        y[-fade_samples:] *= 0.5 * (1.0 + np.cos(np.pi * fade_t))
    # Tiny micro-attack guard against edge clicks
    micro = min(int(0.005 * sr), len(y) // 10)
    if micro > 0:
        y[:micro] *= np.linspace(0.0, 1.0, micro)

    peak = np.max(np.abs(y))
    if peak > 1e-6:
        y = (y / peak) * 0.84  # -1.5 dBFS
    return y.astype(np.float32)


def _raised_cosine_attack(n_samples: int, attack_sec: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    env = np.ones(n_samples, dtype=np.float64)
    att_n = min(int(attack_sec * sr), n_samples // 2)
    if att_n > 0:
        env[:att_n] = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0.0, 1.0, att_n)))
    return env


def synth_cathedral_note(freq: float, duration: float = 10.0, sr: int = SAMPLE_RATE, seed: int = 0) -> np.ndarray:
    """
    Multi-rank cathedral principal pipe organ:
      16' subbass, 8' principal + Voix Céleste detuned ranks (+1.8 / -1.5 cents),
      4' octave, 2 2/3' nazard, 2' fifteenth, rolled-off upper ranks, pipe chiff/wind, cathedral hall reverb.
    """
    rng = np.random.default_rng(seed)
    n_samples = int(duration * sr)
    t = np.linspace(0.0, duration, n_samples, endpoint=False)
    nyq_limit = 0.42 * sr

    sig = np.zeros(n_samples, dtype=np.float64)

    # 16' subbass (attenuated gently when sub < 28 Hz to keep sub clean)
    f_sub = freq * 0.5
    if 18.0 <= f_sub < nyq_limit:
        sub_att = min(1.0, max(0.22, (f_sub - 14.0) / 18.0)) * 0.42
        ph = rng.uniform(0.0, 2.0 * np.pi)
        sig += sub_att * np.sin(2.0 * np.pi * f_sub * t + ph)

    # 8' Principal + Voix Céleste twin sister pipes (0, +1.8 cents, -1.5 cents)
    celeste_ranks = [(0.0, 0.85), (1.8, 0.48), (-1.5, 0.44)]
    for cents, amp in celeste_ranks:
        f_r = freq * (2.0 ** (cents / 1200.0))
        if f_r < nyq_limit:
            ph = rng.uniform(0.0, 2.0 * np.pi)
            sig += amp * np.sin(2.0 * np.pi * f_r * t + ph)

    # Upper organ ranks: 4', 2 2/3', 2', and pitch-rolled-off partials (5x, 6x, 8x)
    pitch_rolloff = 1.0 / (1.0 + (freq / 650.0) ** 1.35)
    upper_ranks = [
        (2.0, 0.52),
        (3.0, 0.28),
        (4.0, 0.20),
        (5.0, 0.11 * pitch_rolloff),
        (6.0, 0.08 * pitch_rolloff),
        (8.0, 0.045 * pitch_rolloff),
    ]
    for mult, amp in upper_ranks:
        f_h = freq * mult
        if f_h < nyq_limit and amp > 1e-4:
            # Slight organic mistuning per pipe rank
            det = 2.0 ** (rng.uniform(-0.8, 0.8) / 1200.0)
            ph = rng.uniform(0.0, 2.0 * np.pi)
            sig += amp * np.sin(2.0 * np.pi * f_h * det * t + ph)

    # Subtle 0.18 Hz breathing tremulant
    trem = 1.0 + 0.032 * np.sin(2.0 * np.pi * 0.18 * t + rng.uniform(0.0, 2.0 * np.pi))
    sig *= trem

    # Velvety pipe speech attack (~0.28s)
    sig *= _raised_cosine_attack(n_samples, 0.28, sr=sr)

    # Pipe chiff & continuous subtle wind air bed (-40 dB)
    pink = _make_pink_noise(n_samples, rng)
    chiff_noise = _bandpass_noise(pink, max(180.0, freq * 1.4), min(4200.0, max(900.0, freq * 6.0)), sr=sr)
    chiff_env = 0.065 * np.exp(-t / 0.13) * np.minimum(1.0, t / 0.035)
    wind_env = 0.010 * _raised_cosine_attack(n_samples, 0.45, sr=sr)
    sig += chiff_noise * (chiff_env + wind_env)

    # Cathedral hall reverb
    wet_audio = apply_cathedral_reverb(sig, sr=sr, wet=0.40, rt60=3.5, damping=0.30)
    return _finalize_organ_note(wet_audio, sr=sr, fade_out_sec=0.6)


def synth_drone_note(freq: float, duration: float = 10.0, sr: int = SAMPLE_RATE, seed: int = 0) -> np.ndarray:
    """
    Deep dark ambient drone organ:
      Warm sub-octave + twin beating fundamental (+-2.0 cents) + slowly evolving fifth (1.5x, 3x)
      and octave (2x) modulated by independent slow out-of-phase LFOs (0.08-0.24 Hz).
    """
    rng = np.random.default_rng(seed)
    n_samples = int(duration * sr)
    t = np.linspace(0.0, duration, n_samples, endpoint=False)
    nyq_limit = 0.42 * sr

    sig = np.zeros(n_samples, dtype=np.float64)

    # Warm sub-octave (0.5x)
    f_sub = freq * 0.5
    if 16.0 <= f_sub < nyq_limit:
        sub_gain = 0.62 if f_sub >= 32.0 else 0.40
        lfo_sub = 0.85 + 0.15 * np.sin(2.0 * np.pi * 0.08 * t + rng.uniform(0.0, 2.0 * np.pi))
        sig += sub_gain * lfo_sub * np.sin(2.0 * np.pi * f_sub * t + rng.uniform(0.0, 2.0 * np.pi))

    # Twin beating fundamental (+2.0 / -2.0 cents + center core)
    for cents, amp in [(0.0, 0.72), (2.0, 0.52), (-2.0, 0.52)]:
        f_b = freq * (2.0 ** (cents / 1200.0))
        if f_b < nyq_limit:
            sig += amp * np.sin(2.0 * np.pi * f_b * t + rng.uniform(0.0, 2.0 * np.pi))

    # Slowly evolving harmonic layers (2x, 1.5x fifth, 3x twelfth, 4x)
    evolving = [
        (2.0, 0.36, 0.11, 0.30),
        (1.5, 0.24, 0.14, 0.45),
        (3.0, 0.14, 0.19, 0.55),
        (4.0, 0.10, 0.24, 0.60),
    ]
    for mult, amp, lfo_hz, depth in evolving:
        f_h = freq * mult
        if f_h < nyq_limit:
            ph_lfo = rng.uniform(0.0, 2.0 * np.pi)
            lfo = (1.0 - depth) + depth * (0.5 + 0.5 * np.sin(2.0 * np.pi * lfo_hz * t + ph_lfo))
            sig += amp * lfo * np.sin(2.0 * np.pi * f_h * t + rng.uniform(0.0, 2.0 * np.pi))

    # Pitch-adaptive warm lowpass (~900 to 2400 Hz)
    cutoff = float(np.clip(freq * 4.5 + 650.0, 900.0, 2400.0))
    sig = _lowpass_filter(sig, cutoff_hz=cutoff, sr=sr, order=2)

    # Velvety 0.55s swell attack
    sig *= _raised_cosine_attack(n_samples, 0.55, sr=sr)

    # Subtle warm air bed
    pink = _make_pink_noise(n_samples, rng)
    air = _bandpass_noise(pink, 140.0, min(1400.0, max(500.0, freq * 3.0)), sr=sr)
    sig += air * 0.008 * _raised_cosine_attack(n_samples, 0.65, sr=sr)

    # Lush dark cathedral reverb
    wet_audio = apply_cathedral_reverb(sig, sr=sr, wet=0.46, rt60=4.2, damping=0.38)
    return _finalize_organ_note(wet_audio, sr=sr, fade_out_sec=0.6)


def synth_glass_note(freq: float, duration: float = 10.0, sr: int = SAMPLE_RATE, seed: int = 0) -> np.ndarray:
    """
    Ethereal luminous glass-flute & shimmer organ:
      Hollow gedackt flute core (1x, 2x, 3x, 4x) + delayed-bloom crystalline shimmer overtones
      (2x, 3x, 4x, 6x swelling after 0.35s) + gentle slow rotary vibrato/chorus (0.42 Hz, +-3 cents).
    """
    rng = np.random.default_rng(seed)
    n_samples = int(duration * sr)
    t = np.linspace(0.0, duration, n_samples, endpoint=False)
    nyq_limit = 0.42 * sr

    # Gentle slow rotary vibrato/chorus (+-3 cents at 0.42 Hz)
    vib_cents = 3.0 * np.sin(2.0 * np.pi * 0.42 * t + rng.uniform(0.0, 2.0 * np.pi))
    vib_phase_mod = np.cumsum((2.0 ** (vib_cents / 1200.0) - 1.0) * (2.0 * np.pi * freq / sr))

    # Hollow gedackt flute core (odd-dominant + soft even harmonics)
    sig = np.zeros(n_samples, dtype=np.float64)
    core_ranks = [(1.0, 0.90), (2.0, 0.22), (3.0, 0.34), (4.0, 0.12)]
    for mult, amp in core_ranks:
        f_h = freq * mult
        if f_h < nyq_limit:
            ph = rng.uniform(0.0, 2.0 * np.pi)
            sig += amp * np.sin(2.0 * np.pi * f_h * t + mult * vib_phase_mod * 0.5 + ph)

    # Delayed-bloom crystalline shimmer overtones swelling in after 0.35s
    bloom_t = np.maximum(0.0, t - 0.35)
    bloom_env = np.where(t > 0.35, 1.0 - np.exp(-bloom_t / 1.1), 0.0)
    shimmer_ranks = [(2.0, 0.22), (3.0, 0.20), (4.0, 0.26), (6.0, 0.16)]
    for mult, amp in shimmer_ranks:
        f_s = freq * mult
        if f_s < nyq_limit:
            # Slight crystalline shimmer detune (+1.5 cents / -1.5 cents chorus pair)
            for det_cents in (-1.6, 1.8):
                f_det = f_s * (2.0 ** (det_cents / 1200.0))
                if f_det < nyq_limit:
                    ph = rng.uniform(0.0, 2.0 * np.pi)
                    sig += (amp * 0.5) * bloom_env * np.sin(2.0 * np.pi * f_det * t + mult * vib_phase_mod + ph)

    # Soft crystalline onset
    sig *= _raised_cosine_attack(n_samples, 0.24, sr=sr)

    # Airy flute breath transient
    pink = _make_pink_noise(n_samples, rng)
    breath = _bandpass_noise(pink, max(500.0, freq * 1.8), min(7500.0, max(2000.0, freq * 8.0)), sr=sr)
    sig += breath * (0.025 * np.exp(-t / 0.20) + 0.006) * _raised_cosine_attack(n_samples, 0.08, sr=sr)

    # Bright airy cathedral reverb
    wet_audio = apply_cathedral_reverb(sig, sr=sr, wet=0.45, rt60=3.8, damping=0.22)
    return _finalize_organ_note(wet_audio, sr=sr, fade_out_sec=0.6)


def synth_harmonium_fallback_note(freq: float, duration: float = 10.0, sr: int = SAMPLE_RATE, seed: int = 0) -> np.ndarray:
    """Warm reed harmonium synthesis used as fallback if organ-harmonium MP3s are unavailable."""
    rng = np.random.default_rng(seed)
    n_samples = int(duration * sr)
    t = np.linspace(0.0, duration, n_samples, endpoint=False)
    nyq_limit = 0.42 * sr

    sig = np.zeros(n_samples, dtype=np.float64)
    # Free-reed rich harmonic spectrum with gentle rolloff
    for h in range(1, 11):
        f_h = freq * h
        if f_h >= nyq_limit:
            break
        amp = (1.0 / (h ** 1.15)) * (1.15 if h % 2 == 1 else 0.85)
        sig += amp * np.sin(2.0 * np.pi * f_h * t + rng.uniform(0.0, 2.0 * np.pi))

    sig = _lowpass_filter(sig, cutoff_hz=min(3600.0, max(1200.0, freq * 6.5)), sr=sr, order=2)
    sig *= 1.0 + 0.04 * np.sin(2.0 * np.pi * 0.25 * t)
    sig *= _raised_cosine_attack(n_samples, 0.16, sr=sr)
    wet_audio = apply_cathedral_reverb(sig, sr=sr, wet=0.28, rt60=2.6, damping=0.32)
    return _finalize_organ_note(wet_audio, sr=sr, fade_out_sec=0.5)


def _should_generate(dest_path: str, force: bool = False) -> bool:
    if force:
        return True
    return not (os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000)


def generate_organ_cathedral(force: bool = False) -> str:
    dest_dir = os.path.join(SAMPLES_DIR, "organ-cathedral")
    os.makedirs(dest_dir, exist_ok=True)
    notes = [
        "C1", "E1", "Gs1",
        "C2", "E2", "Gs2",
        "C3", "E3", "Gs3",
        "C4", "E4", "Gs4",
        "C5", "E5", "Gs5",
        "C6"
    ]
    print(f"Generating organ-cathedral ({len(notes)} notes)...")
    for i, note in enumerate(notes):
        out_path = os.path.join(dest_dir, f"{note}.flac")
        if _should_generate(out_path, force=force):
            audio = synth_cathedral_note(note_to_freq(note), duration=10.0, seed=100 + i)
            sf.write(out_path, audio, SAMPLE_RATE, subtype='PCM_16')
    print(f"organ-cathedral ready in {dest_dir}")
    return dest_dir


def generate_organ_drone(force: bool = False) -> str:
    dest_dir = os.path.join(SAMPLES_DIR, "organ-drone")
    os.makedirs(dest_dir, exist_ok=True)
    notes = [
        "C1", "E1", "Gs1",
        "C2", "E2", "Gs2",
        "C3", "E3", "Gs3",
        "C4", "E4", "Gs4",
        "C5", "E5", "Gs5",
        "C6"
    ]
    print(f"Generating organ-drone ({len(notes)} notes)...")
    for i, note in enumerate(notes):
        out_path = os.path.join(dest_dir, f"{note}.flac")
        if _should_generate(out_path, force=force):
            audio = synth_drone_note(note_to_freq(note), duration=10.0, seed=200 + i)
            sf.write(out_path, audio, SAMPLE_RATE, subtype='PCM_16')
    print(f"organ-drone ready in {dest_dir}")
    return dest_dir


def generate_organ_glass(force: bool = False) -> str:
    dest_dir = os.path.join(SAMPLES_DIR, "organ-glass")
    os.makedirs(dest_dir, exist_ok=True)
    notes = [
        "C2", "E2", "Gs2",
        "C3", "E3", "Gs3",
        "C4", "E4", "Gs4",
        "C5", "E5", "Gs5",
        "C6", "E6", "Gs6",
        "C7", "E7", "Gs7",
        "C8"
    ]
    # Note: plan lists C2..C7 (16 notes) or 19 notes C2, E2, Gs2, ..., C7? Wait: let's check octaves 2..7!
    # C2..C7 every major third is C2,E2,Gs2, C3,E3,Gs3, C4,E4,Gs4, C5,E5,Gs5, C6,E6,Gs6, C7 (16) or with D/F#? Let's keep C2..C7!
    notes_c2_c7 = [
        "C2", "D2", "E2", "Gs2",
        "C3", "E3", "Gs3",
        "C4", "E4", "Gs4",
        "C5", "E5", "Gs5",
        "C6", "E6", "Gs6",
        "A6", "B6", "C7"
    ]
    print(f"Generating organ-glass ({len(notes_c2_c7)} notes)...")
    for i, note in enumerate(notes_c2_c7):
        out_path = os.path.join(dest_dir, f"{note}.flac")
        if _should_generate(out_path, force=force):
            audio = synth_glass_note(note_to_freq(note), duration=10.0, seed=300 + i)
            sf.write(out_path, audio, SAMPLE_RATE, subtype='PCM_16')
    print(f"organ-glass ready in {dest_dir}")
    return dest_dir


def setup_organ_paisaje_mix(force: bool = False) -> str:
    """
    Populates assets/samples/organ-paisaje-mix/ with 4 prefixed melodic organ layers:
      - drone_<note>.flac    (C1..C5)
      - catedral_<note>.flac (C2..C6)
      - cristal_<note>.flac  (C2..C6)
      - armonio_<note>.mp3/.flac (C2..C5 copied from organ-harmonium if available, else synthesized)
    """
    mix_dir = os.path.join(SAMPLES_DIR, "organ-paisaje-mix")
    os.makedirs(mix_dir, exist_ok=True)

    drone_dir = os.path.join(SAMPLES_DIR, "organ-drone")
    cat_dir = os.path.join(SAMPLES_DIR, "organ-cathedral")
    glass_dir = os.path.join(SAMPLES_DIR, "organ-glass")
    harm_dir = os.path.join(SAMPLES_DIR, "organ-harmonium")

    drone_notes = ["C1", "E1", "Gs1", "C2", "E2", "Gs2", "C3", "E3", "Gs3", "C4", "E4", "Gs4", "C5"]
    cat_notes = ["C2", "E2", "Gs2", "C3", "E3", "Gs3", "C4", "E4", "Gs4", "C5", "E5", "Gs5", "C6"]
    cristal_notes = ["C2", "E2", "Gs2", "C3", "E3", "Gs3", "C4", "E4", "Gs4", "C5", "E5", "Gs5", "C6"]
    armonio_notes = ["C2", "E2", "Gs2", "C3", "E3", "Gs3", "C4", "E4", "Gs4", "C5"]

    print("Populating organ-paisaje-mix (4-layer soundscape mix)...")

    for n in drone_notes:
        src = os.path.join(drone_dir, f"{n}.flac")
        dst = os.path.join(mix_dir, f"drone_{n}.flac")
        if _should_generate(dst, force=force) and os.path.exists(src):
            shutil.copy2(src, dst)

    for n in cat_notes:
        src = os.path.join(cat_dir, f"{n}.flac")
        dst = os.path.join(mix_dir, f"catedral_{n}.flac")
        if _should_generate(dst, force=force) and os.path.exists(src):
            shutil.copy2(src, dst)

    for n in cristal_notes:
        src = os.path.join(glass_dir, f"{n}.flac")
        dst = os.path.join(mix_dir, f"cristal_{n}.flac")
        if _should_generate(dst, force=force) and os.path.exists(src):
            shutil.copy2(src, dst)

    for i, n in enumerate(armonio_notes):
        src_mp3 = os.path.join(harm_dir, f"{n}.mp3")
        dst_mp3 = os.path.join(mix_dir, f"armonio_{n}.mp3")
        dst_flac = os.path.join(mix_dir, f"armonio_{n}.flac")
        if os.path.exists(src_mp3) and os.path.getsize(src_mp3) > 1000:
            if _should_generate(dst_mp3, force=force):
                shutil.copy2(src_mp3, dst_mp3)
            if os.path.exists(dst_flac):
                try:
                    os.remove(dst_flac)
                except OSError:
                    pass
        else:
            if _should_generate(dst_flac, force=force):
                audio = synth_harmonium_fallback_note(note_to_freq(n), duration=8.0, seed=400 + i)
                sf.write(dst_flac, audio, SAMPLE_RATE, subtype='PCM_16')

    print(f"organ-paisaje-mix ready in {mix_dir}")
    return mix_dir


def generate_all(force: bool = False):
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    generate_organ_cathedral(force=force)
    generate_organ_drone(force=force)
    generate_organ_glass(force=force)
    setup_organ_paisaje_mix(force=force)
    print("All synthesized organ soundscape banks generated!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate studio organ soundscape sample banks.")
    parser.add_argument("--force", action="store_true", help="Regenerate files even if they already exist.")
    args = parser.parse_args()
    generate_all(force=args.force)
