"""
Pendulum Engine - Physical and Musical Polyphony Simulation
Supports dynamic Root Key (Tonalidad), Base Octave, Harmony Types (Escalas y Modos)
and Tempo-linked physics.
"""

import math
from typing import List, Dict, Any
from harmony import (
    NOTE_NAMES, HARMONIC_TYPES, TIME_SIGNATURES, NOTE_DURATIONS, DYNAMIC_MODES,
    STRIKE_PATTERNS, HARMONIC_FILL_PALETTES, build_scale_notes, midi_to_note_and_octave,
    compute_note_duration, compute_tied_note_duration, compute_dynamic_velocity,
    compute_strike_pitch, resolve_strike_steps, compute_strum_delays,
    compute_strum_velocity, expand_chord_to_n_voices, is_scale_run_palette
)
from rhythm_patterns import (
    compute_pattern_slot_delays, compute_step_tie_span,
    is_hit, count_hits, has_ties
)

# Backward compatibility presets and scale registry
SCALES = {
    'romanza': {'name': 'Romanza (E min)', 'root': 'E', 'octave': 2, 'harmony': 'minor_harmonic'},
    'malaguena': {'name': 'Malagueña (A min)', 'root': 'A', 'octave': 2, 'harmony': 'minor_harmonic'},
    'guitar_dmin': {'name': 'Ballad (D min7)', 'root': 'D', 'octave': 2, 'harmony': 'chord_min9'},
    'c_major': {'name': 'C Major (Pure)', 'root': 'C', 'octave': 3, 'harmony': 'major'},
    'chimes_penta': {'name': 'Zen Chimes (G Penta)', 'root': 'G', 'octave': 3, 'harmony': 'penta_zen'},
    'hirojoshi': {'name': 'Hirojoshi (Zen)', 'root': 'C', 'octave': 3, 'harmony': 'hirojoshi'},
    'techno_phrygian': {'name': 'Acid Pulse (Phrygian)', 'root': 'C', 'octave': 2, 'harmony': 'phrygian'},
    'monotone': {'name': 'Monotone Drone', 'root': 'C', 'octave': 3, 'harmony': 'sus4_ambient'}
}
PRESET_MAP = SCALES

PENDULUM_COLORS = [
    '#00f5d4', '#2ec4b6', '#3a86ff', '#8338ec',
    '#f72585', '#ff006e', '#fb5607', '#ff9f1c',
    '#ffd166', '#06d6a0', '#00b4d8', '#9b5de5'
]

def midi_to_note_name(midi_pitch: int) -> str:
    return midi_to_note_and_octave(midi_pitch)

class StrikeEvent:
    def __init__(
        self,
        time: float,
        pendulum_index: int,
        pitch: int,
        velocity: int,
        duration: float,
        pan: float,
        timbre: str = None,
        decay: float = None,
    ):
        self.time = time
        self.pendulum_index = pendulum_index
        self.pitch = pitch
        self.velocity = velocity
        self.duration = duration
        self.pan = pan  # -1.0 (left) to +1.0 (right)
        self.timbre = timbre
        self.decay = decay

    def __repr__(self):
        return f"<Strike t={self.time:.3f}s p={self.pendulum_index} pitch={self.pitch} ({midi_to_note_name(self.pitch)}) vel={self.velocity}>"


class Pendulum:
    def __init__(self, index: int, total_pendulums: int, frequency: float, base_pitch: int):
        self.index = index
        self.frequency = max(0.05, frequency)
        self.period = 1.0 / self.frequency
        self.half_period = self.period / 2.0
        self.base_pitch = base_pitch
        self.color = PENDULUM_COLORS[index % len(PENDULUM_COLORS)]
        self.pan = -0.8 + (1.6 * index / max(1, total_pendulums - 1)) if total_pendulums > 1 else 0.0

    def angle_at(self, t: float, amplitude: float = 0.4) -> float:
        return amplitude * math.cos(2.0 * math.pi * self.frequency * t)

    def speed_at(self, t: float, amplitude: float = 0.4) -> float:
        return -amplitude * 2.0 * math.pi * self.frequency * math.sin(2.0 * math.pi * self.frequency * t)


class PendulumSystem:
    def __init__(
        self,
        root_key: str = 'E',
        base_octave: int = 2,
        harmony_type: str = 'minor_harmonic',
        n_pendulums: int = 2,
        rhythm_mode: str = 'sync',
        strike_mode: str = 'bilateral',
        strike_pattern: str = '1+1',
        fill_palette: str = 'chord_arpeggio',
        tempo_bpm: float = 96.0,
        voicing: str = 'linear',
        time_signature: str = '4/4',
        note_duration_mode: str = 'auto',
        dynamic_mode: str = 'accent_bar',
        scale_key: str = None  # for legacy preset compatibility
    ):
        # Resolve legacy preset if provided
        if scale_key and scale_key in PRESET_MAP:
            p_data = PRESET_MAP[scale_key]
            self.root_key = p_data['root']
            self.base_octave = p_data['octave']
            self.harmony_type = p_data['harmony']
        else:
            self.root_key = root_key if root_key in NOTE_NAMES else 'E'
            self.base_octave = max(1, min(6, base_octave))
            self.harmony_type = harmony_type if harmony_type in HARMONIC_TYPES else 'minor_harmonic'

        self.n_pendulums = max(1, min(32, n_pendulums))
        self.rhythm_mode = rhythm_mode
        self.strike_mode = strike_mode
        self.strike_pattern = strike_pattern if strike_pattern in STRIKE_PATTERNS else '1+1'
        self.fill_palette = fill_palette if fill_palette in HARMONIC_FILL_PALETTES else 'chord_arpeggio'
        self.tempo_bpm = max(0.01, float(tempo_bpm))
        self.voicing = voicing
        self.time_signature = time_signature if time_signature in TIME_SIGNATURES else '4/4'
        self.note_duration_mode = note_duration_mode if note_duration_mode in NOTE_DURATIONS else 'auto'
        self.dynamic_mode = dynamic_mode if dynamic_mode in DYNAMIC_MODES else 'accent_bar'

        self.custom_ball_strikes: Dict[int, tuple] = {}
        self.custom_ball_dynamics: Dict[int, str] = {}
        self.custom_ball_durations: Dict[int, str] = {}
        self.custom_ball_palettes: Dict[int, str] = {}
        self.strum_progression_ratio: float = 1.0
        self.strum_accent_sensitivity: float = 0.50
        self.custom_ball_strum_ratio: Dict[int, float] = {}
        self.custom_ball_strum_sens: Dict[int, float] = {}
        self.chord_play_mode: str = 'off'
        self.chord_pitches: List[int] = []

        self._init_harmony_and_pendulums()

    def set_dynamic_mode(self, mode: str):
        """Sets strike dynamic velocity profile according to the beat of the compás."""
        if mode in DYNAMIC_MODES:
            self.dynamic_mode = mode

    def set_note_duration(self, mode: str):
        """Sets articulation / note duration mode ('auto', 'staccato', 'short', 'normal', 'tenuto', 'legato', 'drone')."""
        if mode in NOTE_DURATIONS:
            self.note_duration_mode = mode

    def get_current_note_duration(self, pendulum_index: int = 0) -> float:
        """Returns the active note duration in seconds for a specific pendulum."""
        half_p = 1.0
        if 0 <= pendulum_index < len(self.pendulums):
            half_p = self.pendulums[pendulum_index].half_period
        return compute_note_duration(self.note_duration_mode, half_period=half_p)

    def set_time_signature(self, time_signature: str):
        """Sets the time signature (e.g. '2/4', '3/4', '4/4', '6/8') and recalculates bar subdivisions."""
        if time_signature in TIME_SIGNATURES:
            self.time_signature = time_signature
            self._init_harmony_and_pendulums()

    def set_root(self, root_key: str, base_octave: int = None):
        """Changes the root key and octave in real-time and recalculates all pitches."""
        if root_key in NOTE_NAMES:
            self.root_key = root_key
        if base_octave is not None:
            self.base_octave = max(1, min(6, base_octave))
        self._init_harmony_and_pendulums()

    def set_root_pitch_inplace(self, root_key: str, base_octave: int) -> List[int]:
        """Updates root key, octave, scale_notes, and pendulum base_pitches in place without altering rhythm/phase."""
        if root_key in NOTE_NAMES:
            self.root_key = root_key
        self.base_octave = max(1, min(6, int(base_octave)))
        self.scale_notes = build_scale_notes(
            root_key=self.root_key,
            base_octave=self.base_octave,
            harmony_type=self.harmony_type,
            n_pendulums=self.n_pendulums,
            voicing=self.voicing,
        )
        for i, p in enumerate(self.pendulums):
            if i < len(self.scale_notes):
                p.base_pitch = self.scale_notes[i]
        return self.scale_notes

    def set_chord_pitches_inplace(
        self,
        root_key: str,
        base_octave: int,
        chord_pitches: List[int],
    ) -> List[int]:
        """Updates root, scale_notes, and pendulum base_pitches to the active chord in place."""
        if root_key in NOTE_NAMES:
            self.root_key = root_key
        self.base_octave = max(1, min(6, int(base_octave)))
        self.scale_notes = build_scale_notes(
            root_key=self.root_key,
            base_octave=self.base_octave,
            harmony_type=self.harmony_type,
            n_pendulums=self.n_pendulums,
            voicing=self.voicing,
        )
        self.chord_pitches = list(chord_pitches) if chord_pitches else []
        for i, p in enumerate(self.pendulums):
            if self.chord_pitches and self.harmony_type != 'drum_kit':
                base_c = self.chord_pitches[i % len(self.chord_pitches)]
                oct_add = (i // len(self.chord_pitches)) * 12
                p.base_pitch = min(108, max(21, base_c + oct_add))
            elif i < len(self.scale_notes):
                p.base_pitch = self.scale_notes[i]
        return [p.base_pitch for p in self.pendulums]

    def set_harmony_type(self, harmony_type: str):
        """Changes musical scale or chord type (e.g. Major, Minor, Dorian, Zen Chimes...)."""
        if harmony_type in HARMONIC_TYPES:
            self.harmony_type = harmony_type
            self._init_harmony_and_pendulums()

    def set_tempo(self, bpm: float):
        """Updates tempo and accelerates or decelerates physical pendulum oscillation."""
        self.tempo_bpm = max(0.01, float(bpm))
        self._init_harmony_and_pendulums()

    def _init_harmony_and_pendulums(self):
        # 1. Build musical scale notes based on root key and harmony type
        self.scale_notes = build_scale_notes(
            root_key=self.root_key,
            base_octave=self.base_octave,
            harmony_type=self.harmony_type,
            n_pendulums=self.n_pendulums,
            voicing=self.voicing
        )

        # 2. Calculate physical frequencies linked to BPM, Time Signature and rhythm mode
        self.pendulums: List[Pendulum] = []
        beat_sec = 60.0 / self.tempo_bpm
        bps = self.tempo_bpm / 60.0

        sig_data = TIME_SIGNATURES.get(self.time_signature, TIME_SIGNATURES['4/4'])
        beats_per_bar = sig_data['beats_per_bar']
        self.bar_duration_sec = beats_per_bar * beat_sec

        if self.rhythm_mode == 'sync':
            # Subdivisions customized for the specific Time Signature (2/4, 3/4, 4/4, 6/8, etc.)
            intervals = sig_data['subdivisions']
            for i in range(self.n_pendulums):
                interval = intervals[min(i, len(intervals) - 1)]
                if i >= len(intervals):
                    interval = intervals[-1] / (2.0 ** (i - len(intervals) + 1))
                strike_freq = bps / interval
                f_i = strike_freq / 2.0
                pitch = self.scale_notes[i]
                self.pendulums.append(Pendulum(i, self.n_pendulums, f_i, pitch))
        elif self.rhythm_mode == 'gaps':
            # Espaciado amplio / Huecos y respiros: silencios extendidos entre golpes
            base_bars = beats_per_bar * 2.0
            gap_intervals = [base_bars * 2.0, base_bars, base_bars / 2.0, base_bars / 4.0]
            for i in range(self.n_pendulums):
                interval = gap_intervals[i % len(gap_intervals)]
                strike_freq = bps / interval
                f_i = strike_freq / 2.0
                pitch = self.scale_notes[i]
                self.pendulums.append(Pendulum(i, self.n_pendulums, f_i, pitch))
        elif self.rhythm_mode == 'beat_pulse':
            # Pulso continuo sin silencios: golpe exacto en cada beat y subdivisiones
            beat_intervals = [1.0, 0.5, 0.25, 1.0, 0.5]
            for i in range(self.n_pendulums):
                interval = beat_intervals[i % len(beat_intervals)]
                strike_freq = bps / interval
                f_i = strike_freq / 2.0
                pitch = self.scale_notes[i]
                self.pendulums.append(Pendulum(i, self.n_pendulums, f_i, pitch))
        else:
            # Wave mode: harmonic wave cycle locked to an integer number of bars
            cycle_bars = sig_data.get('cycle_bars', 4)
            cycle_beats = cycle_bars * beats_per_bar
            cycle_sec = cycle_beats * beat_sec
            base_oscillations = max(6, int(cycle_bars * beats_per_bar * 0.75))
            for i in range(self.n_pendulums):
                f_i = (base_oscillations + i) / cycle_sec
                pitch = self.scale_notes[i]
                self.pendulums.append(Pendulum(i, self.n_pendulums, f_i, pitch))

    def generate_strikes(self, duration: float) -> List[StrikeEvent]:
        events: List[StrikeEvent] = []
        pool = self.scale_notes

        for p in self.pendulums:
            t_cross = p.period / 4.0
            strike_count = 0
            ball_cum_strikes = 0

            while t_cross < duration:
                moving_right = (strike_count % 2 == 1)

                # Determine strike steps for both sides (1..8 steps with hits, rests, and ties)
                if p.index in self.custom_ball_strikes:
                    pat_tuple = self.custom_ball_strikes[p.index]
                    left_conf, right_conf = pat_tuple[0], pat_tuple[1]
                else:
                    pat_data = STRIKE_PATTERNS.get(self.strike_pattern, {'ida': 1, 'vuelta': 1, 'izq': 1, 'der': 1})
                    left_conf = pat_data.get('izq', pat_data.get('ida', 1))
                    right_conf = pat_data.get('der', pat_data.get('vuelta', 1))

                left_steps = resolve_strike_steps(left_conf)
                right_steps = resolve_strike_steps(right_conf)
                active_steps = right_steps if moving_right else left_steps
                next_steps = left_steps if moving_right else right_steps
                n_steps = len(active_steps)
                n_active = count_hits(active_steps)

                if n_active > 0:
                    ratio = self.custom_ball_strum_ratio.get(p.index, self.strum_progression_ratio)
                    sens = self.custom_ball_strum_sens.get(p.index, self.strum_accent_sensitivity)

                    voice_norm = p.index / max(1, self.n_pendulums - 1) if self.n_pendulums > 1 else 0.5
                    base_vel = 85 + int(25 * (1.0 - voice_norm * 0.3))
                    beat_sec = 60.0 / self.tempo_bpm
                    sig_data = TIME_SIGNATURES.get(self.time_signature, TIME_SIGNATURES['4/4'])
                    beats_per_bar = int(sig_data['numerator'])
                    dyn_mode = self.custom_ball_dynamics.get(p.index, self.dynamic_mode)
                    dur_mode = self.custom_ball_durations.get(p.index, self.note_duration_mode)
                    duration_note = compute_note_duration(dur_mode, half_period=p.half_period)
                    pal_mode = self.custom_ball_palettes.get(p.index, self.fill_palette)

                    if (
                        self.chord_play_mode in ('block', 'strum')
                        and bool(self.chord_pitches)
                        and self.harmony_type != 'drum_kit'
                    ):
                        active_indices = [k for k, st in enumerate(active_steps) if is_hit(st)]
                        chord_pool = expand_chord_to_n_voices(
                            self.chord_pitches, n_steps, inversion=p.index
                        )
                        c_notes = [chord_pool[k] for k in active_indices]
                        n_v = len(c_notes)
                        beat_in_bar = int((t_cross / beat_sec) % beats_per_bar)
                        velocity = compute_dynamic_velocity(dyn_mode, beat_in_bar, beats_per_bar, base_vel)
                        vel_scale = max(0.68, 0.90 - 0.04 * max(0, n_v - 2)) if n_v >= 2 else 1.0

                        if self.chord_play_mode == 'strum' and n_v >= 2:
                            if not moving_right:
                                c_notes.reverse()
                            strum_span = min(0.18, p.half_period * 0.70, max(0.035, 0.030 * (n_v - 1)))
                            voice_offsets = compute_strum_delays(n_v, strum_span, ratio)
                            apply_strum_vel = True
                        else:
                            voice_offsets = [0.0] * n_v
                            apply_strum_vel = False

                        for v_idx, (c_pt, v_off) in enumerate(zip(c_notes, voice_offsets)):
                            ev_t = t_cross + v_off
                            if ev_t >= duration:
                                continue
                            c_vel = max(25, min(127, int(velocity * vel_scale)))
                            if apply_strum_vel:
                                c_vel = compute_strum_velocity(c_vel, v_idx, n_v, sens)
                            events.append(StrikeEvent(
                                time=ev_t,
                                pendulum_index=p.index,
                                pitch=c_pt,
                                velocity=c_vel,
                                duration=duration_note,
                                pan=p.pan
                            ))
                        ball_cum_strikes += n_v
                    else:
                        slot_delays = compute_pattern_slot_delays(
                            n_steps, p.half_period, ratio=ratio, speed_factor=1.0
                        )
                        has_any_tie = has_ties(left_steps) or has_ties(right_steps)
                        next_delays = (
                            compute_pattern_slot_delays(
                                len(next_steps), p.half_period, ratio=ratio, speed_factor=1.0
                            )
                            if has_any_tie
                            else []
                        )
                        active_count_idx = 0
                        for k_sub, step_val in enumerate(active_steps):
                            if not is_hit(step_val):
                                continue
                            t_slot = t_cross + slot_delays[k_sub]
                            if t_slot >= duration:
                                break
                            beat_in_bar = int((t_slot / beat_sec) % beats_per_bar)
                            sub_base_vel = compute_strum_velocity(base_vel, active_count_idx, n_active, sens)
                            velocity = compute_dynamic_velocity(dyn_mode, beat_in_bar, beats_per_bar, sub_base_vel)
                            active_count_idx += 1

                            if has_any_tie:
                                tie_count, slot_span, tied_span = compute_step_tie_span(
                                    active_steps, next_steps, k_sub, p.half_period, slot_delays, next_delays
                                )
                                step_dur = compute_tied_note_duration(
                                    dur_mode, duration_note, True, tie_count, slot_span, tied_span
                                )
                            else:
                                step_dur = duration_note

                            if is_scale_run_palette(pal_mode):
                                pitch = p.base_pitch
                            elif self.strike_mode == 'bilateral':
                                pitch = p.base_pitch if moving_right else min(108, p.base_pitch + (7 if p.index % 2 == 0 else 12))
                            elif self.strike_mode == 'unison':
                                pitch = p.base_pitch
                            elif self.strike_mode == 'stepArp':
                                pitch = pool[(p.index + strike_count + k_sub) % len(pool)]
                            elif self.strike_mode == 'octaveAlt':
                                pitch = p.base_pitch if moving_right else min(108, p.base_pitch + 12)
                            else:
                                pitch = p.base_pitch

                            actual_pitch = compute_strike_pitch(
                                base_pitch=pitch,
                                strike_idx=k_sub,
                                palette_key=pal_mode,
                                scale_notes=pool,
                                strike_counter=ball_cum_strikes,
                                harmony_type=self.harmony_type
                            )
                            ball_cum_strikes += 1

                            if actual_pitch is not None:
                                events.append(StrikeEvent(
                                    time=t_slot,
                                    pendulum_index=p.index,
                                    pitch=actual_pitch,
                                    velocity=velocity,
                                    duration=step_dur,
                                    pan=p.pan
                                ))

                strike_count += 1
                t_cross += p.half_period

        events.sort(key=lambda e: e.time)
        return events
