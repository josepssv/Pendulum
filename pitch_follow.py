"""
Pitch-Follower & Chromatic Piano Keyboard Controller for Pendulum Polyphony.
Inverts the computer keyboard from a solo trigger into a live accompaniment pitch
controller so the pendulum system follows the soloist/melody in real time,
with interval transposition keys and extensible transition policies.
"""

from typing import Dict, List, Optional, Tuple
from harmony import HARMONIC_TYPES, NOTE_NAMES, midi_to_note_and_octave, note_name_to_midi

MIN_FOLLOW_MIDI = 24  # C1
MAX_FOLLOW_MIDI = 88  # E6 (matches MAX_KEYBOARD_BASE_MIDI + 16)

MIN_KEYBOARD_BASE_MIDI = 24  # C1
MAX_KEYBOARD_BASE_MIDI = 72  # C5 (top key +16 reaches E6 = 88)

PIANO_TOP_ROW_SLOTS: List[Tuple[str, Optional[int]]] = [
    ("Q", None),
    ("W", 1),
    ("E", 3),
    ("R", None),
    ("T", 6),
    ("Y", 8),
    ("U", 10),
    ("I", None),
    ("O", 13),
    ("P", 15),
]

PIANO_WHITE_ROW_SLOTS: List[Tuple[str, int]] = [
    ("A", 0),
    ("S", 2),
    ("D", 4),
    ("F", 5),
    ("G", 7),
    ("H", 9),
    ("J", 11),
    ("K", 12),
    ("L", 14),
    ("Ñ", 16),
]

PIANO_GAP_KEYS = {"Q", "R", "I"}

PIANO_NOTE_OFFSETS: Dict[str, int] = {
    **{k: off for k, off in PIANO_TOP_ROW_SLOTS if off is not None},
    **{k: off for k, off in PIANO_WHITE_ROW_SLOTS},
}

TRANSPOSE_ROW_KEYS: List[str] = ["Z", "X", "C", "V", "B", "N", "M", ",", "."]

THIRD_INTERVAL_MODES: Dict[str, Dict[str, str]] = {
    "auto": {"name": "Auto", "short": "Auto"},
    "minor": {"name": "3ª menor (3st)", "short": "3ªm"},
    "major": {"name": "3ª mayor (4st)", "short": "3ªM"},
}

FOLLOW_TRANSITION_MODES: Dict[str, Dict[str, str]] = {
    "immediate": {
        "name": "Inmediato (Latch)",
        "short": "Inmediato",
        "desc": "Cambia el tono al instante y lo mantiene hasta pulsar otra nota",
    },
    "next_beat": {
        "name": "Siguiente Pulso",
        "short": "Sig. Pulso",
        "desc": "Encola el cambio y lo aplica en el siguiente pulso del compás",
    },
    "next_bar": {
        "name": "Inicio de Compás",
        "short": "Sig. Compás",
        "desc": "Encola el cambio y lo aplica al empezar el siguiente compás",
    },
    "momentary": {
        "name": "Momentáneo (Hold)",
        "short": "Hold",
        "desc": "Transpone mientras mantienes pulsada la tecla; al soltar vuelve al tono base",
    },
}

SHORT_CLICK_THRESHOLD_SEC = 0.25
KEYBOARD_VOICE_INDEX = 15

KEYBOARD_SOUND_MODES: Dict[str, Dict[str, str]] = {
    "hold": {
        "name": "Dinámico (Hold)",
        "short": "Hold",
        "desc": "Suena al instante al pulsar: clic corto = nota breve, mantener = sostenida",
    },
    "staccato": {
        "name": "Clic Corto (Staccato)",
        "short": "Staccato",
        "desc": "Suena siempre un toque breve fijo (0.22s) al pulsar cada tecla",
    },
    "short_only": {
        "name": "Solo Clic <250ms",
        "short": "<250ms",
        "desc": "Solo suena al soltar si fue un clic rápido (<250ms); mantener solo cambia tono",
    },
    "silent": {
        "name": "Silencio (Solo Tono)",
        "short": "Silencio",
        "desc": "El teclado no emite nota propia; solo cambia el tono del acompañamiento",
    },
}

CHORD_PLAY_MODES: Dict[str, Dict[str, str]] = {
    "off": {"name": "Solo Nota", "short": "Nota"},
    "block": {"name": "Acorde (Bloque)", "short": "Acorde"},
    "strum": {"name": "Rasgueo (Strum)", "short": "Rasgueo"},
}

CHORD_TARGET_MODES: Dict[str, Dict[str, str]] = {
    "both": {"name": "Acomp + Teclado", "short": "Ambos"},
    "accompaniment": {"name": "Solo Acomp", "short": "Acomp"},
    "keyboard": {"name": "Solo Teclado", "short": "Teclado"},
}

CHORD_QUALITY_MODES: Dict[str, Dict[str, str]] = {
    "diatonic": {"name": "Auto (Diatónico)"},
    "parallel": {"name": "Paralelo (Armonía)"},
    "major": {"name": "Mayor"},
    "minor": {"name": "Menor"},
    "dom7": {"name": "Dominante 7ª"},
    "min7": {"name": "Menor 7ª (m7)"},
    "maj7": {"name": "Mayor 7ª (Maj7)"},
    "sus4": {"name": "Sus4"},
    "power5": {"name": "Power 5ª"},
}


def resolve_piano_key(char: str, keysym: str, is_shift: bool = False) -> Optional[str]:
    """Maps a keyboard event's char/keysym to one of the 17 chromatic piano key IDs."""
    c = (char or "").lower()
    k = (keysym or "").lower()

    if c == "ñ" or k == "ntilde":
        return "Ñ"
    if (c == ";" or k == "semicolon") and not is_shift:
        return "Ñ"

    c_up = c.upper()
    if c_up in PIANO_NOTE_OFFSETS:
        return c_up
    k_up = k.upper()
    if k_up in PIANO_NOTE_OFFSETS:
        return k_up
    return None


def is_piano_gap_key(char: str, keysym: str) -> bool:
    """Returns True if the event corresponds to an inactive black-key gap (Q, R, I)."""
    return (char or "").upper() in PIANO_GAP_KEYS or (keysym or "").upper() in PIANO_GAP_KEYS


def resolve_transpose_key(char: str, keysym: str) -> Optional[str]:
    """Maps a keyboard event's char/keysym to a transposition row key ID (Z..M, ,, ., BackSpace->.)."""
    c = (char or "").lower()
    k = (keysym or "").lower()

    if k == "comma" or c == ",":
        return ","
    if k == "period" or c == ".":
        return "."
    if k == "backspace":
        return "."

    c_up = c.upper()
    if c_up in ("Z", "X", "C", "V", "B", "N", "M"):
        return c_up
    k_up = k.upper()
    if k_up in ("Z", "X", "C", "V", "B", "N", "M"):
        return k_up
    return None


def get_third_semitones(third_mode: str, harmony_type: str) -> int:
    """Returns 3 or 4 semitones for 3rd-interval transposition based on mode and active harmony."""
    if third_mode == "minor":
        return 3
    if third_mode == "major":
        return 4
    intervals = HARMONIC_TYPES.get(harmony_type, {}).get("intervals", [])
    return 4 if (4 in intervals and 3 not in intervals) else 3


def format_semitone_offset(semitones: int) -> str:
    """Formats a semitone displacement into a musical interval summary label."""
    s = int(semitones)
    if s == 0:
        return "0 st (Original)"
    sign = "+" if s > 0 else "-"
    abs_s = abs(s)
    interval_names = {
        1: "2ªm",
        3: "3ªm",
        4: "3ªM",
        5: "4ª",
        7: "5ª",
        12: "8ª",
    }
    if abs_s in interval_names:
        return f"{s:+d} st ({sign}{interval_names[abs_s]})"
    if s % 12 == 0:
        return f"{s:+d} st ({s // 12:+d}×8ª)"
    return f"{s:+d} st"


class PitchFollowController:
    """
    Stateful controller managing chromatic piano note-to-pitch mapping,
    keyboard interval transposition, and extensible accompaniment transition policies.
    """

    def __init__(
        self,
        root_midi: int = 40,
        transition_mode: str = "immediate",
        third_mode: str = "auto",
    ):
        clamped = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, int(root_midi)))
        self.home_root_midi: int = clamped
        self.active_midi: int = clamped
        self.anchor_midi: int = clamped
        self.pending_midi: Optional[int] = None

        base_oct = max(1, min(5, (clamped // 12) - 1))
        c_midi = max(MIN_KEYBOARD_BASE_MIDI, min(MAX_KEYBOARD_BASE_MIDI, (base_oct + 1) * 12))
        self.keyboard_home_midi: int = c_midi
        self.keyboard_base_midi: int = c_midi

        self.transition_mode: str = (
            transition_mode if transition_mode in FOLLOW_TRANSITION_MODES else "immediate"
        )
        self.third_mode: str = (
            third_mode if third_mode in THIRD_INTERVAL_MODES else "auto"
        )
        self.held_piano_keys: List[str] = []

    @property
    def transpose_semitones(self) -> int:
        return self.keyboard_base_midi - self.keyboard_home_midi

    def midi_for_key(self, key_id: str) -> Optional[int]:
        """Returns the MIDI pitch currently mapped to piano key_id, or None if invalid."""
        offset = PIANO_NOTE_OFFSETS.get(key_id)
        if offset is None:
            return None
        return self.keyboard_base_midi + offset

    def key_for_midi(self, midi_val: Optional[int]) -> Optional[str]:
        """Returns the piano key_id currently mapped to midi_val, or None if outside span."""
        if midi_val is None:
            return None
        target_offset = int(midi_val) - self.keyboard_base_midi
        for key_id, offset in PIANO_NOTE_OFFSETS.items():
            if offset == target_offset:
                return key_id
        return None

    def get_keyboard_range_names(self) -> Tuple[str, str]:
        """Returns human-readable (low_note, high_note) names for the current 17-note span."""
        return (
            midi_to_note_and_octave(self.keyboard_base_midi),
            midi_to_note_and_octave(self.keyboard_base_midi + 16),
        )

    def get_transpose_delta(self, key_id: str, harmony_type: str) -> Optional[int]:
        """Returns semitone shift delta for Z..M/,, or None for Reset (.)."""
        third = get_third_semitones(self.third_mode, harmony_type)
        deltas: Dict[str, Optional[int]] = {
            "Z": -1,
            "X": 1,
            "C": -third,
            "V": third,
            "B": -7,
            "N": 7,
            "M": -12,
            ",": 12,
            ".": None,
        }
        return deltas.get(key_id)

    def set_transition_mode(self, mode: str) -> Optional[int]:
        """Switches transition policy; commits pending pitch immediately if switching to immediate."""
        if mode not in FOLLOW_TRANSITION_MODES:
            return None
        self.transition_mode = mode
        if mode == "immediate" and self.pending_midi is not None:
            committed = self.pending_midi
            self.pending_midi = None
            self.active_midi = committed
            self.anchor_midi = committed
            return committed
        if mode == "momentary":
            self.pending_midi = None
        return None

    def set_third_mode(self, mode: str) -> None:
        """Sets the 3rd-interval polarity mode ('auto', 'minor', or 'major')."""
        if mode in THIRD_INTERVAL_MODES:
            self.third_mode = mode

    def on_note_press(self, key_id: str, is_live_active: bool = True) -> Optional[int]:
        """Handles a piano key press according to the active transition policy."""
        if key_id in self.held_piano_keys:
            return None
        target = self.midi_for_key(key_id)
        if target is None:
            return None
        target = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, target))
        self.held_piano_keys.append(key_id)

        if self.transition_mode == "immediate" or (
            not is_live_active and self.transition_mode in ("next_beat", "next_bar")
        ):
            self.pending_midi = None
            self.active_midi = target
            self.anchor_midi = target
            return target
        if self.transition_mode in ("next_beat", "next_bar"):
            self.pending_midi = target
            return None
        if self.transition_mode == "momentary":
            self.pending_midi = None
            self.active_midi = target
            return target
        return None

    def on_note_release(self, key_id: str) -> Optional[int]:
        """Handles a piano key release; reverts to held key or anchor in momentary mode."""
        if key_id in self.held_piano_keys:
            self.held_piano_keys.remove(key_id)

        if self.transition_mode == "momentary":
            if self.held_piano_keys:
                fallback = self.midi_for_key(self.held_piano_keys[-1])
                if fallback is not None:
                    target = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, fallback))
                    self.active_midi = target
                    return target
            self.active_midi = self.anchor_midi
            return self.anchor_midi
        return None

    def on_beat_advance(self, beat_total: int, beat_in_bar: int, numerator: int) -> Optional[int]:
        """Commits queued pitch changes on beat or bar boundaries when quantized."""
        if self.pending_midi is None:
            return None
        if self.transition_mode == "next_beat" or (
            self.transition_mode == "next_bar" and beat_in_bar == 0
        ):
            target = self.pending_midi
            self.pending_midi = None
            self.active_midi = target
            self.anchor_midi = target
            return target
        return None

    def on_pendulum_crossing(self, ball_idx: int, is_primary_ball: bool = False) -> Optional[int]:
        """Extensibility hook for future strike-based or phrase-based transition policies."""
        return None

    def shift_keyboard(
        self,
        delta_semitones: int,
        apply_to_accompaniment: bool = True,
    ) -> Optional[int]:
        """Transposes the keyboard window and optionally shifts the accompaniment in lockstep."""
        old_kb = self.keyboard_base_midi
        new_kb = max(MIN_KEYBOARD_BASE_MIDI, min(MAX_KEYBOARD_BASE_MIDI, old_kb + int(delta_semitones)))
        actual_delta = new_kb - old_kb
        self.keyboard_base_midi = new_kb
        if actual_delta == 0:
            return None
        if apply_to_accompaniment:
            self.active_midi = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, self.active_midi + actual_delta))
            self.anchor_midi = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, self.anchor_midi + actual_delta))
            if self.pending_midi is not None:
                self.pending_midi = max(
                    MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, self.pending_midi + actual_delta)
                )
            return self.active_midi
        return None

    def reset_transpose(self, apply_to_accompaniment: bool = True) -> Optional[int]:
        """Resets keyboard transposition and optionally restores the home accompaniment root."""
        self.keyboard_base_midi = self.keyboard_home_midi
        self.pending_midi = None
        self.held_piano_keys.clear()
        if apply_to_accompaniment:
            self.active_midi = self.home_root_midi
            self.anchor_midi = self.home_root_midi
            return self.active_midi
        return None

    def sync_external_root(
        self,
        root_midi: int,
        update_home: bool = False,
        recenter_keyboard: bool = False,
    ) -> None:
        """Synchronizes controller state when the root key or octave changes from GUI controls."""
        clamped = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, int(root_midi)))
        self.active_midi = clamped
        self.anchor_midi = clamped
        self.pending_midi = None
        if update_home:
            self.home_root_midi = clamped
        if recenter_keyboard:
            base_oct = max(1, min(5, (clamped // 12) - 1))
            c_midi = max(MIN_KEYBOARD_BASE_MIDI, min(MAX_KEYBOARD_BASE_MIDI, (base_oct + 1) * 12))
            self.keyboard_home_midi = c_midi
            self.keyboard_base_midi = c_midi
