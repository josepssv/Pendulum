"""
Harmonic Foundation & Scale Builder for Pendulum Polyphony
Generates musical scales, chords and voicings from any Root Key and Octave.
"""

from typing import List, Dict, Any, Optional, Tuple
import random
from rhythm_patterns import (
    STEP_HIT,
    STEP_REST,
    count_hits,
    normalize_pattern,
    euclidean_pattern,
    generate_random_pattern_side,
    DEFAULT_PATTERN_STEPS,
)

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Musical intervals in semitones relative to root (0)
HARMONIC_TYPES: Dict[str, Dict[str, Any]] = {
    'minor_harmonic': {
        'name': 'Harmonic Minor (Española / Romanza)',
        'intervals': [0, 2, 3, 5, 7, 8, 11],
        'description': 'Classical Spanish & dramatic tension'
    },
    'minor_natural': {
        'name': 'Natural Minor (Eólica)',
        'intervals': [0, 2, 3, 5, 7, 8, 10],
        'description': 'Melancholic, intimate & deep'
    },
    'major': {
        'name': 'Major (Jónica Pura)',
        'intervals': [0, 2, 4, 5, 7, 9, 11],
        'description': 'Bright, uplifting & pure'
    },
    'dorian': {
        'name': 'Dorian (Mística / Jazz)',
        'intervals': [0, 2, 3, 5, 7, 9, 10],
        'description': 'Medieval modal & groovy jazz flavor'
    },
    'phrygian': {
        'name': 'Phrygian (Flamenca / Acid)',
        'intervals': [0, 1, 3, 5, 7, 8, 10],
        'description': 'Dark, exotic with minor 2nd flavor'
    },
    'lydian': {
        'name': 'Lydian (Etérea / Cine)',
        'intervals': [0, 2, 4, 6, 7, 9, 11],
        'description': 'Dreamy, ethereal film score sound'
    },
    'mixolydian': {
        'name': 'Mixolydian (Blues / Folk)',
        'intervals': [0, 2, 4, 5, 7, 9, 10],
        'description': 'Rock, Celtic & dominant warmth'
    },
    'penta_zen': {
        'name': 'Zen Pentatonic (Campanas)',
        'intervals': [0, 2, 4, 7, 9],
        'description': 'Harmonious, never dissonant chime bells'
    },
    'penta_minor': {
        'name': 'Minor Pentatonic (Blues / Soul)',
        'intervals': [0, 3, 5, 7, 10],
        'description': 'Bluesy & expressive'
    },
    'hirojoshi': {
        'name': 'Hirojoshi (Zen Tradicional)',
        'intervals': [0, 2, 3, 7, 8],
        'description': 'Traditional Japanese meditative pentatonic'
    },
    'chord_min9': {
        'name': 'Balada Arpegio (m9 / Ballad)',
        'intervals': [0, 3, 7, 10, 14],  # Root, b3, 5, b7, 9
        'description': 'Deep acoustic ballad arpeggio'
    },
    'chord_maj9': {
        'name': 'Celestial Arpegio (Maj9)',
        'intervals': [0, 4, 7, 11, 14],  # Root, 3, 5, 7, 9
        'description': 'Airy, rich open chord voicing'
    },
    'sus4_ambient': {
        'name': 'Ambient Sus4 Drone',
        'intervals': [0, 5, 7, 12, 17],  # Root, 4th, 5th, octave, 11th
        'description': 'Spacious, open drone without 3rd dissonance'
    },
    'monotone': {
        'name': 'Monotone (Misma Nota / Pulso Puro)',
        'intervals': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        'description': 'Single-note cadence, ideal for percussion metronome'
    },
    'drum_kit': {
        'name': 'Percussion Kit (Kick, Snare, Hats, Toms)',
        'intervals': [0, 2, 6, 8, 5, 9, 12, 14, 20, 39],
        'description': 'Standard GM Drum kit mapping: Kick (36), Snare (38), Hats (42), Toms (41,45), Claves (75)'
    }
}

def note_name_to_midi(note_name: str, octave: int) -> int:
    """Converts root name (e.g. 'C#', 'E') and octave (e.g. 2, 3) to MIDI pitch number."""
    clean_name = note_name.strip().upper()
    if clean_name not in NOTE_NAMES:
        clean_name = 'C'
    root_idx = NOTE_NAMES.index(clean_name)
    # MIDI formula: C-1 is 0, C0 is 12, C1 is 24, C2 is 36, C3 is 48, C4 is 60 (Middle C)
    return (octave + 1) * 12 + root_idx

def midi_to_note_and_octave(midi_pitch: int) -> str:
    """Returns human-readable name like 'E2' or 'F#3'."""
    octave = (midi_pitch // 12) - 1
    name = NOTE_NAMES[midi_pitch % 12]
    return f"{name}{octave}"

def build_scale_notes(
    root_key: str = 'E',
    base_octave: int = 2,
    harmony_type: str = 'minor_harmonic',
    n_pendulums: int = 10,
    voicing: str = 'linear'
) -> List[int]:
    """
    Constructs a musically coherent list of MIDI pitches for n_pendulums based on:
    - root_key: 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'
    - base_octave: usually 2 or 3 for rich bass foundation
    - harmony_type: key in HARMONIC_TYPES
    - voicing: 'linear' (scales up stepwise), 'open' (skips for wide spacious chords)
    """
    root_pitch = note_name_to_midi(root_key, base_octave)

    if harmony_type == 'monotone':
        # Pure monotone: Every single pendulum plays the exact same pitch/drum
        return [root_pitch] * n_pendulums

    if harmony_type == 'drum_kit':
        # Map to standard GM percussion root C2 (MIDI 36 = Kick)
        base_drum_root = 36
        harm_def = HARMONIC_TYPES['drum_kit']
        intervals = harm_def['intervals']
        return [intervals[i % len(intervals)] + base_drum_root for i in range(n_pendulums)]

    harm_def = HARMONIC_TYPES.get(harmony_type, HARMONIC_TYPES['minor_harmonic'])
    intervals = harm_def['intervals']

    pitches: List[int] = []

    if voicing == 'open':
        # Open voicing: Root in bass, 5th, 10th (octave 3rd), etc.
        # Alternates scale degrees to create airy acoustic piano/harp voicings
        for i in range(n_pendulums):
            oct_add = (i // len(intervals)) * 12
            # Stride through intervals by steps of 2 (1st, 3rd, 5th, 7th...)
            interval_idx = (i * 2) % len(intervals)
            raw_interval = intervals[interval_idx] + oct_add + ((i * 2) // len(intervals)) * 12
            p = min(108, root_pitch + raw_interval)
            pitches.append(p)
    else:
        # Linear voicing: Sequential degrees ascending smoothly
        for i in range(n_pendulums):
            oct_add = (i // len(intervals)) * 12
            interval = intervals[i % len(intervals)]
            p = min(108, root_pitch + interval + oct_add)
            pitches.append(p)

    return pitches

# Musical Time Signatures (Compases)
TIME_SIGNATURES: Dict[str, Dict[str, Any]] = {
    '4/4': {
        'name': '4/4 (Estándar / Cuaternario)',
        'numerator': 4,
        'denominator': 4,
        'beats_per_bar': 4.0,
        # Musical subdivisions in beats for locked pendulum polyphony
        'subdivisions': [8.0, 4.0, 2.0, 1.333, 1.0, 0.667, 0.5, 0.333, 0.25, 0.125],
        'cycle_bars': 4  # 4 bars = 16 beats cycle
    },
    '3/4': {
        'name': '3/4 (Vals / Ternario)',
        'numerator': 3,
        'denominator': 4,
        'beats_per_bar': 3.0,
        # 2 bars (6), 1 bar (3), hemiolia 2 vs 3 (1.5), quarter (1.0), 8th (0.5), triplet (0.333), 16th (0.25)
        'subdivisions': [6.0, 3.0, 1.5, 1.0, 0.75, 0.5, 0.333, 0.25, 0.125],
        'cycle_bars': 4  # 4 bars = 12 beats cycle
    },
    '2/4': {
        'name': '2/4 (Marcha / Binario Rápido)',
        'numerator': 2,
        'denominator': 4,
        'beats_per_bar': 2.0,
        # 2 bars (4), 1 bar (2), 1 beat (1.0), triplet (0.667), 8th (0.5), 16th (0.25)
        'subdivisions': [4.0, 2.0, 1.0, 0.667, 0.5, 0.333, 0.25, 0.125],
        'cycle_bars': 4  # 4 bars = 8 beats cycle
    },
    '6/8': {
        'name': '6/8 (Compuesto / Balanceo)',
        'numerator': 6,
        'denominator': 8,
        'beats_per_bar': 3.0,  # 6 eighths = 3 quarter beats
        # Compound pulse: dotted quarter (1.5), hemiolia (1.0), eighth (0.5), 16th (0.25)
        'subdivisions': [6.0, 3.0, 1.5, 1.0, 0.5, 0.375, 0.25, 0.125],
        'cycle_bars': 4  # 4 bars = 12 beats cycle
    },
    '5/4': {
        'name': '5/4 (Amalgama / 3+2)',
        'numerator': 5,
        'denominator': 4,
        'beats_per_bar': 5.0,
        'subdivisions': [5.0, 2.5, 1.667, 1.0, 0.5, 0.25],
        'cycle_bars': 4  # 4 bars = 20 beats cycle
    }
}

# Musical Note Durations & Articulations
NOTE_DURATIONS: Dict[str, Dict[str, Any]] = {
    'auto': {
        'name': 'Auto (Dinámico)',
        'sec': None,
        'factor': 0.85,
        'desc': 'Proporcional al periodo del péndulo'
    },
    'staccato': {
        'name': 'Staccato (0.2s)',
        'sec': 0.18,
        'factor': 0.25,
        'desc': 'Puntos secos, picados y cortados'
    },
    'short': {
        'name': 'Corto (0.5s)',
        'sec': 0.45,
        'factor': 0.50,
        'desc': 'Articulación ágil y rítmica'
    },
    'normal': {
        'name': 'Normal (0.9s)',
        'sec': 0.90,
        'factor': 0.85,
        'desc': 'Cuerpo acústico natural estándar'
    },
    'tenuto': {
        'name': 'Tenuto (1.8s)',
        'sec': 1.80,
        'factor': 1.60,
        'desc': 'Notas apoyadas y sostenidas'
    },
    'legato': {
        'name': 'Legato (3.2s)',
        'sec': 3.20,
        'factor': 2.50,
        'desc': 'Resonancia extendida que enlaza frases'
    },
    'drone': {
        'name': 'Drone (5.0s)',
        'sec': 5.00,
        'factor': 4.00,
        'desc': 'Sustain envolvente e infinito'
    },
    'paisaje': {
        'name': 'Paisaje (8.0s)',
        'sec': 8.00,
        'factor': 6.00,
        'desc': 'Manto sonoro largo ideal para paisajes de órgano'
    }
}

def compute_note_duration(mode: str, half_period: float = 1.0, custom_sec: float = None) -> float:
    """
    Calculates effective note duration in seconds based on articulation mode or pendulum period.
    """
    if custom_sec is not None and custom_sec > 0:
        return max(0.05, min(10.0, custom_sec))

    info = NOTE_DURATIONS.get(mode, NOTE_DURATIONS['auto'])
    if info.get('sec') is not None:
        return float(info['sec'])

    factor = info.get('factor', 0.85)
    return max(0.10, min(8.0, half_period * factor))


def compute_tied_note_duration(
    dur_mode: str,
    base_dur: float,
    has_any_tie: bool,
    tie_count: int,
    slot_span_sec: float,
    tied_span_sec: float,
) -> float:
    """
    Adjusts effective note duration in seconds when a step pattern includes ties ('~').
    Keeps base_dur unchanged when no ties exist in the pendulum's pattern.
    """
    if not has_any_tie:
        return base_dur
    if dur_mode == 'auto':
        if tie_count > 0:
            return max(0.10, min(10.0, tied_span_sec * 0.94))
        return max(0.08, min(8.0, slot_span_sec * 0.88))
    if tie_count > 0:
        extra_span = max(0.0, tied_span_sec - slot_span_sec)
        return max(0.10, min(10.0, max(tied_span_sec * 0.94, base_dur + extra_span)))
    return base_dur

# Musical Dynamic Profiles (Dinámica del golpe según el beat del compás)
DYNAMIC_MODES: Dict[str, Dict[str, Any]] = {
    'accent_bar': {
        'name': 'Acento 1 (Fuerte en 1, Delicado resto)',
        'short': 'Acento 1',
        'desc': 'Downbeat fuerte y expresivo (127), beats secundarios delicados (34)'
    },
    'marcato': {
        'name': 'Marcato Extremo (ff en 1, pp resto)',
        'short': 'Marcato',
        'desc': 'Acento máximo (127) en pulso 1 y susurro (32) en el resto'
    },
    'forte': {
        'name': 'Forte (Impacto Máximo ff)',
        'short': 'Forte',
        'desc': 'Golpes con fuerza y presencia máxima (126) en todo el compás'
    },
    'delicado': {
        'name': 'Suave (Pianissimo pp)',
        'short': 'Suave',
        'desc': 'Golpes suaves, etéreos y delicados (32) en todo el compás'
    },
    'crescendo': {
        'name': 'Crescendo (Delicado a Fuerte)',
        'short': 'Crescendo',
        'desc': 'Crece progresivamente desde susurro (28) hasta impacto (127)'
    },
    'decrescendo': {
        'name': 'Decrescendo (Fuerte a Delicado)',
        'short': 'Decrescendo',
        'desc': 'Comienza enérgico en 1 (127) y se atenúa suavemente a 28'
    },
    'sincopa': {
        'name': 'Síncopa (Delicado en 1, Fuerte contratiempos)',
        'short': 'Síncopa',
        'desc': 'Acentos en pulsos pares/contratiempo (125), beat 1 suave (30)'
    },
    'ghost_notes': {
        'name': 'Ghost Notes (Acento / Susurro Alterno)',
        'short': 'Ghost Notes',
        'desc': 'Golpes alternos entre fortissimo (126) y notas fantasma (26)'
    },
    'unison': {
        'name': 'Plano (Constante)',
        'short': 'Plano',
        'desc': 'Dinámica homogénea y constante en todos los beats'
    }
}

def compute_dynamic_velocity(mode: str, beat_in_bar: int, beats_per_bar: int, base_velocity: int = 90) -> int:
    """
    Computes strike velocity (dynamics: fuerte / delicado) depending on the beat of the compás.
    Provides clear, dramatic dynamic contrast between forte (ff) and piano/ghost (pp).
    """
    num = max(1, beats_per_bar)
    b_idx = max(0, min(num - 1, beat_in_bar))
    norm_pos = b_idx / max(1, num - 1) if num > 1 else 0.0

    if mode == 'forte':
        # Pure Fortissimo: maximum presence and impact
        return 126

    elif mode in ('delicado', 'piano'):
        # Pure Pianissimo: delicate, ethereal whisper
        return 32

    elif mode in ('marcato', 'accent_bar'):
        # Extreme contrast: Beat 0 is 127 (ff), all other beats are 34 (pp)
        if b_idx == 0:
            return 127
        else:
            return 34

    elif mode == 'sincopa':
        # Beat 0 is delicate (30), offbeats/odd beats are fortissimo (125)
        if b_idx == 0:
            return 30
        elif b_idx % 2 == 1:
            return 125
        else:
            return 38

    elif mode == 'crescendo':
        # From whisper (28) up to fortissimo (127) at bar resolution
        return int(28 + 99 * norm_pos)

    elif mode == 'decrescendo':
        # From fortissimo (127) on beat 0 down to whisper (28)
        return int(127 - 99 * norm_pos)

    elif mode == 'ghost_notes':
        # Alternating fortissimo and ghost whisper
        return 126 if (b_idx % 2 == 0) else 26

    else:  # 'unison' / default
        return max(30, min(127, base_velocity))

def resolve_strike_steps(conf) -> List[int]:
    """
    Resolves strike configuration into 1..8 step states (STEP_REST, STEP_HIT, STEP_TIE).
    Supports integer counts, step sequences, or 'x'/'~'/'-' pattern strings.
    """
    return normalize_pattern(conf, default_len=DEFAULT_PATTERN_STEPS)


def bjorklund_euclidean(hits: int, steps: int = 6) -> List[int]:
    """Euclidean rhythm generator using Bjorklund algorithm."""
    return euclidean_pattern(hits, steps)


def generate_random_strikes(
    style: str,
    cur_left: Optional[List[int]] = None,
    cur_right: Optional[List[int]] = None
) -> Tuple[List[int], List[int]]:
    """
    Generates diverse musical, polyrhythmic and creative strike configurations while
    preserving each side's active step length (1..8 steps).
    Styles: 'ida', 'vuelta', 'bilateral', 'flamenco', 'euclidean', 'syncopated', 'chaos'.
    """
    left = normalize_pattern(cur_left) if cur_left is not None else [STEP_HIT] + [STEP_REST] * 5
    right = normalize_pattern(cur_right) if cur_right is not None else [STEP_HIT] + [STEP_REST] * 5
    len_l = len(left)
    len_r = len(right)
    st = (style or "random").lower()

    if st == 'ida':
        left = generate_random_pattern_side(len_l, 'random')
    elif st == 'vuelta':
        right = generate_random_pattern_side(len_r, 'random')
    elif st == 'bilateral':
        left = generate_random_pattern_side(len_l, 'random')
        right = generate_random_pattern_side(len_r, 'random')
    elif st == 'flamenco':
        left = generate_random_pattern_side(len_l, 'flamenco')
        right = generate_random_pattern_side(len_r, 'flamenco')
    elif st == 'euclidean':
        left = generate_random_pattern_side(len_l, 'euclidean')
        right = generate_random_pattern_side(len_r, 'euclidean')
    elif st == 'syncopated':
        left = generate_random_pattern_side(len_l, 'syncopated')
        right = generate_random_pattern_side(len_r, 'syncopated')
    elif st == 'chaos':
        left = generate_random_pattern_side(len_l, 'chaos')
        right = generate_random_pattern_side(len_r, 'chaos')
    else:
        left = generate_random_pattern_side(len_l, 'random')
        right = generate_random_pattern_side(len_r, 'random')

    if count_hits(left) == 0 and count_hits(right) == 0:
        left[0] = STEP_HIT

    return (left, right)


STRIKE_PATTERNS: Dict[str, Dict[str, Any]] = {
    '1+1': {
        'name': '1+1 (Estándar)',
        'short': '1+1',
        'ida': 1,
        'vuelta': 1,
        'izq': 1,
        'der': 1,
        'desc': '1 golpe al ir, 1 golpe al volver'
    },
    '1+2': {
        'name': '1+2 (Rebote Retorno)',
        'short': '1+2',
        'ida': 1,
        'vuelta': 2,
        'izq': 1,
        'der': 2,
        'desc': '1 golpe a la izq, 2 golpes a la der'
    },
    '2+1': {
        'name': '2+1 (Impulso Entrada)',
        'short': '2+1',
        'ida': 2,
        'vuelta': 1,
        'izq': 2,
        'der': 1,
        'desc': '2 golpes a la izq, 1 golpe a la der'
    },
    '2+2': {
        'name': '2+2 (Doble Continuo)',
        'short': '2+2',
        'ida': 2,
        'vuelta': 2,
        'izq': 2,
        'der': 2,
        'desc': '2 golpes a la izq, 2 golpes a la der'
    },
    '1+3': {
        'name': '1+3 (Tresillo Retorno)',
        'short': '1+3',
        'ida': 1,
        'vuelta': 3,
        'izq': 1,
        'der': 3,
        'desc': '1 golpe a la izq, 3 golpes a la der'
    },
    '3+1': {
        'name': '3+1 (Tresillo Entrada)',
        'short': '3+1',
        'ida': 3,
        'vuelta': 1,
        'izq': 3,
        'der': 1,
        'desc': '3 golpes a la izq, 1 golpe a la der'
    },
    '3+3': {
        'name': '3+3 (Sextillo Bilateral)',
        'short': '3+3',
        'ida': 3,
        'vuelta': 3,
        'izq': 3,
        'der': 3,
        'desc': '3 golpes a la izq, 3 golpes a la der'
    },
    '1+4': {
        'name': '1+4 (Cuatrillo Retorno)',
        'short': '1+4',
        'ida': 1,
        'vuelta': 4,
        'izq': 1,
        'der': 4,
        'desc': '1 golpe a la izq, 4 golpes a la der'
    },
    '4+1': {
        'name': '4+1 (Cuatrillo Entrada)',
        'short': '4+1',
        'ida': 4,
        'vuelta': 1,
        'izq': 4,
        'der': 1,
        'desc': '4 golpes a la izq, 1 golpe a la der'
    },
    '4+4': {
        'name': '4+4 (Cuatrillo Doble)',
        'short': '4+4',
        'ida': 4,
        'vuelta': 4,
        'izq': 4,
        'der': 4,
        'desc': '4 golpes a la izq, 4 golpes a la der'
    },
    '1+5': {
        'name': '1+5 (Quintillo Retorno)',
        'short': '1+5',
        'ida': 1,
        'vuelta': 5,
        'izq': 1,
        'der': 5,
        'desc': '1 golpe a la izq, 5 golpes a la der'
    },
    '5+1': {
        'name': '5+1 (Quintillo Entrada)',
        'short': '5+1',
        'ida': 5,
        'vuelta': 1,
        'izq': 5,
        'der': 1,
        'desc': '5 golpes a la izq, 1 golpe a la der'
    },
    '5+5': {
        'name': '5+5 (Quintillo Doble)',
        'short': '5+5',
        'ida': 5,
        'vuelta': 5,
        'izq': 5,
        'der': 5,
        'desc': '5 golpes a la izq, 5 golpes a la der'
    },
    '1+6': {
        'name': '1+6 (Guitarra 6 Cuerdas Retorno)',
        'short': '1+6 🎸',
        'ida': 1,
        'vuelta': 6,
        'izq': 1,
        'der': 6,
        'desc': '1 golpe a la izq, 6 golpes a la der (como las 6 cuerdas de la guitarra)'
    },
    '6+1': {
        'name': '6+1 (Guitarra 6 Cuerdas Entrada)',
        'short': '6+1 🎸',
        'ida': 6,
        'vuelta': 1,
        'izq': 6,
        'der': 1,
        'desc': '6 golpes a la izq (guitarra), 1 golpe a la der'
    },
    '6+6': {
        'name': '6+6 (Guitarra Completa 6 Cuerdas Bilateral)',
        'short': '6+6 🎸',
        'ida': 6,
        'vuelta': 6,
        'izq': 6,
        'der': 6,
        'desc': '6 golpes a la izq, 6 golpes a la der (arpegio de 6 cuerdas en ambos sentidos)'
    },
    '1+0': {
        'name': '1+0 (Solo Izquierda)',
        'short': '1+0',
        'ida': 1,
        'vuelta': 0,
        'izq': 1,
        'der': 0,
        'desc': 'Suena solo a la izq, silencio a la der'
    },
    '0+1': {
        'name': '0+1 (Solo Derecha)',
        'short': '0+1',
        'ida': 0,
        'vuelta': 1,
        'izq': 0,
        'der': 1,
        'desc': 'Silencio a la izq, suena solo a la der'
    },
    '2+0': {
        'name': '2+0 (Doble Solo Izquierda)',
        'short': '2+0',
        'ida': 2,
        'vuelta': 0,
        'izq': 2,
        'der': 0,
        'desc': '2 golpes a la izq, silencio a la der'
    },
    '0+2': {
        'name': '0+2 (Doble Solo Derecha)',
        'short': '0+2',
        'ida': 0,
        'vuelta': 2,
        'izq': 0,
        'der': 2,
        'desc': 'Silencio a la izq, 2 golpes a la der'
    },
    '3+0': {
        'name': '3+0 (Tresillo Solo Izquierda)',
        'short': '3+0',
        'ida': 3,
        'vuelta': 0,
        'izq': 3,
        'der': 0,
        'desc': '3 golpes a la izq, silencio a la der'
    },
    '0+3': {
        'name': '0+3 (Tresillo Solo Derecha)',
        'short': '0+3',
        'ida': 0,
        'vuelta': 3,
        'izq': 0,
        'der': 3,
        'desc': 'Silencio a la izq, 3 golpes a la der'
    },
    '4+0': {
        'name': '4+0 (Cuatrillo Solo Izquierda)',
        'short': '4+0',
        'ida': 4,
        'vuelta': 0,
        'izq': 4,
        'der': 0,
        'desc': '4 golpes a la izq, silencio a la der'
    },
    '0+4': {
        'name': '0+4 (Cuatrillo Solo Derecha)',
        'short': '0+4',
        'ida': 0,
        'vuelta': 4,
        'izq': 0,
        'der': 4,
        'desc': 'Silencio a la izq, 4 golpes a la der'
    },
    '5+0': {
        'name': '5+0 (Quintillo Solo Izquierda)',
        'short': '5+0',
        'ida': 5,
        'vuelta': 0,
        'izq': 5,
        'der': 0,
        'desc': '5 golpes a la izq, silencio a la der'
    },
    '0+5': {
        'name': '0+5 (Quintillo Solo Derecha)',
        'short': '0+5',
        'ida': 0,
        'vuelta': 5,
        'izq': 0,
        'der': 5,
        'desc': 'Silencio a la izq, 5 golpes a la der'
    },
    '6+0': {
        'name': '6+0 (Guitarra 6 Cuerdas Solo Izquierda)',
        'short': '6+0 🎸',
        'ida': 6,
        'vuelta': 0,
        'izq': 6,
        'der': 0,
        'desc': '6 golpes a la izq (guitarra), silencio a la der'
    },
    '0+6': {
        'name': '0+6 (Guitarra 6 Cuerdas Solo Derecha)',
        'short': '0+6 🎸',
        'ida': 0,
        'vuelta': 6,
        'izq': 0,
        'der': 6,
        'desc': 'Silencio a la izq, 6 golpes a la der (guitarra)'
    }
}

HARMONIC_FILL_PALETTES: Dict[str, Dict[str, Any]] = {
    'chord_arpeggio': {
        'name': 'Arpegio de Acorde (1ª - 3ª - 5ª - 8ª)',
        'short': 'Arpegio',
        'desc': 'Arpegia sobre la tríada/acorde de la armonía activa'
    },
    'guitar_strum': {
        'name': 'Guitarra Rasgueo (6 Cuerdas Acorde)',
        'short': 'Guitarra',
        'desc': 'Distribución armónica de las 6 cuerdas de la guitarra (Grave a Agudo)'
    },
    'scale_run_loop': {
        'name': 'Escala Corrida (Bucle)',
        'short': 'EscBucle',
        'desc': 'Recorre la escala completa nota a nota por cada golpe en bucle'
    },
    'scale_run_oneshot': {
        'name': 'Escala Corrida (Hasta Terminar)',
        'short': 'EscFin',
        'desc': 'Recorre la escala entera hasta la última nota y luego reposa/silencia'
    },
    'scale_run_pingpong': {
        'name': 'Escala Corrida (Ida y Vuelta)',
        'short': 'EscPing',
        'desc': 'Recorre la escala ascendente y descendente (ping-pong)'
    },
    'scale_run_pingpong_oneshot': {
        'name': 'Escala Corrida (Ida y Vuelta · 1 Vez)',
        'short': 'EscIdV1',
        'desc': 'Sube hasta la octava, regresa hasta la nota inicial y luego reposa/silencia'
    },
    'scale_run_pool': {
        'name': 'Escala Sistema (Bolas 1 a N)',
        'short': 'EscPool',
        'desc': 'Recorre todas las notas del sistema de péndulos en orden'
    },
    'scale_step': {
        'name': 'Escala Paso a Paso (+1 Grado)',
        'short': 'Escala',
        'desc': 'Avanza grado a grado por la escala musical activa'
    },
    'power_fifths': {
        'name': 'Quintas y Octavas (1ª - 5ª - 8ª)',
        'short': 'Quintas',
        'desc': 'Intervalos de 5ª y 8ª brillantes y etéreos'
    },
    'ornament': {
        'name': 'Bordadura / Trino (+1 / -1)',
        'short': 'Bordadura',
        'desc': 'Ornamento melódico alternando grados cercanos'
    },
    'unison': {
        'name': 'Unísono (Misma Nota)',
        'short': 'Unís',
        'desc': 'Todos los golpes suenan en la misma nota base'
    }
}

SCALE_RUN_PALETTES = (
    'scale_run_loop',
    'scale_run_oneshot',
    'scale_run_pingpong',
    'scale_run_pingpong_oneshot',
    'scale_run_pool',
)


def is_scale_run_palette(palette_key: Optional[str]) -> bool:
    """Returns True if palette_key traverses the scale sequentially across strikes."""
    return palette_key in SCALE_RUN_PALETTES

def get_scale_notes_for_run(base_pitch: int, scale_notes: List[int], harmony_type: str = 'minor_harmonic') -> List[int]:
    """
    Constructs the complete scale notes sequence for a scale run.
    Uses the harmonic intervals from base_pitch to base_pitch + 12 (octave),
    or the active scale_notes pool.
    """
    harm_def = HARMONIC_TYPES.get(harmony_type, {})
    intervals = harm_def.get('intervals')
    if intervals and harmony_type not in ('drum_kit', 'monotone'):
        run_notes = [min(108, max(21, base_pitch + iv)) for iv in intervals]
        run_notes.append(min(108, max(21, base_pitch + 12)))
        return run_notes
    elif scale_notes:
        return sorted(list(set(scale_notes)))
    else:
        return [base_pitch]

def compute_strike_pitch(
    base_pitch: int,
    strike_idx: int,
    palette_key: str,
    scale_notes: List[int],
    strike_counter: int = 0,
    harmony_type: str = 'minor_harmonic'
) -> Optional[int]:
    """
    Computes the melodic pitch for a multi-strike event (1st, 2nd, 3rd... strike in a pass)
    or sequential scale run across strikes according to the selected harmonic fill palette.
    Returns None if the palette is in one-shot mode and has reached the end of the scale.
    """
    pal = palette_key if palette_key in HARMONIC_FILL_PALETTES else 'chord_arpeggio'

    # Sequential Scale Traversal Palettes (run entire scale in order of strikes)
    if pal == 'scale_run_loop':
        run_notes = get_scale_notes_for_run(base_pitch, scale_notes, harmony_type)
        return run_notes[strike_counter % len(run_notes)]

    elif pal == 'scale_run_oneshot':
        run_notes = get_scale_notes_for_run(base_pitch, scale_notes, harmony_type)
        if strike_counter < len(run_notes):
            return run_notes[strike_counter]
        return None  # Finished running the scale!

    elif pal == 'scale_run_pingpong':
        run_notes = get_scale_notes_for_run(base_pitch, scale_notes, harmony_type)
        n = len(run_notes)
        if n <= 1:
            return run_notes[0]
        cycle = 2 * (n - 1)
        phase = strike_counter % cycle
        idx = phase if phase < n else cycle - phase
        return run_notes[idx]

    elif pal == 'scale_run_pingpong_oneshot':
        run_notes = get_scale_notes_for_run(base_pitch, scale_notes, harmony_type)
        n = len(run_notes)
        if n <= 1:
            return run_notes[0] if strike_counter == 0 else None
        full_seq = run_notes + list(reversed(run_notes[:-1]))
        if strike_counter < len(full_seq):
            return full_seq[strike_counter]
        return None

    elif pal == 'scale_run_pool':
        pool = sorted(list(set(scale_notes))) if scale_notes else [base_pitch]
        return pool[strike_counter % len(pool)]

    # Standard Sub-strike Burst Palettes
    if strike_idx <= 0 or pal == 'unison' or not scale_notes:
        return base_pitch

    pal = palette_key if palette_key in HARMONIC_FILL_PALETTES else 'chord_arpeggio'

    if pal == 'power_fifths':
        fifths_offsets = [0, 7, 12, 19, 24, 31]
        offset = fifths_offsets[strike_idx % len(fifths_offsets)]
        octave_add = (strike_idx // len(fifths_offsets)) * 12
        return min(108, base_pitch + offset + octave_add)

    # For scale/chord palettes, find location in scale_notes
    pool = scale_notes
    best_idx = 0
    min_diff = 999
    for i, p in enumerate(pool):
        diff = abs(p - base_pitch)
        if diff < min_diff:
            min_diff = diff
            best_idx = i

    harm_def = HARMONIC_TYPES.get(harmony_type, {})
    intervals = harm_def.get('intervals')
    if not intervals or harmony_type in ('drum_kit', 'monotone'):
        intervals = [0, 2, 4, 5, 7, 9, 11]
    n_deg = len(intervals)

    if pal == 'guitar_strum':
        # Guitar 6-string chord voicing: String 6 (root), String 5 (5th), String 4 (8ve root), String 3 (10th/3rd), String 2 (12th/5th), String 1 (double 8ve)
        guitar_degrees = [0, 4, 7, 9, 11, 14]
        deg = guitar_degrees[strike_idx % len(guitar_degrees)]
        extra_oct = (strike_idx // len(guitar_degrees)) * 12
        oct_shift = (deg // n_deg) * 12
        semi = intervals[deg % n_deg] + oct_shift + extra_oct
        return min(108, max(21, base_pitch + semi))

    elif pal == 'chord_arpeggio':
        # Triad arpeggio spanning 6 notes across 2 octaves: 1st, 3rd, 5th, 8ve, 10th, 12th
        triad_degrees = [0, 2, 4, 7, 9, 11]
        deg = triad_degrees[strike_idx % len(triad_degrees)]
        extra_oct = (strike_idx // len(triad_degrees)) * 12
        oct_shift = (deg // n_deg) * 12
        semi = intervals[deg % n_deg] + oct_shift + extra_oct
        return min(108, max(21, base_pitch + semi))

    elif pal == 'scale_step':
        # Stepwise scale movement: +1, +2, +3...
        target_idx = best_idx + strike_idx
        oct_span = (target_idx // len(pool)) * 12
        note = pool[target_idx % len(pool)] + oct_span
        return min(108, max(21, note))

    elif pal == 'ornament':
        # Melodic embellishment / mordent: 6 steps
        orn_steps = [0, 1, 0, 2, 1, 0]
        step = orn_steps[strike_idx % len(orn_steps)]
        target_idx = best_idx + step
        if target_idx < 0:
            note = pool[target_idx % len(pool)] - 12
        else:
            oct_span = (target_idx // len(pool)) * 12
            note = pool[target_idx % len(pool)] + oct_span
        return min(108, max(21, note))

    return base_pitch


# --- Strum Progression Ratios & Accent Sensitivity (Rasgueo no uniforme) ---

STRUM_PROGRESSIONS = {
    'hyper_fast': {'name': 'Ráfaga Hiper-Rápida (0.30)', 'ratio': 0.30, 'short': '0.30 🌪'},
    'ultra_fast': {'name': 'Flamenco Ultra (0.45)', 'ratio': 0.45, 'short': '0.45 ⚡'},
    'rasgueo_fast': {'name': 'Rasgueo Flamenco (0.60)', 'ratio': 0.60, 'short': '0.60 🔥'},
    'rasgueo_guitar': {'name': 'Rasgueo Guitarra (0.72)', 'ratio': 0.72, 'short': '0.72 🎸'},
    'rasgueo_soft': {'name': 'Rasgueo Suave (0.85)', 'ratio': 0.85, 'short': '0.85'},
    'uniform': {'name': 'Uniforme (1.0)', 'ratio': 1.0, 'short': '1.0'},
    'arpeggio_decel': {'name': 'Arpegio Decelerando (1.50)', 'ratio': 1.50, 'short': '1.50'},
    'decel_marked': {'name': 'Decelerando Marcado (1.80)', 'ratio': 1.80, 'short': '1.80'},
    'hyper_decel': {'name': 'Decelerando Freno (2.20)', 'ratio': 2.20, 'short': '2.20 🌊'},
    'ultra_open': {'name': 'Cascada Hiper-Expansiva (3.20)', 'ratio': 3.20, 'short': '3.20 ✨'},
}

STRUM_ACCENT_SENSITIVITIES = {
    'none': {'name': '0% (Sin acento)', 'value': 0.0, 'short': '0%'},
    'low': {'name': '25% (Sensibilidad Baja)', 'value': 0.25, 'short': '25%'},
    'med': {'name': '50% (Sensibilidad Media)', 'value': 0.50, 'short': '50%'},
    'high': {'name': '75% (Sensibilidad Alta)', 'value': 0.75, 'short': '75%'},
    'extreme': {'name': '100% (Sensibilidad Extrema)', 'value': 1.00, 'short': '100%'},
}

def compute_strum_delays(active_step_count: int, total_span: float, ratio: float = 0.72) -> List[float]:
    """
    Computes progressive time offsets (in seconds) for successive strikes in a guitar strum.
    If ratio == 1.0, intervals are equidistant / uniform.
    If ratio < 1.0, intervals get progressively shorter (accelerating guitar strum sweep).
    If ratio > 1.0, intervals get progressively longer (decelerating arpeggiation).
    """
    if active_step_count <= 1:
        return [0.0]
    weights = [ratio ** j for j in range(active_step_count - 1)]
    sum_w = sum(weights)
    if sum_w <= 0.0001:
        sum_w = float(active_step_count - 1)
        weights = [1.0] * (active_step_count - 1)

    offsets = [0.0]
    cum = 0.0
    for w in weights:
        cum += (w / sum_w) * total_span
        offsets.append(cum)
    return offsets

def compute_strum_velocity(base_vel: int, strike_idx: int, total_strikes: int, sensitivity: float = 0.50) -> int:
    """
    Computes velocity for strike_idx in a strum based on accent sensitivity (0.0 to 1.0).
    Higher sensitivity produces stronger accent on the initial strike and dynamic sweep curve.
    """
    if strike_idx == 0 or total_strikes <= 1:
        return base_vel
    decay_fraction = strike_idx / max(1, total_strikes - 1)
    factor = 1.0 - (sensitivity * 0.45 * decay_fraction)
    return max(25, min(127, int(base_vel * factor)))


def get_degree_chord_name(root_key: str, harmony_type: str, degree_idx: int, with_seventh: bool = False) -> str:
    """
    Returns harmonic degree and chord label (e.g. 'I (Em)', 'IV (Am7)', 'V (B)').
    """
    harm_def = HARMONIC_TYPES.get(harmony_type, HARMONIC_TYPES.get('minor_harmonic', {}))
    scale_intervals = harm_def.get('intervals', [0, 2, 3, 5, 7, 8, 11])
    n = max(1, len(scale_intervals))
    deg = degree_idx % n

    root_clean = root_key.strip().upper() if root_key else 'E'
    if root_clean not in NOTE_NAMES:
        root_clean = 'E'
    root_pitch = note_name_to_midi(root_clean, 3)

    deg_root_pitch = root_pitch + scale_intervals[deg]
    deg_root_name = NOTE_NAMES[deg_root_pitch % 12]

    # Calculate intervals of 3rd and 5th relative to chord root
    step_3rd = deg + 2
    step_5th = deg + 4
    semi_3rd = (scale_intervals[step_3rd % n] + (step_3rd // n) * 12) - scale_intervals[deg]
    semi_5th = (scale_intervals[step_5th % n] + (step_5th // n) * 12) - scale_intervals[deg]

    if semi_3rd == 4 and semi_5th == 7:
        qual = "maj7" if with_seventh else ""
    elif semi_3rd == 3 and semi_5th == 7:
        qual = "m7" if with_seventh else "m"
    elif semi_3rd == 3 and semi_5th == 6:
        qual = "m7b5" if with_seventh else "dim"
    elif semi_3rd == 4 and semi_5th == 8:
        qual = "aug"
    elif semi_3rd == 3:
        qual = "m"
    else:
        qual = ""

    roman_numerals = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    r_num = roman_numerals[deg] if deg < len(roman_numerals) else f"{deg + 1}"
    return f"{r_num} ({deg_root_name}{qual})"


def build_degree_chord_pitches(
    root_key: str = 'E',
    base_octave: int = 2,
    harmony_type: str = 'minor_harmonic',
    degree_idx: int = 0,
    n_pitches: int = 4,
    inversion: int = 0,
    add_seventh: bool = False
) -> List[int]:
    """
    Generates musical chord pitches across n_pitches (for active pendulum balls)
    based on the scale degree (I to VII), chord inversion (0=root, 1=1st inv, 2=2nd inv),
    and harmonic color/extensions.
    """
    root_clean = root_key.strip().upper() if root_key else 'E'
    if root_clean not in NOTE_NAMES:
        root_clean = 'E'
    root_pitch = note_name_to_midi(root_clean, base_octave)

    harm_def = HARMONIC_TYPES.get(harmony_type, HARMONIC_TYPES.get('minor_harmonic', {}))
    scale_intervals = harm_def.get('intervals', [0, 2, 3, 5, 7, 8, 11])
    n = max(1, len(scale_intervals))
    d = degree_idx % n

    def get_scale_step_pitch(step: int) -> int:
        oct_add = (step // n) * 12
        return root_pitch + scale_intervals[step % n] + oct_add

    # Diatonic triad and extension steps
    if add_seventh and n >= 5:
        base_chord_steps = [d, d + 2, d + 4, d + (6 if n >= 7 else 3)]
    else:
        base_chord_steps = [d, d + 2, d + 4]

    # Apply inversion: rotate base triad tones
    inv = inversion % len(base_chord_steps)
    chord_tones: List[int] = []
    for idx in range(len(base_chord_steps)):
        src_idx = (idx + inv) % len(base_chord_steps)
        step = base_chord_steps[src_idx]
        pitch = get_scale_step_pitch(step)
        if src_idx < inv:
            pitch += 12  # Transpose inverted bass tones up an octave
        chord_tones.append(pitch)

    # Sort bass to treble for natural strumming
    chord_tones.sort()

    # Expand across n_pitches with octave doubling
    result_pitches: List[int] = []
    for i in range(n_pitches):
        base_tone = chord_tones[i % len(chord_tones)]
        oct_mult = i // len(chord_tones)
        p = min(108, max(24, base_tone + oct_mult * 12))
        result_pitches.append(p)

    return result_pitches


CHORD_QUALITY_INTERVALS: Dict[str, Tuple[List[int], str]] = {
    'major': ([0, 4, 7], ''),
    'minor': ([0, 3, 7], 'm'),
    'dom7': ([0, 4, 7, 10], '7'),
    'min7': ([0, 3, 7, 10], 'm7'),
    'maj7': ([0, 4, 7, 11], 'maj7'),
    'sus4': ([0, 5, 7], 'sus4'),
    'power5': ([0, 7, 12], '5'),
}


def build_chord_for_midi(
    target_midi: int,
    quality: str = 'diatonic',
    home_root_midi: Optional[int] = None,
    harmony_type: str = 'minor_harmonic',
    add_seventh: bool = False,
    strum_voicing: bool = False,
) -> Tuple[List[int], str]:
    """Builds sorted unique MIDI chord pitches and chord label anchored at target_midi."""
    root_midi = max(21, min(108, int(target_midi)))
    root_name = NOTE_NAMES[root_midi % 12]

    if harmony_type == 'drum_kit':
        return [root_midi], root_name

    if quality in CHORD_QUALITY_INTERVALS:
        base_iv, base_suffix = CHORD_QUALITY_INTERVALS[quality]
        intervals = list(base_iv)
        qual_str = base_suffix
        if add_seventh:
            if quality == 'major':
                intervals.append(11)
                qual_str = 'maj7'
            elif quality == 'minor':
                intervals.append(10)
                qual_str = 'm7'
            elif quality == 'sus4':
                intervals.append(10)
                qual_str = '7sus4'
    else:
        if harmony_type == 'monotone':
            intervals = [0]
            qual_str = ''
        elif harmony_type == 'chord_min9':
            intervals = [0, 3, 7, 10] if add_seventh else [0, 3, 7]
            qual_str = 'm7' if add_seventh else 'm'
        elif harmony_type == 'chord_maj9':
            intervals = [0, 4, 7, 11] if add_seventh else [0, 4, 7]
            qual_str = 'maj7' if add_seventh else ''
        elif harmony_type == 'sus4_ambient':
            intervals = [0, 5, 7, 10] if add_seventh else [0, 5, 7]
            qual_str = '7sus4' if add_seventh else 'sus4'
        else:
            scale_iv = HARMONIC_TYPES.get(
                harmony_type, HARMONIC_TYPES['minor_harmonic']
            ).get('intervals', [0, 2, 3, 5, 7, 8, 11])
            n = max(1, len(scale_iv))

            if quality == 'diatonic' and home_root_midi is not None:
                rel = (root_midi - int(home_root_midi)) % 12
                deg = scale_iv.index(rel) if rel in scale_iv else 0
            else:
                deg = 0

            if n >= 7:
                base_val = scale_iv[deg]

                def _step_semi(step: int) -> int:
                    return (scale_iv[step % n] + (step // n) * 12) - base_val

                intervals = [0, _step_semi(deg + 2), _step_semi(deg + 4)]
                if add_seventh:
                    intervals.append(_step_semi(deg + 6))
            else:
                rel_set = {(scale_iv[j] - scale_iv[deg]) % 12 for j in range(n)}
                semi_3 = 3 if 3 in rel_set else (4 if 4 in rel_set else (5 if 5 in rel_set else 2))
                semi_5 = 7 if 7 in rel_set else (6 if 6 in rel_set else (8 if 8 in rel_set else 7))
                intervals = [0, semi_3, semi_5]
                if add_seventh:
                    intervals.append(10 if 10 in rel_set else (11 if 11 in rel_set else 10))

            s3 = intervals[1] if len(intervals) > 1 else 0
            s5 = intervals[2] if len(intervals) > 2 else 7
            s7 = intervals[3] if len(intervals) > 3 else None

            triad_map = {
                (4, 7): ('', {11: 'maj7', 10: '7'}),
                (3, 7): ('m', {10: 'm7', 11: 'm(maj7)'}),
                (3, 6): ('dim', {9: 'dim7', 10: 'm7b5'}),
                (4, 8): ('aug', {11: 'augMaj7', 10: 'aug7'}),
                (5, 7): ('sus4', {10: '7sus4'}),
            }
            if (s3, s5) in triad_map:
                base_q, sev_map = triad_map[(s3, s5)]
                qual_str = sev_map.get(s7, base_q) if s7 is not None else base_q
            else:
                qual_str = 'm' if s3 == 3 else ''

    pitches = sorted({max(21, min(108, root_midi + iv)) for iv in intervals})
    if strum_voicing and len(pitches) >= 3 and quality != 'power5':
        oct_top = min(108, root_midi + 12)
        if oct_top not in pitches:
            pitches = sorted(set(pitches + [oct_top]))

    return pitches, f"{root_name}{qual_str}"


def expand_chord_to_n_voices(
    chord_pitches: List[int],
    n_voices: int,
    inversion: int = 0,
) -> List[int]:
    """
    Builds an ascending voicing of exactly n_voices (1..6) from chord_pitches,
    starting at chord tone index `inversion % m` (deduplicated by pitch class)
    and extending smoothly across octaves.
    """
    n_req = max(1, int(n_voices))
    if not chord_pitches:
        return []

    seen_pc = set()
    base: List[int] = []
    for p in sorted(int(x) for x in chord_pitches):
        pc = p % 12
        if pc not in seen_pc:
            seen_pc.add(pc)
            base.append(p)
    if not base:
        return []

    m = len(base)
    inv = int(inversion) % m
    rotated: List[int] = []
    for k in range(m):
        src = (k + inv) % m
        pitch = base[src]
        if src < inv:
            pitch += 12
        rotated.append(pitch)

    result: List[int] = []
    for j in range(n_req):
        tone = rotated[j % m] + (j // m) * 12
        result.append(min(108, max(21, tone)))
    return result





