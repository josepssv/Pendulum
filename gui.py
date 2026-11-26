"""
Pendulum Polyphony GUI - Live Performance & Recording Studio
Allows real-time sound manipulation, accompaniment pitch-follow keyboard, and instant WAV/MIDI recording.
Full computer keyboard functionality with 4 dedicated rows:
  - Row 1 (Numbers 1-0): Timed Ball Silence Controls (Mute per Pendulum in Measures)
  - Row 2 (W-P): Chromatic Piano Black Keys (#) for accompaniment pitch follow + transition mode
  - Row 3 (A-Ñ): Chromatic Piano White Keys for accompaniment pitch follow
  - Row 4 (Z-.): Interval Transposition Controls (±1st, ±3ª, ±5ª, ±8ª, Reset)
"""

import os
import time
import math
import threading
from typing import List, Dict, Any, Optional, Tuple, Set
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pygame

from harmony import (
    NOTE_NAMES, HARMONIC_TYPES, TIME_SIGNATURES, NOTE_DURATIONS,
    DYNAMIC_MODES, STRIKE_PATTERNS, HARMONIC_FILL_PALETTES,
    STRUM_PROGRESSIONS, STRUM_ACCENT_SENSITIVITIES,
    note_name_to_midi,
    compute_dynamic_velocity, compute_note_duration, compute_tied_note_duration,
    compute_strike_pitch, resolve_strike_steps, compute_strum_delays,
    compute_strum_velocity, build_degree_chord_pitches, get_degree_chord_name,
    build_chord_for_midi, expand_chord_to_n_voices,
    generate_random_strikes, bjorklund_euclidean, is_scale_run_palette
)
from pitch_follow import (
    MIN_FOLLOW_MIDI, MAX_FOLLOW_MIDI,
    SHORT_CLICK_THRESHOLD_SEC, KEYBOARD_VOICE_INDEX,
    KEYBOARD_SOUND_MODES,
    CHORD_PLAY_MODES, CHORD_TARGET_MODES, CHORD_QUALITY_MODES,
    PIANO_TOP_ROW_SLOTS, PIANO_WHITE_ROW_SLOTS, PIANO_NOTE_OFFSETS,
    TRANSPOSE_ROW_KEYS, FOLLOW_TRANSITION_MODES, THIRD_INTERVAL_MODES,
    PitchFollowController, resolve_piano_key, is_piano_gap_key,
    resolve_transpose_key, format_semitone_offset, get_third_semitones,
)
from rhythm_patterns import (
    MIN_PATTERN_STEPS, MAX_PATTERN_STEPS, DEFAULT_PATTERN_STEPS,
    STEP_REST, STEP_HIT, STEP_TIE,
    is_hit, is_tie, count_hits, has_ties,
    normalize_pattern, resize_pattern, toggle_pattern_step,
    cycle_pattern_step, toggle_pattern_tie, set_pattern_step,
    rotate_pattern, invert_pattern, reverse_pattern,
    euclidean_pattern, format_pattern, compute_pattern_slot_delays,
    compute_step_tie_span, generate_random_pattern_side,
)
from engine import PendulumSystem, PENDULUM_COLORS, midi_to_note_name
from live_audio import LiveAudioEngine
from midi_export import export_midi
from audio_synth import export_wav, SAMPLE_RATE
from sample_engine import get_sample_engine

DRUM_VOICE_LABELS = {
    '__melodic__': '🎹 Melódico (Nota)',
    'boom': '💥 Sub Bombo (Boom / 808)',
    'tom': '🥁 Tom Resonante',
    'kick': '🔊 Bombo Acústico (Kick)',
    'snare': '⚡ Caja (Snare)',
    'hihat': '🎩 Charles Cerrado (Hi-Hat)',
    'openhat': '🛎️ Charles Abierto (Open Hat)',
    'clap': '👏 Palmas (Clap)',
    'ride': '💿 Plato (Ride / Crash)',
    'tink': '🔔 Tink Percusión'
}

DRUM_VOICE_SHORT = {
    '__melodic__': 'Nota',
    'boom': 'Sub',
    'tom': 'Tom',
    'kick': 'Kick',
    'snare': 'Caja',
    'hihat': 'Hat',
    'openhat': 'Open',
    'clap': 'Clap',
    'ride': 'Ride',
    'tink': 'Tink'
}

SOUNDSCAPE_PRESETS = {
    'catedral': {
        'label': '⛪ Catedral Profunda',
        'timbre': 'organ-cathedral',
        'root': 'D',
        'octave': 2,
        'harmony': 'dorian',
        'n_pendulums': 6,
        'voicing': 'open',
        'bpm': 48.0,
        'rhythm_mode': 'gaps',
        'duration_mode': 'drone',
        'decay': 1.6,
        'dynamic_mode': 'crescendo',
        'strike_mode': 'bilateral',
        'strike_pattern': '1+1',
        'fill_palette': 'power_fifths',
    },
    'drone': {
        'label': '🌌 Drone Cósmico',
        'timbre': 'organ-drone',
        'root': 'C',
        'octave': 2,
        'harmony': 'sus4_ambient',
        'n_pendulums': 5,
        'voicing': 'open',
        'bpm': 36.0,
        'rhythm_mode': 'gaps',
        'duration_mode': 'paisaje',
        'decay': 1.8,
        'dynamic_mode': 'unison',
        'strike_mode': 'unison',
        'strike_pattern': '1+0',
        'fill_palette': 'unison',
    },
    'cristal': {
        'label': '✨ Cristal Etéreo',
        'timbre': 'organ-glass',
        'root': 'F',
        'octave': 3,
        'harmony': 'lydian',
        'n_pendulums': 7,
        'voicing': 'open',
        'bpm': 54.0,
        'rhythm_mode': 'wave',
        'duration_mode': 'legato',
        'decay': 1.5,
        'dynamic_mode': 'crescendo',
        'strike_mode': 'bilateral',
        'strike_pattern': '1+1',
        'fill_palette': 'chord_arpeggio',
    },
    'armonio': {
        'label': '🌬️ Armonio Meditativo',
        'timbre': 'organ-harmonium',
        'root': 'E',
        'octave': 2,
        'harmony': 'hirojoshi',
        'n_pendulums': 5,
        'voicing': 'linear',
        'bpm': 44.0,
        'rhythm_mode': 'gaps',
        'duration_mode': 'legato',
        'decay': 1.4,
        'dynamic_mode': 'delicado',
        'strike_mode': 'bilateral',
        'strike_pattern': '1+1',
        'fill_palette': 'scale_step',
    },
    'hammond': {
        'label': '🎹 Niebla Hammond',
        'timbre': 'organ-hammond',
        'root': 'A',
        'octave': 2,
        'harmony': 'chord_min9',
        'n_pendulums': 6,
        'voicing': 'open',
        'bpm': 58.0,
        'rhythm_mode': 'wave',
        'duration_mode': 'tenuto',
        'decay': 1.4,
        'dynamic_mode': 'accent_bar',
        'strike_mode': 'bilateral',
        'strike_pattern': '1+1',
        'fill_palette': 'chord_arpeggio',
    },
    'sinfonia_mix': {
        'label': '🎼 Sinfonía Multi-Órgano (Mix)',
        'timbre': 'organ-paisaje-mix',
        'root': 'D',
        'octave': 2,
        'harmony': 'chord_maj9',
        'n_pendulums': 6,
        'voicing': 'open',
        'bpm': 42.0,
        'rhythm_mode': 'gaps',
        'duration_mode': 'paisaje',
        'decay': 1.6,
        'dynamic_mode': 'crescendo',
        'strike_mode': 'bilateral',
        'strike_pattern': '1+1',
        'fill_palette': 'chord_arpeggio',
    },
}

class PendulumApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Pendulum Polyphony - Harmonic Studio & Live Keyboard Instrument")
        self.root.geometry("1240x880")
        self.root.minsize(1050, 720)
        self.root.configure(bg="#0f1117")

        # Audio Engine
        self.audio_engine = LiveAudioEngine()

        # Performance & Animation state
        self.is_live_active = False
        self.is_recording = False
        self.anim_time = 0.0
        self.last_wall_time = time.time()
        self.active_flashes = {}
        self.pilot_flashes = {}
        self.pendulum_impulses = {}  # Visual boost when user presses 1-0
        self.pressed_keys_ui = {}
        self.last_cross_states = {}

        # Key-Hold & Real-Time Articulation State
        self.held_notes = {}  # key_id -> dict(start_time, channel, rec_ev, row_type, char)
        self.pending_releases = {}  # key_id -> after_id for OS key-repeat debounce
        self.sustain_pedal_active = False
        self.sustained_channels = []

        # Quantized Melodic Solo Lead State (Beat-synced & Bar-aligned)
        self.solo_held_keys = set()           # Keys physically pressed ('a', 's', ...)
        self.solo_queued_triggers = {}        # Keys waiting for the next beat to trigger
        self.solo_active_notes = {}           # Currently sounding solo notes: key -> dict(channel, rec_ev, start_beat_total, ...)
        self.last_total_beat = -1             # Beat clock progression tracker

        # Live Performance Modal Keyboard State (AA Chords & AE Rhythm Modes)
        self.keyboard_mode = "normal"         # "normal", "chords_aa", "rhythm_ae"
        self.last_key_press_char = None       # Char of last press for sequence detection
        self.last_key_press_time = 0.0        # Timestamp of last key press
        self.active_chord_degree = 0          # Active degree (0 to 6, I to VII)
        self.active_chord_inversion = 0       # 0=Root, 1=1st inv, 2=2nd inv
        self.active_chord_seventh = False     # Whether 7th is added
        self.strum_retrograde = False         # Whether return pass reverses pitch order (melodic mirror)
        self.strum_target_mode = "all"        # "all", "even", "odd", "single"
        self.strum_speed_factor = 1.0         # Global strum speed factor / span multiplier (0.4x to 2.8x)
        self.strum_evolving_mode = "off"      # Dynamic evolution across passes: "off", "accel", "decel", "breathe"
        self.ball_cross_count = {}            # ball_index -> count of crossings (for evolving accel/decel)
        self.mode_banner_text = ""            # Live banner text on screen

        # Individual Ball Silence / Timed Mutes & Custom Overrides
        self.pendulum_mutes = {}              # ball_index -> mute_until_anim_time
        self.silence_bars_var = tk.StringVar(value="2")  # "1", "2", "4", "8", or "Permanente"
        self.space_silence_active: bool = False
        self.space_silence_until: float = 0.0
        self._pre_space_mutes: Dict[int, float] = {}
        self._last_pause_btn_state: Optional[Tuple[str, str, str]] = None
        self.ball_custom_dynamics = {}        # ball_index -> dynamic_mode (str)
        self.ball_custom_durations = {}       # ball_index -> duration_mode (str)
        self.ball_custom_strikes = {}         # ball_index -> (ida: int, vuelta: int) or (steps_left, steps_right)
        self.ball_custom_palettes = {}        # ball_index -> palette_key (str)
        self.ball_custom_strum_ratio = {}     # ball_index -> float progression ratio (0.60 to 1.50)
        self.ball_custom_strum_sens = {}      # ball_index -> float accent sensitivity (0.0 to 1.0)
        self.ball_custom_drum_voices = {}     # ball_index -> voice_key (str) e.g. 'boom', 'tom', etc.
        self.ball_strike_counts = {}          # ball_index -> sequential strike counter (int)
        self.ball_wait_for_ida: Dict[int, bool] = {}  # ball_index -> wait for ◄ IDA before starting scale run
        self.canvas_bob_coords = {}           # ball_index -> (rx1, ry1, rx2, ry2) for mouse clicks
        self.canvas_pilot_coords = {}         # (ball_idx, side, step_idx) -> (px1, py1, px2, py2)

        # Backing Track (WAV / MP3) State
        self.backing_track_path = None
        self.backing_loop_var = tk.BooleanVar(value=True)
        self.space_stops_backing_var = tk.BooleanVar(value=False)
        self.backing_manually_paused: bool = False
        self._backing_paused_by_space: bool = False
        self.backing_volume_var = tk.DoubleVar(value=0.8)
        self.synth_volume_var = tk.DoubleVar(value=1.0)
        self.backing_track_name_var = tk.StringVar(value="(Sin pista)")
        self.canvas_mute_coords = {}          # ball_idx -> (mx1, my1, mx2, my2)

        # Drum Machine Matrix & Permanent Properties State
        self.selected_ball_idx = 0
        self.matrix_step_buttons = {}         # (ball_idx, side, step_idx) -> tk.Button
        self.matrix_vox_buttons = {}          # ball_idx -> tk.Button
        self.matrix_mute_buttons = {}         # ball_idx -> tk.Button
        self.matrix_step_flash_resets = {}    # (ball_idx, side, step_idx) -> after_id

        # Harmonic & Metric variables
        self.root_key_var = tk.StringVar(value="E")
        self.octave_var = tk.IntVar(value=2)
        self.harmony_type_var = tk.StringVar(value="minor_harmonic")
        self.voicing_var = tk.StringVar(value="linear")
        self.time_sig_var = tk.StringVar(value="4/4")
        self.duration_mode_var = tk.StringVar(value="auto")

        # General parameters
        self.timbre_var = tk.StringVar(value="piano")
        self.decay_var = tk.DoubleVar(value=1.0)
        self.strike_mode_var = tk.StringVar(value="bilateral")
        self.strike_pattern_var = tk.StringVar(value="1+1")
        self.fill_palette_var = tk.StringVar(value="chord_arpeggio")
        self.rhythm_mode_var = tk.StringVar(value="sync")
        self.view_mode_var = tk.StringVar(value="uniform")
        self.dynamic_mode_var = tk.StringVar(value="accent_bar")
        self.strum_progression_var = tk.StringVar(value="uniform")
        self.strum_sensitivity_var = tk.StringVar(value="med")
        self.n_pendulums_var = tk.IntVar(value=2)
        self.duration_var = tk.IntVar(value=30)
        self.bpm_var = tk.DoubleVar(value=96.0)
        self.multitrack_var = tk.BooleanVar(value=True)

        # Pitch-Follower & Chromatic Piano Keyboard State
        self.pitch_follow = PitchFollowController(
            root_midi=note_name_to_midi(self.root_key_var.get(), self.octave_var.get())
        )
        self.follow_transition_var = tk.StringVar(value="immediate")
        self.keyboard_sound_mode_var = tk.StringVar(value="hold")
        self.keyboard_sound_last_active_mode = "hold"
        self.kb_link_accompaniment_var = tk.BooleanVar(value=True)
        self.kb_timbre_var = tk.StringVar(value="")
        self.kb_decay_follow_var = tk.BooleanVar(value=True)
        self.kb_decay_var = tk.DoubleVar(value=1.0)
        self.kb_duration_mode_var = tk.StringVar(value="auto")
        self.kb_octave_offset_var = tk.IntVar(value=0)
        self.kb_volume_var = tk.DoubleVar(value=1.0)
        self.kb_pan_var = tk.DoubleVar(value=0.0)
        self._kb_props_win: Optional[tk.Toplevel] = None
        self.follow_key_voices: Dict[str, Dict[str, Any]] = {}
        self.mode_buttons: Dict[str, tk.Button] = {}
        self.held_transpose_keys = set()
        self.piano_key_labels: Dict[str, tk.Label] = {}
        self.active_chord_pitches: List[int] = []
        self.sounding_pendulum_pitches: Dict[int, float] = {}
        self._last_piano_red_state: Optional[Tuple[frozenset, frozenset, frozenset]] = None
        self._last_unmuted_balls: Tuple[int, ...] = ()
        self.chord_play_mode_var = tk.StringVar(value="off")
        self.chord_target_var = tk.StringVar(value="both")
        self.chord_quality_var = tk.StringVar(value="diatonic")
        self.chord_add_seventh_var = tk.BooleanVar(value=False)
        self.active_chord_label: str = ""
        self.chord_mode_buttons: Dict[str, tk.Button] = {}
        self.pending_strum_after_ids: List[str] = []
        self.pending_step_after_ids: List[str] = []
        self.is_finishing_recording: bool = False
        self._rec_finish_after_id: Optional[str] = None
        self._rec_stop_wall_time: float = 0.0
        self._rec_stop_offset_sec: Optional[float] = None
        self.matrix_len_buttons: Dict[Tuple[int, str], tk.Button] = {}

        self._build_ui()
        self._init_system(update_follow_home=True, recenter_keyboard=True)
        self._bind_keyboard()
        self._animate()

    def _get_effective_ball_palette(self, ball_idx: int) -> str:
        return self.ball_custom_palettes.get(ball_idx, self.fill_palette_var.get())

    def _arm_scale_run_on_ida(self, ball_idx: Optional[int] = None, reset_clock_if_paused: bool = False):
        if not hasattr(self, 'system'):
            return
        targets = range(self.system.n_pendulums) if ball_idx is None else [ball_idx]
        for b in targets:
            self.ball_strike_counts[b] = 0
            self.ball_wait_for_ida[b] = is_scale_run_palette(self._get_effective_ball_palette(b))
        if reset_clock_if_paused and not self.is_live_active:
            self.anim_time = 0.0
            self.last_total_beat = -1
            self.last_cross_states = {
                k: (p.angle_at(0.0) >= 0.0)
                for k, p in enumerate(self.system.pendulums)
            }

    def _init_system(self, update_follow_home: bool = False, recenter_keyboard: bool = False):
        """Initializes or updates the pendulum physical and harmonic model."""
        if hasattr(self, 'pending_strum_after_ids'):
            self._cancel_pending_strum_afters()
        if hasattr(self, 'follow_key_voices'):
            self._stop_all_follow_key_voices()
        self.system = PendulumSystem(
            root_key=self.root_key_var.get(),
            base_octave=self.octave_var.get(),
            harmony_type=self.harmony_type_var.get(),
            n_pendulums=self.n_pendulums_var.get(),
            rhythm_mode=self.rhythm_mode_var.get(),
            strike_mode=self.strike_mode_var.get(),
            strike_pattern=self.strike_pattern_var.get(),
            fill_palette=self.fill_palette_var.get(),
            tempo_bpm=float(self.bpm_var.get()),
            voicing=self.voicing_var.get(),
            time_signature=self.time_sig_var.get(),
            note_duration_mode=self.duration_mode_var.get(),
            dynamic_mode=self.dynamic_mode_var.get()
        )
        self.system.custom_ball_strikes = dict(self.ball_custom_strikes)
        self.system.custom_ball_dynamics = dict(self.ball_custom_dynamics)
        self.system.custom_ball_durations = dict(self.ball_custom_durations)
        self.system.custom_ball_palettes = dict(self.ball_custom_palettes)
        self.system.strum_progression_ratio = STRUM_PROGRESSIONS.get(self.strum_progression_var.get(), {}).get('ratio', 1.0)
        self.system.strum_accent_sensitivity = STRUM_ACCENT_SENSITIVITIES.get(self.strum_sensitivity_var.get(), {}).get('value', 0.50)
        self.system.custom_ball_strum_ratio = dict(self.ball_custom_strum_ratio)
        self.system.custom_ball_strum_sens = dict(self.ball_custom_strum_sens)
        self.ball_strike_counts = {i: 0 for i in range(self.system.n_pendulums)}
        self.ball_wait_for_ida = {
            i: is_scale_run_palette(self._get_effective_ball_palette(i))
            for i in range(self.system.n_pendulums)
        }
        self.audio_engine.set_timbre(self.timbre_var.get())
        self.active_flashes = {i: 0 for i in range(self.system.n_pendulums)}
        self.pilot_flashes = {
            i: {'left': [0] * MAX_PATTERN_STEPS, 'right': [0] * MAX_PATTERN_STEPS, 'last_dir': 'right'}
            for i in range(self.system.n_pendulums)
        }
        self.pendulum_impulses = {i: 0.0 for i in range(self.system.n_pendulums)}
        if not self.is_live_active:
            self.anim_time = 0.0
            self.last_total_beat = -1
        self.last_cross_states = {
            i: (p.angle_at(self.anim_time) >= 0.0)
            for i, p in enumerate(self.system.pendulums)
        }
        if hasattr(self, 'pitch_follow'):
            root_midi = note_name_to_midi(self.root_key_var.get(), self.octave_var.get())
            self.pitch_follow.sync_external_root(
                root_midi,
                update_home=update_follow_home,
                recenter_keyboard=recenter_keyboard,
            )
            self._update_follow_indicator()
        self.active_chord_pitches = []
        self.sounding_pendulum_pitches.clear()
        self._last_piano_red_state = None
        self._last_unmuted_balls = ()
        if hasattr(self, 'chord_play_mode_var'):
            if self._is_chord_enabled_for_accompaniment():
                pitches, cname = self._resolve_chord_for_midi(
                    self.pitch_follow.active_midi, for_strum=False
                )
                self.system.chord_play_mode = self.chord_play_mode_var.get()
                self.system.set_chord_pitches_inplace(
                    self.root_key_var.get(),
                    self.octave_var.get(),
                    pitches,
                )
                self.active_chord_pitches = list(pitches)
                self.active_chord_label = cname
            elif self._is_chord_enabled_for_keyboard():
                _, cname = self._resolve_chord_for_midi(self.pitch_follow.active_midi)
                self.active_chord_label = cname
            else:
                self.active_chord_label = ""
            self._update_chord_controls()
            self._update_follow_indicator()
        if hasattr(self, 'btn_kb_props'):
            self._update_kb_props_button()
        self._update_hud_info()
        self._update_keyboard_labels()
        if hasattr(self, 'matrix_rows_frame'):
            self._build_drum_matrix_rows()
            self._sync_side_panel_controls()

    def _build_ui(self):
        # 1. Header Bar (pack right_header FIRST so Rec stays pinned inside the window)
        header = tk.Frame(self.root, bg="#161922", pady=4, padx=10)
        header.pack(fill=tk.X)

        right_header = tk.Frame(header, bg="#161922")
        right_header.pack(side=tk.RIGHT)

        self.follow_indicator = tk.Label(
            right_header,
            text="🎹 E2 (0st)",
            font=("Segoe UI", 9, "bold"),
            fg="#00f5d4",
            bg="#161922"
        )
        self.follow_indicator.pack(side=tk.LEFT, padx=(0, 6))

        self.rec_indicator = tk.Label(
            right_header,
            text="● OFF",
            font=("Segoe UI", 9, "bold"),
            fg="#64748b",
            bg="#161922"
        )
        self.rec_indicator.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_live_rec = tk.Button(
            right_header,
            text="🔴 Rec",
            font=("Segoe UI", 8, "bold"),
            bg="#ef4444",
            fg="#ffffff",
            activebackground="#dc2626",
            activeforeground="#fff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._toggle_live_recording
        )
        self.btn_live_rec.pack(side=tk.LEFT)

        title_frame = tk.Frame(header, bg="#161922")
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        title_label = tk.Label(
            title_frame,
            text="PENDULUM STUDIO",
            font=("Segoe UI", 11, "bold"),
            fg="#00f5d4",
            bg="#161922"
        )
        title_label.pack(side=tk.LEFT)

        self.harmony_badge = tk.Label(
            title_frame,
            text="[E2 • 4/4 • Menor Armónica]",
            font=("Segoe UI", 9, "bold"),
            fg="#ffd166",
            bg="#161922",
            anchor="w"
        )
        self.harmony_badge.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        # 1.5 Dedicated Backing Track & Master Mixer Toolbar (Always 100% visible across full window width)
        self.backing_bar = tk.Frame(self.root, bg="#111624", padx=8, pady=3, bd=1, relief=tk.SOLID)
        self.backing_bar.pack(fill=tk.X, padx=14, pady=(2, 4))

        self.btn_import_backing = tk.Button(
            self.backing_bar,
            text="📁 Importar",
            font=("Segoe UI", 8, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=6,
            pady=1,
            cursor="hand2",
            command=self._choose_backing_track
        )
        self.btn_import_backing.pack(side=tk.LEFT, padx=(0, 3))

        self.lbl_backing_name = tk.Label(
            self.backing_bar,
            textvariable=self.backing_track_name_var,
            font=("Segoe UI", 8, "italic"),
            fg="#64748b",
            bg="#111624"
        )
        self.lbl_backing_name.pack(side=tk.LEFT, padx=(0, 4))

        # Independent Play / Pause button for Imported Track
        self.btn_backing_play = tk.Button(
            self.backing_bar,
            text="▶ Pista",
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b",
            fg="#64748b",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            state=tk.DISABLED,
            command=self._toggle_backing_play
        )
        self.btn_backing_play.pack(side=tk.LEFT, padx=(0, 3))

        # Loop Toggle Button (Distinct Green/Dark, clearly labeled)
        self.btn_backing_loop = tk.Button(
            self.backing_bar,
            text="🔁 Loop: SÍ",
            font=("Segoe UI", 8, "bold"),
            bg="#065f46",
            fg="#6ee7b7",
            activebackground="#047857",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=self._toggle_backing_loop
        )
        self.btn_backing_loop.pack(side=tk.LEFT, padx=(0, 3))

        # Toggle whether Space also pauses/stops the imported backing track (default: NO)
        self.btn_space_stops_backing = tk.Button(
            self.backing_bar,
            text="Esp→Pista: NO",
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=self._toggle_space_stops_backing
        )
        self.btn_space_stops_backing.pack(side=tk.LEFT, padx=(0, 3))

        # Remove Button
        self.btn_backing_remove = tk.Button(
            self.backing_bar,
            text="✖ Quitar",
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#94a3b8",
            activebackground="#991b1b",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            state=tk.DISABLED,
            command=self._remove_backing_track
        )
        self.btn_backing_remove.pack(side=tk.LEFT, padx=(0, 3))

        tk.Frame(self.backing_bar, bg="#334155", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)

        # Imported Track Master & Produced Sound Master (Side by Side)
        self.lbl_backing_vol = self._create_master_volume_group(
            self.backing_bar,
            label_text="Vol Pista:",
            label_fg="#38bdf8",
            init_text="80%",
            val_fg="#00f5d4",
            adjust_fn=self._adjust_backing_volume,
            cycle_fn=self._cycle_backing_volume,
            right_pad=5,
        )
        self.lbl_synth_vol = self._create_master_volume_group(
            self.backing_bar,
            label_text="🔊 Sonido:",
            label_fg="#ffd166",
            init_text="100%",
            val_fg="#ffd166",
            adjust_fn=self._adjust_synth_volume,
            cycle_fn=self._cycle_synth_volume,
            right_pad=4,
        )

        # Status / Help Text
        self.lbl_backing_status = tk.Label(
            self.backing_bar,
            text="● Sin pista",
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#111624"
        )
        self.lbl_backing_status.pack(side=tk.RIGHT)

        # 2. Main Visualization Canvas & Permanent Drum Machine Matrix Panel
        middle_container = tk.Frame(self.root, bg="#0b0d12")
        middle_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=(2, 6))

        self.canvas = tk.Canvas(middle_container, bg="#0b0d12", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.side_panel = tk.Frame(middle_container, bg="#131622", width=404, padx=6, pady=6, bd=1, relief=tk.SOLID)
        self.side_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        self.side_panel.pack_propagate(False)

        def _on_canvas_click(event):
            self.canvas.focus_set()

        self.canvas.bind("<Button-1>", _on_canvas_click)

        self._build_permanent_side_panel()

        # 3. Interactive Virtual Keyboard Strip (Mode Bar + 4 Dedicated Rows)
        self.keyboard_frame = tk.Frame(self.root, bg="#13161f", padx=12, pady=5)
        self.keyboard_frame.pack(fill=tk.X, padx=14, pady=(0, 6))

        # Row 0: Keyboard Mode Selector Bar (F1-F5) + Live Sound & Transition Controls
        row_modes = tk.Frame(self.keyboard_frame, bg="#13161f")
        row_modes.pack(fill=tk.X, pady=(0, 3))
        tk.Label(
            row_modes,
            text="Modo [F1-F5]:",
            font=("Segoe UI", 8, "bold"),
            fg="#94a3b8",
            bg="#13161f",
            width=16,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.mode_buttons = {}
        mode_defs = [
            ("normal", "[F1] Piano", self._exit_keyboard_mode),
            ("chords_aa", "[F2] Acordes", lambda: self._toggle_keyboard_mode("chords_aa")),
            ("accent_ss", "[F3] Acentos", lambda: self._toggle_keyboard_mode("accent_ss")),
            ("strum_dd", "[F4] Patrón", lambda: self._toggle_keyboard_mode("strum_dd")),
            ("accel_ff", "[F5] Acel", lambda: self._toggle_keyboard_mode("accel_ff")),
        ]
        for m_key, m_txt, m_cmd in mode_defs:
            btn = tk.Button(
                row_modes,
                text=m_txt,
                font=("Segoe UI", 8, "bold"),
                bg="#1e293b",
                fg="#cbd5e1",
                activebackground="#0284c7",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=5,
                pady=1,
                cursor="hand2",
                command=m_cmd
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.mode_buttons[m_key] = btn

        ctrl_right = tk.Frame(row_modes, bg="#13161f")
        ctrl_right.pack(side=tk.RIGHT)

        self.btn_kb_sound = tk.Button(
            ctrl_right,
            text="🔊 Teclado",
            font=("Segoe UI", 8, "bold"),
            bg="#065f46",
            fg="#6ee7b7",
            activebackground="#047857",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=self._toggle_keyboard_sound
        )
        self.btn_kb_sound.pack(side=tk.LEFT, padx=(0, 3))

        self.kb_sound_combo = ttk.Combobox(
            ctrl_right,
            values=[v["name"] for v in KEYBOARD_SOUND_MODES.values()],
            state="readonly",
            width=16
        )
        self.kb_sound_combo.current(0)
        self.kb_sound_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.kb_sound_combo.bind("<<ComboboxSelected>>", self._on_kb_sound_mode_selected)

        tk.Label(
            ctrl_right,
            text="Cambio:",
            font=("Segoe UI", 8, "bold"),
            fg="#94a3b8",
            bg="#13161f"
        ).pack(side=tk.LEFT, padx=(0, 3))
        self.follow_transition_combo = ttk.Combobox(
            ctrl_right,
            values=[v["name"] for v in FOLLOW_TRANSITION_MODES.values()],
            state="readonly",
            width=15
        )
        self.follow_transition_combo.current(0)
        self.follow_transition_combo.pack(side=tk.LEFT)
        self.follow_transition_combo.bind("<<ComboboxSelected>>", self._on_follow_transition_selected)

        # Row 0b: Chord & Strum Companion Controls
        row_chord = tk.Frame(self.keyboard_frame, bg="#13161f")
        row_chord.pack(fill=tk.X, pady=(0, 2))
        tk.Label(
            row_chord,
            text="🎸 Acordes:",
            font=("Segoe UI", 8, "bold"),
            fg="#fb7185",
            bg="#13161f",
            width=16,
            anchor="w"
        ).pack(side=tk.LEFT)

        self.chord_mode_buttons = {}
        chord_btn_defs = [
            ("off", "🎵 Nota"),
            ("block", "🎹 Acorde"),
            ("strum", "🎸 Rasgueo"),
        ]
        for cm_key, cm_txt in chord_btn_defs:
            btn = tk.Button(
                row_chord,
                text=cm_txt,
                font=("Segoe UI", 8, "bold"),
                bg="#1e293b",
                fg="#cbd5e1",
                activebackground="#e11d48",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=5,
                pady=1,
                cursor="hand2",
                command=lambda k_mode=cm_key: self._set_chord_play_mode(k_mode)
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.chord_mode_buttons[cm_key] = btn

        tk.Label(
            row_chord,
            text="En:",
            font=("Segoe UI", 8, "bold"),
            fg="#94a3b8",
            bg="#13161f"
        ).pack(side=tk.LEFT, padx=(8, 3))
        self.chord_target_combo = ttk.Combobox(
            row_chord,
            values=[v["name"] for v in CHORD_TARGET_MODES.values()],
            state="readonly",
            width=15
        )
        self.chord_target_combo.current(0)
        self.chord_target_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.chord_target_combo.bind("<<ComboboxSelected>>", self._on_chord_target_selected)

        tk.Label(
            row_chord,
            text="Tipo:",
            font=("Segoe UI", 8, "bold"),
            fg="#94a3b8",
            bg="#13161f"
        ).pack(side=tk.LEFT, padx=(0, 3))
        self.chord_quality_combo = ttk.Combobox(
            row_chord,
            values=[v["name"] for v in CHORD_QUALITY_MODES.values()],
            state="readonly",
            width=16
        )
        self.chord_quality_combo.current(0)
        self.chord_quality_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.chord_quality_combo.bind("<<ComboboxSelected>>", self._on_chord_quality_selected)

        self.btn_chord_7th = tk.Button(
            row_chord,
            text="+7ª",
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b",
            fg="#94a3b8",
            activebackground="#4a154b",
            activeforeground="#38bdf8",
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=self._toggle_chord_seventh
        )
        self.btn_chord_7th.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_chord_badge = tk.Label(
            row_chord,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg="#fb7185",
            bg="#13161f"
        )
        self.lbl_chord_badge.pack(side=tk.LEFT, padx=(2, 0))

        # Row 1: Number Keys (1-0) -> Timed Ball Silence & Mute Controls
        row_num = tk.Frame(self.keyboard_frame, bg="#13161f")
        row_num.pack(fill=tk.X, pady=1)
        self.lbl_num_title = tk.Label(row_num, text="[1-0] Silenciar:", font=("Segoe UI", 8, "bold"), fg="#f87171", bg="#13161f", width=16, anchor="w")
        self.lbl_num_title.pack(side=tk.LEFT)
        self.num_labels = {}
        for idx, k in enumerate(["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]):
            lbl = tk.Label(
                row_num,
                text=f"[{k}] P{idx+1}",
                font=("Consolas", 8, "bold"),
                fg="#93c5fd",
                bg="#1e2230",
                padx=4,
                pady=1,
                cursor="hand2",
                relief=tk.RAISED,
                bd=1
            )
            lbl.pack(side=tk.LEFT, padx=1)
            lbl.bind("<Button-1>", lambda e, b_idx=idx: self._on_num_button_click(b_idx))
            lbl.bind("<Button-3>", lambda e, b_idx=idx: self._on_num_button_right_click(e, b_idx))
            self.num_labels[k] = lbl

        tk.Label(row_num, text=" | Tiempo:", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#13161f").pack(side=tk.LEFT, padx=(4, 1))
        silence_combo = ttk.Combobox(
            row_num,
            textvariable=self.silence_bars_var,
            values=["1", "2", "4", "8", "Permanente"],
            state="readonly",
            width=9
        )
        silence_combo.pack(side=tk.LEFT, padx=(1, 2))
        silence_combo.bind("<<ComboboxSelected>>", self._on_silence_bars_changed)

        self.btn_kb_props = tk.Button(
            row_num,
            text="🎹 Props",
            font=("Segoe UI", 8),
            bg="#252b3b",
            fg="#38bdf8",
            relief=tk.FLAT,
            padx=4,
            pady=0,
            cursor="hand2",
            command=self._open_keyboard_props_dialog
        )
        self.btn_kb_props.pack(side=tk.LEFT, padx=(2, 2))

        # Row 2: Top Letter Keys (Q-P) -> Chromatic Piano Black Keys (#) / Alternate Mode Controls
        row_qp = tk.Frame(self.keyboard_frame, bg="#13161f")
        row_qp.pack(fill=tk.X, pady=1)
        self.lbl_qp_title = tk.Label(row_qp, text="[Q-P] Negras (#):", font=("Segoe UI", 8, "bold"), fg="#c084fc", bg="#13161f", width=16, anchor="w")
        self.lbl_qp_title.pack(side=tk.LEFT)
        self.qp_labels = {}
        self.piano_key_labels = {}
        for key_id, offset in PIANO_TOP_ROW_SLOTS:
            is_gap = (offset is None)
            lbl = tk.Label(
                row_qp,
                text="" if is_gap else f"[{key_id}]",
                font=("Consolas", 8, "bold"),
                width=7,
                fg="#334155" if is_gap else "#c084fc",
                bg="#13161f" if is_gap else "#12151f",
                padx=2,
                pady=1,
                cursor="" if is_gap else "hand2",
                relief=tk.FLAT if is_gap else tk.RAISED,
                bd=1,
                highlightthickness=1,
                highlightbackground="#13161f"
            )
            lbl.pack(side=tk.LEFT, padx=2)
            lbl.bind("<ButtonPress-1>", lambda e, kid=key_id: self._on_qp_slot_press(kid))
            lbl.bind("<ButtonRelease-1>", lambda e, kid=key_id: self._on_qp_slot_release(kid))
            self.qp_labels[key_id] = lbl
            if not is_gap:
                self.piano_key_labels[key_id] = lbl

        # Row 3: Middle Letter Keys (A-Ñ) -> Chromatic Piano White Keys / Alternate Mode Controls
        row_al = tk.Frame(self.keyboard_frame, bg="#13161f")
        row_al.pack(fill=tk.X, pady=1)
        self.lbl_al_title = tk.Label(row_al, text="[A-Ñ] Blancas:", font=("Segoe UI", 8, "bold"), fg="#34d399", bg="#13161f", width=16, anchor="w")
        self.lbl_al_title.pack(side=tk.LEFT)
        piano_indent = tk.Frame(row_al, width=24, height=1, bg="#13161f")
        piano_indent.pack(side=tk.LEFT)
        piano_indent.pack_propagate(False)
        self.al_labels = {}
        for key_id, _offset in PIANO_WHITE_ROW_SLOTS:
            lbl = tk.Label(
                row_al,
                text=f"[{key_id}]",
                font=("Consolas", 8, "bold"),
                width=7,
                fg="#f1f5f9",
                bg="#232d3f",
                padx=2,
                pady=1,
                cursor="hand2",
                relief=tk.RAISED,
                bd=1,
                highlightthickness=1,
                highlightbackground="#13161f"
            )
            lbl.pack(side=tk.LEFT, padx=2)
            lbl.bind("<ButtonPress-1>", lambda e, kid=key_id: self._on_al_slot_press(kid))
            lbl.bind("<ButtonRelease-1>", lambda e, kid=key_id: self._on_al_slot_release(kid))
            self.al_labels[key_id] = lbl
            self.piano_key_labels[key_id] = lbl

        self.lbl_al_hint = tk.Label(
            row_al,
            text="🎯 Tono + Sonido (Hold)",
            font=("Segoe UI", 8, "italic"),
            fg="#059669",
            bg="#13161f"
        )
        self.lbl_al_hint.pack(side=tk.LEFT, padx=8)

        # Row 4: Bottom Keys (Z-.) -> Interval Transposition / Randoms / Span
        row_zm = tk.Frame(self.keyboard_frame, bg="#13161f")
        row_zm.pack(fill=tk.X, pady=1)
        self.lbl_zm_title = tk.Label(row_zm, text="[Z-.] Transponer:", font=("Segoe UI", 8, "bold"), fg="#14b8a6", bg="#13161f", width=16, anchor="w")
        self.lbl_zm_title.pack(side=tk.LEFT)
        self.zm_labels = {}
        for key_id in TRANSPOSE_ROW_KEYS:
            lbl = tk.Label(
                row_zm,
                text=f"[{key_id}]",
                font=("Consolas", 8, "bold"),
                fg="#5eead4",
                bg="#132e2b",
                padx=3,
                pady=1,
                cursor="hand2",
                relief=tk.RAISED,
                bd=1
            )
            lbl.pack(side=tk.LEFT, padx=1)
            lbl.bind("<Button-1>", lambda e, kid=key_id: self._on_zm_slot_click(kid))
            self.zm_labels[key_id] = lbl

        self.btn_third_mode = tk.Button(
            row_zm,
            text="3ª: Auto (3st)",
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b",
            fg="#38bdf8",
            activebackground="#0284c7",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=6,
            pady=1,
            cursor="hand2",
            command=self._cycle_third_mode
        )
        self.btn_third_mode.pack(side=tk.LEFT, padx=(6, 4))

        self.lbl_transpose_status = tk.Label(
            row_zm,
            text="C2–E3 (0st)",
            font=("Segoe UI", 8, "bold"),
            fg="#ffd166",
            bg="#13161f"
        )
        self.lbl_transpose_status.pack(side=tk.LEFT, padx=(4, 0))

        # Row 5: Global Hotkeys Hint Bar
        row_hints = tk.Frame(self.keyboard_frame, bg="#13161f")
        row_hints.pack(fill=tk.X, pady=(2, 0))
        tk.Label(row_hints, text="[Atajos Globales]:", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#13161f", width=16, anchor="w").pack(side=tk.LEFT)
        hints_text = "⏯ [Espacio] Play • 🎹 [A-Ñ/W-P] Tono+Sonido • [F1-F5] Modos/Patrón • [ESC] Piano • [Z-.] Transponer • [1-0] Mute/Bola (0=Todas)"
        tk.Label(row_hints, text=hints_text, font=("Segoe UI", 8), fg="#94a3b8", bg="#13161f").pack(side=tk.LEFT, padx=2)

        # 4. Controls & Harmonic Settings Panel (3 Clean Compact Rows)
        controls_frame = tk.Frame(self.root, bg="#161922", padx=12, pady=6)
        controls_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=14, pady=(0, 6))

        # Row 0: Harmony, Metric & Timbre controls
        row0 = tk.Frame(controls_frame, bg="#161922")
        row0.pack(fill=tk.X, pady=(0, 4))

        # Compás / Time Signature Selector
        tk.Label(row0, text="Compás:", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        sig_combo = ttk.Combobox(
            row0,
            textvariable=self.time_sig_var,
            values=list(TIME_SIGNATURES.keys()),
            state="readonly",
            width=5
        )
        sig_combo.pack(side=tk.LEFT, padx=(0, 8))
        sig_combo.bind("<<ComboboxSelected>>", lambda e: self._on_control_selected())

        # Root Key Selector
        tk.Label(row0, text="Key:", font=("Segoe UI", 8, "bold"), fg="#ffd166", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        btn_key_dn = tk.Button(row0, text="◀", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._modulate_key(-1))
        btn_key_dn.pack(side=tk.LEFT, padx=1)
        key_combo = ttk.Combobox(
            row0,
            textvariable=self.root_key_var,
            values=NOTE_NAMES,
            state="readonly",
            width=3
        )
        key_combo.pack(side=tk.LEFT, padx=2)
        key_combo.bind("<<ComboboxSelected>>", lambda e: self._on_root_key_selected())
        btn_key_up = tk.Button(row0, text="▶", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._modulate_key(+1))
        btn_key_up.pack(side=tk.LEFT, padx=(1, 8))

        # Octave
        tk.Label(row0, text="Oct:", font=("Segoe UI", 8, "bold"), fg="#ffd166", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        oct_spin = ttk.Spinbox(row0, from_=1, to=5, textvariable=self.octave_var, width=2, command=self._on_octave_selected)
        oct_spin.pack(side=tk.LEFT, padx=(0, 8))

        # Harmony Scale Type
        tk.Label(row0, text="Armonía:", font=("Segoe UI", 8, "bold"), fg="#00f5d4", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        harm_labels = [f"{v['name']}" for v in HARMONIC_TYPES.values()]
        self.harm_combo = ttk.Combobox(
            row0,
            values=harm_labels,
            state="readonly",
            width=20
        )
        self.harm_combo.current(0)
        self.harm_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.harm_combo.bind("<<ComboboxSelected>>", self._on_harmony_selected)

        # Voicing
        tk.Label(row0, text="Voicing:", font=("Segoe UI", 8, "bold"), fg="#cad3f5", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        voicing_combo = ttk.Combobox(
            row0,
            textvariable=self.voicing_var,
            values=["linear", "open"],
            state="readonly",
            width=6
        )
        voicing_combo.pack(side=tk.LEFT, padx=(0, 8))
        voicing_combo.bind("<<ComboboxSelected>>", lambda e: self._on_control_selected())

        # Timbre
        tk.Label(row0, text="Timbre:", font=("Segoe UI", 8, "bold"), fg="#cad3f5", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        self.timbre_combo = ttk.Combobox(
            row0,
            textvariable=self.timbre_var,
            values=self._get_instrument_list(),
            state="readonly",
            width=16
        )
        self.timbre_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.timbre_combo.bind("<<ComboboxSelected>>", lambda e: self._on_timbre_combo())

        # Decay / Seco (Damping control)
        tk.Label(row0, text="Decay:", font=("Segoe UI", 8, "bold"), fg="#cad3f5", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        btn_dec_dn = tk.Button(row0, text="◀", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=2, pady=0, command=lambda: self._adjust_decay(-0.2))
        btn_dec_dn.pack(side=tk.LEFT, padx=1)
        self.decay_label = tk.Label(row0, text=f"{self.decay_var.get():.1f}x", font=("Segoe UI", 8, "bold"), fg="#00f5d4", bg="#161922", width=5)
        self.decay_label.pack(side=tk.LEFT, padx=1)
        btn_dec_up = tk.Button(row0, text="▶", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=2, pady=0, command=lambda: self._adjust_decay(+0.2))
        btn_dec_up.pack(side=tk.LEFT, padx=(1, 4))

        # Row 1: Tempo (BPM), Dynamics, Duration & Ball Count
        row1 = tk.Frame(controls_frame, bg="#161922")
        row1.pack(fill=tk.X, pady=(0, 4))

        # BPM Control
        tk.Label(row1, text="BPM [↑/↓]:", font=("Segoe UI", 8, "bold"), fg="#cad3f5", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        btn_bpm_dn = tk.Button(row1, text="◀", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._adjust_bpm(-1))
        btn_bpm_dn.pack(side=tk.LEFT, padx=1)
        self.bpm_label = tk.Label(row1, text=self._format_bpm(self.bpm_var.get()), font=("Segoe UI", 8, "bold"), fg="#00f5d4", bg="#161922", width=6, cursor="hand2")
        self.bpm_label.pack(side=tk.LEFT, padx=1)
        btn_bpm_up = tk.Button(row1, text="▶", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._adjust_bpm(+1))
        btn_bpm_up.pack(side=tk.LEFT, padx=1)

        btn_bpm_half = tk.Button(
            row1,
            text="/2",
            font=("Segoe UI", 7, "bold"),
            bg="#252b3b",
            fg="#38bdf8",
            relief=tk.FLAT,
            padx=3,
            pady=0,
            cursor="hand2",
            command=self._half_bpm
        )
        btn_bpm_half.pack(side=tk.LEFT, padx=1)

        btn_bpm_double = tk.Button(
            row1,
            text="x2",
            font=("Segoe UI", 7, "bold"),
            bg="#252b3b",
            fg="#38bdf8",
            relief=tk.FLAT,
            padx=3,
            pady=0,
            cursor="hand2",
            command=self._double_bpm
        )
        btn_bpm_double.pack(side=tk.LEFT, padx=(1, 8))

        for w in (self.bpm_label, btn_bpm_dn, btn_bpm_up):
            w.bind("<MouseWheel>", lambda e: self._adjust_bpm(1 if e.delta > 0 else -1))
        self.bpm_label.bind("<Button-1>", self._snap_bpm_integer)
        self.bpm_label.bind("<Button-3>", self._prompt_exact_bpm)
        self.bpm_label.bind("<Double-Button-1>", self._prompt_exact_bpm)

        # Dinámica
        tk.Label(row1, text="Dinámica:", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#161922").pack(side=tk.LEFT, padx=(4, 2))
        btn_dyn_dn = tk.Button(row1, text="◀", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._cycle_dynamic(-1))
        btn_dyn_dn.pack(side=tk.LEFT, padx=1)
        self.dyn_combo = ttk.Combobox(
            row1,
            values=[v['name'] for v in DYNAMIC_MODES.values()],
            state="readonly",
            width=15
        )
        self.dyn_combo.current(0)
        self.dyn_combo.pack(side=tk.LEFT, padx=2)
        self.dyn_combo.bind("<<ComboboxSelected>>", self._on_dynamic_selected)
        btn_dyn_up = tk.Button(row1, text="▶", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._cycle_dynamic(+1))
        btn_dyn_up.pack(side=tk.LEFT, padx=(1, 8))

        # Duración [◄/►]
        tk.Label(row1, text="Duración [◄/►]:", font=("Segoe UI", 8, "bold"), fg="#f472b6", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        btn_dur_dn = tk.Button(row1, text="◀", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._cycle_duration(-1))
        btn_dur_dn.pack(side=tk.LEFT, padx=1)
        self.dur_combo = ttk.Combobox(
            row1,
            values=[f"{v['name']}" for v in NOTE_DURATIONS.values()],
            state="readonly",
            width=12
        )
        self.dur_combo.current(0)
        self.dur_combo.pack(side=tk.LEFT, padx=2)
        self.dur_combo.bind("<<ComboboxSelected>>", self._on_duration_selected)
        btn_dur_up = tk.Button(row1, text="▶", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._cycle_duration(+1))
        btn_dur_up.pack(side=tk.LEFT, padx=(1, 8))

        # Balls count
        tk.Label(row1, text="Bolas [+/-]:", font=("Segoe UI", 8, "bold"), fg="#cad3f5", bg="#161922").pack(side=tk.LEFT, padx=(0, 2))
        btn_balls_dn = tk.Button(row1, text="◀", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._adjust_pendulums(-1))
        btn_balls_dn.pack(side=tk.LEFT, padx=1)
        balls_spin = ttk.Spinbox(row1, from_=1, to=20, textvariable=self.n_pendulums_var, width=3, command=self._on_control_selected)
        balls_spin.pack(side=tk.LEFT, padx=1)
        btn_balls_up = tk.Button(row1, text="▶", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", relief=tk.FLAT, padx=3, pady=0, command=lambda: self._adjust_pendulums(+1))
        btn_balls_up.pack(side=tk.LEFT, padx=(1, 6))

        # Strum Progression Ratio (Global)
        tk.Label(row1, text="Rasgueo:", font=("Segoe UI", 8, "bold"), fg="#fb923c", bg="#161922").pack(side=tk.LEFT, padx=(4, 2))
        strum_p_vals = [v['name'] for v in STRUM_PROGRESSIONS.values()]
        self.strum_prog_combo = ttk.Combobox(
            row1,
            values=strum_p_vals,
            state="readonly",
            width=15
        )
        prog_keys = list(STRUM_PROGRESSIONS.keys())
        self.strum_prog_combo.current(prog_keys.index("uniform") if "uniform" in prog_keys else 0)
        self.strum_prog_combo.pack(side=tk.LEFT, padx=1)
        self.strum_prog_combo.bind("<<ComboboxSelected>>", self._on_global_strum_prog_selected)

        # Strum Accent Sensitivity (Global)
        tk.Label(row1, text="Acento:", font=("Segoe UI", 8, "bold"), fg="#f472b6", bg="#161922").pack(side=tk.LEFT, padx=(4, 2))
        strum_s_vals = [v['name'] for v in STRUM_ACCENT_SENSITIVITIES.values()]
        self.strum_sens_combo = ttk.Combobox(
            row1,
            values=strum_s_vals,
            state="readonly",
            width=14
        )
        self.strum_sens_combo.current(2)  # default '50% (Sensibilidad Media)'
        self.strum_sens_combo.pack(side=tk.LEFT, padx=1)
        self.strum_sens_combo.bind("<<ComboboxSelected>>", self._on_global_strum_sens_selected)

        # Row 2: Transport, Performance Modes & Exporters
        row2 = tk.Frame(controls_frame, bg="#161922")
        row2.pack(fill=tk.X)

        # Play / Pause button
        self.btn_pause = tk.Button(
            row2,
            text="▶ Play [Espacio]",
            font=("Segoe UI", 8, "bold"),
            bg="#f59e0b",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._toggle_pause
        )
        self.btn_pause.pack(side=tk.LEFT, padx=(0, 6))

        btn_mute_all = tk.Button(
            row2,
            text="🔇 Mute",
            font=("Segoe UI", 8, "bold"),
            bg="#7f1d1d",
            fg="#fecaca",
            activebackground="#991b1b",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=7,
            pady=2,
            cursor="hand2",
            command=self._dampen_all
        )
        btn_mute_all.pack(side=tk.LEFT, padx=(0, 6))

        # Strum button
        btn_strum = tk.Button(
            row2,
            text="⚡ Strum",
            font=("Segoe UI", 8, "bold"),
            bg="#8338ec",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=7,
            pady=2,
            cursor="hand2",
            command=self._strum_wave
        )
        btn_strum.pack(side=tk.LEFT, padx=(0, 6))

        # Rhythm Mode Button
        self.btn_rhythm = tk.Button(
            row2,
            text="🔒 Ritmo",
            font=("Segoe UI", 8, "bold"),
            bg="#2ec4b6",
            fg="#0f1117",
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._toggle_rhythm_mode
        )
        self.btn_rhythm.pack(side=tk.LEFT, padx=(0, 6))

        # Strike Mode & Pattern Button
        self.btn_strike = tk.Button(
            row2,
            text="⇄ Golpes",
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._toggle_strike_mode
        )
        self.btn_strike.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_strike.bind("<Button-3>", self._show_strike_menu)

        # Harmonic Fill Palette Button
        self.btn_palette = tk.Button(
            row2,
            text="🎨 Paleta",
            font=("Segoe UI", 8, "bold"),
            bg="#4338ca",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._cycle_fill_palette
        )
        self.btn_palette.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_palette.bind("<Button-3>", self._show_fill_palette_menu)
        self._update_palette_button()

        # Visual Mode Button
        self.btn_view = tk.Button(
            row2,
            text="📏 Vista",
            font=("Segoe UI", 8, "bold"),
            bg="#3a86ff",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._toggle_view_mode
        )
        self.btn_view.pack(side=tk.LEFT, padx=(0, 6))

        # Organ Soundscape Presets Button
        self.btn_paisajes = tk.Button(
            row2,
            text="🌌 Paisajes",
            font=("Segoe UI", 8, "bold"),
            bg="#0f766e",
            fg="#ffffff",
            activebackground="#115e59",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=7,
            pady=2,
            cursor="hand2",
            command=self._show_soundscape_menu
        )
        self.btn_paisajes.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Separator(row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        # Batch Exporters
        btn_wav = tk.Button(
            row2,
            text="🔊 Save WAV",
            font=("Segoe UI", 8, "bold"),
            bg="#3a86ff",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._save_studio_wav
        )
        btn_wav.pack(side=tk.LEFT, padx=(4, 4))

        btn_midi = tk.Button(
            row2,
            text="🎹 Save MIDI",
            font=("Segoe UI", 8, "bold"),
            bg="#06d6a0",
            fg="#0f1117",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._save_studio_midi
        )
        btn_midi.pack(side=tk.LEFT, padx=(0, 4))

        btn_open_exp = tk.Button(
            row2,
            text="📁 Exports",
            font=("Segoe UI", 8),
            bg="#252b3b",
            fg="#8c9ab8",
            relief=tk.FLAT,
            padx=7,
            pady=2,
            cursor="hand2",
            command=self._open_exports_folder
        )
        btn_open_exp.pack(side=tk.RIGHT)

    def _get_instrument_list(self) -> List[str]:
        try:
            insts = get_sample_engine().get_available_instruments()
            return insts if insts else ["piano", "marimba", "celesta", "guitar-nylon", "harp", "drums"]
        except Exception:
            return ["piano", "marimba", "celesta", "guitar-nylon", "harp", "drums"]

    def _adjust_decay(self, delta: float):
        new_val = max(0.2, min(3.0, round(self.decay_var.get() + delta, 1)))
        self.decay_var.set(new_val)
        if hasattr(self, 'decay_label'):
            self.decay_label.config(text=f"{new_val:.1f}x")
        self.audio_engine.set_decay(new_val)
        self.canvas.focus_set()

    def _on_control_selected(self):
        self._init_system()
        self.canvas.focus_set()

    def _on_timbre_combo(self):
        self._on_timbre_change()
        self.canvas.focus_set()

    def _bind_keyboard(self):
        # Global keypress and keyrelease bindings that ALWAYS trigger regardless of widget focus!
        self.root.bind_all("<KeyPress>", self._on_key_press)
        self.root.bind_all("<KeyRelease>", self._on_key_release)
        self.canvas.focus_set()

    def _on_key_press(self, event):
        if event.widget is not None:
            try:
                if event.widget.winfo_toplevel() != self.root:
                    return
            except Exception:
                pass
            if isinstance(event.widget, tk.Entry) or (
                isinstance(event.widget, ttk.Entry) and not isinstance(event.widget, ttk.Combobox)
            ):
                return

        k = event.keysym.lower() if event.keysym else ""
        char = event.char.lower() if event.char else ""
        is_shift = bool(event.state & 0x0001)

        # F1-F5: Switch Keyboard Mode directly (no double-tap gestures)
        if k == "f1":
            self._exit_keyboard_mode()
            return "break"
        if k == "f2":
            self._toggle_keyboard_mode("chords_aa")
            return "break"
        if k == "f3":
            self._toggle_keyboard_mode("accent_ss")
            return "break"
        if k == "f4":
            self._toggle_keyboard_mode("strum_dd")
            return "break"
        if k == "f5":
            self._toggle_keyboard_mode("accel_ff")
            return "break"

        # ESC: Return to Piano mode if in an alternate mode; otherwise cancel pending transition
        if k == "escape":
            if self.keyboard_mode != "normal":
                self._exit_keyboard_mode()
            elif hasattr(self, 'pitch_follow'):
                self.pitch_follow.pending_midi = None
                self._update_follow_indicator()
                self._update_piano_keyboard_labels()
            return "break"

        # Global Transport, Tempo & Ball Count (always active in all modes)
        if k == "space" or char == " ":
            self._toggle_pause()
            return "break"
        if k == "up":
            self._adjust_bpm(+1)
            return "break"
        if k == "down":
            self._adjust_bpm(-1)
            return "break"
        if char in ("+", "=") or k in ("plus", "kp_add", "equal"):
            self._adjust_pendulums(+1)
            return "break"
        if char in ("-", "_") or k in ("minus", "kp_subtract"):
            self._adjust_pendulums(-1)
            return "break"

        num_char = None
        if char in "1234567890" and char:
            num_char = char
        elif k.startswith("kp_") and len(k) > 3 and k[3:] in "1234567890":
            num_char = k[3:]
        elif k in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"):
            num_char = k

        qp_keys = ("q", "w", "e", "r", "t", "y", "u", "i", "o", "p")
        al_keys = ("a", "s", "d", "f", "g", "h", "j", "k", "l")
        zm_keys = ("z", "x", "c", "v", "b", "n", "m")
        active_qp = char if char in qp_keys else (k if k in qp_keys else "")
        active_al = char if char in al_keys else (k if k in al_keys else "")
        active_zm = char if char in zm_keys else (k if k in zm_keys else "")

        # -------------------------------------------------------------
        # ALTERNATE KEYBOARD MODES: DD, FF, AA, SS
        # -------------------------------------------------------------
        if self.keyboard_mode == "strum_dd":
            if k in ("left", "bracketleft"):
                self._cycle_selected_ball(-1)
                return "break"
            if k in ("right", "bracketright"):
                self._cycle_selected_ball(+1)
                return "break"
            if k == "tab":
                self._cycle_selected_ball(-1 if is_shift else +1)
                return "break"
            if num_char is not None:
                self._handle_strum_num_key(num_char, is_shift)
                return "break"
            if active_qp:
                self._handle_strum_qp_key(active_qp, is_shift=is_shift)
                return "break"
            if active_al or char == "ñ" or k in ("ntilde", "semicolon"):
                self._handle_strum_mode_key(active_al or "ñ", is_shift=is_shift)
                return "break"
            if active_zm or char in (",", ".") or k in ("comma", "period"):
                zm_ch = active_zm or ("," if (char == "," or k == "comma") else ".")
                self._handle_strum_zm_key(zm_ch, is_shift)
                return "break"
            return

        if self.keyboard_mode == "accel_ff":
            if num_char is not None:
                idx = 9 if num_char == "0" else int(num_char) - 1
                self._toggle_ball_silence(idx)
                return "break"
            if k == "left":
                self._cycle_duration(-1)
                return "break"
            if k == "right":
                self._cycle_duration(+1)
                return "break"
            if active_qp:
                self._handle_accel_qp_key(active_qp)
                return "break"
            if active_al:
                self._handle_accel_al_key(active_al)
                return "break"
            if active_zm:
                self._handle_accel_zm_key(active_zm)
                return "break"
            return

        if self.keyboard_mode in ("chords_aa", "accent_ss"):
            if num_char is not None:
                idx = 9 if num_char == "0" else int(num_char) - 1
                self._toggle_ball_silence(idx)
                return "break"
            if active_al:
                if self.keyboard_mode == "chords_aa":
                    self._handle_chords_mode_key(active_al)
                else:
                    self._handle_accent_mode_key(active_al)
                return "break"
            if active_qp or char == "ñ" or k == "ntilde":
                return "break"
            t_key = resolve_transpose_key(char, k)
            if t_key is not None:
                self._on_transpose_key_press(t_key, from_mouse=False)
                return "break"
            if k in ("bracketleft", "bracketright") or char in ("[", "]"):
                delta = -12 if (k == "bracketleft" or char == "[") else +12
                self._apply_transpose_shift(delta)
                return "break"
            if k == "left":
                self._cycle_duration(-1)
                return "break"
            if k == "right":
                self._cycle_duration(+1)
                return "break"
            return

        # -------------------------------------------------------------
        # NORMAL MODE: CHROMATIC PIANO FOLLOW + LIVE SOUND + TRANSPOSITION
        # -------------------------------------------------------------
        if num_char is not None:
            idx = 9 if num_char == "0" else int(num_char) - 1
            self._toggle_ball_silence(idx)
            return "break"

        piano_key = resolve_piano_key(char, k, is_shift=is_shift)
        if piano_key is not None:
            self._on_follow_note_press(piano_key)
            return "break"

        if is_piano_gap_key(char, k):
            return "break"

        t_key = resolve_transpose_key(char, k)
        if t_key is not None:
            self._on_transpose_key_press(t_key, from_mouse=False)
            return "break"

        if k in ("bracketleft", "bracketright") or char in ("[", "]"):
            delta = -12 if (k == "bracketleft" or char == "[") else +12
            self._apply_transpose_shift(delta)
            return "break"

        if k == "left":
            self._cycle_duration(-1)
            return "break"
        if k == "right":
            self._cycle_duration(+1)
            return "break"

    def _on_key_release(self, event):
        if event.widget is not None:
            try:
                if event.widget.winfo_toplevel() != self.root:
                    return
            except Exception:
                pass
            if isinstance(event.widget, tk.Entry) or (
                isinstance(event.widget, ttk.Entry) and not isinstance(event.widget, ttk.Combobox)
            ):
                return

        k = event.keysym.lower() if event.keysym else ""
        char = event.char.lower() if event.char else ""
        is_shift = bool(event.state & 0x0001)

        if self.keyboard_mode == "normal":
            piano_key = resolve_piano_key(char, k, is_shift=is_shift)
            if piano_key is not None:
                self._schedule_follow_note_release(piano_key)
                return "break"

        t_key = resolve_transpose_key(char, k)
        if t_key is not None and (
            self.keyboard_mode in ("normal", "chords_aa", "accent_ss")
            or t_key in self.held_transpose_keys
        ):
            self._schedule_transpose_key_release(t_key)
            return "break"

    def _on_num_button_click(self, idx: int):
        if self.keyboard_mode == "strum_dd":
            num_char = "0" if idx == 9 else str(idx + 1)
            self._handle_strum_num_key(num_char, False)
            return
        self._toggle_ball_silence(idx)

    def _on_num_button_right_click(self, event, idx: int):
        if self.keyboard_mode == "strum_dd" and idx == 9:
            return
        self._show_ball_properties_menu(event, idx)

    def _on_qp_slot_press(self, key_id: str):
        if self.keyboard_mode == "strum_dd":
            self._handle_strum_qp_key(key_id.lower())
        elif self.keyboard_mode == "accel_ff":
            self._handle_accel_qp_key(key_id.lower())
        elif self.keyboard_mode == "normal" and key_id in PIANO_NOTE_OFFSETS:
            self._on_follow_note_press(key_id)

    def _on_qp_slot_release(self, key_id: str):
        if self.keyboard_mode == "normal" and key_id in PIANO_NOTE_OFFSETS:
            self._on_follow_note_release(key_id)

    def _on_al_slot_press(self, key_id: str):
        if self.keyboard_mode == "chords_aa":
            if key_id != "Ñ":
                self._handle_chords_mode_key(key_id.lower())
        elif self.keyboard_mode == "accent_ss":
            if key_id != "Ñ":
                self._handle_accent_mode_key(key_id.lower())
        elif self.keyboard_mode == "strum_dd":
            self._handle_strum_mode_key(key_id.lower())
        elif self.keyboard_mode == "accel_ff":
            if key_id != "Ñ":
                self._handle_accel_al_key(key_id.lower())
        elif self.keyboard_mode == "normal":
            self._on_follow_note_press(key_id)

    def _on_al_slot_release(self, key_id: str):
        if self.keyboard_mode == "normal":
            self._on_follow_note_release(key_id)

    def _on_zm_slot_click(self, key_id: str):
        if self.keyboard_mode == "strum_dd":
            self._handle_strum_zm_key(key_id.lower(), False)
        elif self.keyboard_mode == "accel_ff":
            if key_id not in (",", "."):
                self._handle_accel_zm_key(key_id.lower())
        else:
            self._on_transpose_key_press(key_id, from_mouse=True)

    # -------------------------------------------------------------
    # ACCOMPANIMENT PITCH-FOLLOW, LIVE KEYBOARD SOUND & TRANSPOSITION
    # -------------------------------------------------------------
    def _cancel_pending_strum_afters(self, include_strums: bool = True):
        for aid in list(getattr(self, 'pending_step_after_ids', [])):
            try:
                self.root.after_cancel(aid)
            except Exception:
                pass
        if hasattr(self, 'pending_step_after_ids'):
            self.pending_step_after_ids.clear()

        if not include_strums:
            return
        for aid in list(getattr(self, 'pending_strum_after_ids', [])):
            try:
                self.root.after_cancel(aid)
            except Exception:
                pass
        if hasattr(self, 'pending_strum_after_ids'):
            self.pending_strum_after_ids.clear()

    def _is_chord_enabled_for_keyboard(self) -> bool:
        if not hasattr(self, 'chord_play_mode_var'):
            return False
        return (
            self.chord_play_mode_var.get() != "off"
            and self.chord_target_var.get() in ("both", "keyboard")
        )

    def _is_chord_enabled_for_accompaniment(self) -> bool:
        if not hasattr(self, 'chord_play_mode_var'):
            return False
        return (
            self.chord_play_mode_var.get() != "off"
            and self.chord_target_var.get() in ("both", "accompaniment")
        )

    def _resolve_chord_for_midi(
        self, target_midi: int, for_strum: Optional[bool] = None
    ) -> Tuple[List[int], str]:
        strum_v = (
            (self.chord_play_mode_var.get() == "strum")
            if for_strum is None
            else bool(for_strum)
        )
        home_midi = self.pitch_follow.home_root_midi if hasattr(self, 'pitch_follow') else None
        return build_chord_for_midi(
            target_midi=target_midi,
            quality=self.chord_quality_var.get(),
            home_root_midi=home_midi,
            harmony_type=self.harmony_type_var.get(),
            add_seventh=bool(self.chord_add_seventh_var.get()),
            strum_voicing=strum_v,
        )

    def _update_chord_controls(self):
        if not hasattr(self, 'chord_play_mode_var'):
            return
        c_mode = self.chord_play_mode_var.get()
        active_styles = {
            "off": ("#00f5d4", "#000000"),
            "block": ("#e11d48", "#ffffff"),
            "strum": ("#d97706", "#ffffff"),
        }
        for cm_key, btn in getattr(self, 'chord_mode_buttons', {}).items():
            if cm_key == c_mode:
                bg_c, fg_c = active_styles.get(cm_key, ("#e11d48", "#ffffff"))
                btn.config(bg=bg_c, fg=fg_c, relief=tk.SUNKEN)
            else:
                btn.config(bg="#1e293b", fg="#94a3b8", relief=tk.FLAT)

        t_keys = list(CHORD_TARGET_MODES.keys())
        cur_t = self.chord_target_var.get()
        if hasattr(self, 'chord_target_combo') and cur_t in t_keys:
            self.chord_target_combo.current(t_keys.index(cur_t))

        q_keys = list(CHORD_QUALITY_MODES.keys())
        cur_q = self.chord_quality_var.get()
        if hasattr(self, 'chord_quality_combo') and cur_q in q_keys:
            self.chord_quality_combo.current(q_keys.index(cur_q))

        if hasattr(self, 'btn_chord_7th'):
            if bool(self.chord_add_seventh_var.get()):
                self.btn_chord_7th.config(bg="#4a154b", fg="#38bdf8", relief=tk.SUNKEN)
            else:
                self.btn_chord_7th.config(bg="#1e293b", fg="#94a3b8", relief=tk.FLAT)

        if hasattr(self, 'lbl_chord_badge'):
            if c_mode == "off":
                self.lbl_chord_badge.config(text="")
            else:
                badge = f"▶ {self.active_chord_label}" if self.active_chord_label else ""
                self.lbl_chord_badge.config(text=badge)

    def _sync_system_chord_state(self, restore_scale_if_off: bool = True):
        self._cancel_pending_strum_afters()
        if hasattr(self, 'sounding_pendulum_pitches'):
            self.sounding_pendulum_pitches.clear()

        if self._is_chord_enabled_for_accompaniment():
            pitches, cname = self._resolve_chord_for_midi(
                self.pitch_follow.active_midi, for_strum=False
            )
            if hasattr(self, 'system'):
                self.system.chord_play_mode = self.chord_play_mode_var.get()
                self.system.set_chord_pitches_inplace(
                    self.root_key_var.get(),
                    self.octave_var.get(),
                    pitches,
                )
            self.active_chord_pitches = list(pitches)
            self.active_chord_label = cname
        else:
            if hasattr(self, 'system'):
                self.system.chord_play_mode = 'off'
                self.system.chord_pitches = []
                if restore_scale_if_off and self.keyboard_mode != "chords_aa":
                    self.system.set_root_pitch_inplace(
                        self.root_key_var.get(),
                        self.octave_var.get(),
                    )
                    self.active_chord_pitches = []
            elif restore_scale_if_off and self.keyboard_mode != "chords_aa":
                self.active_chord_pitches = []

            if self._is_chord_enabled_for_keyboard():
                _, cname = self._resolve_chord_for_midi(self.pitch_follow.active_midi)
                self.active_chord_label = cname
            else:
                self.active_chord_label = ""

        self._update_chord_controls()
        self._update_hud_info()
        self._update_follow_indicator()
        self._update_matrix_buttons()
        self._sync_side_panel_ball_names()
        self._update_piano_keyboard_labels()

    def _set_chord_play_mode(self, mode: str):
        if mode not in CHORD_PLAY_MODES:
            return
        self.chord_play_mode_var.set(mode)
        self._stop_all_follow_key_voices()
        self._sync_system_chord_state(restore_scale_if_off=True)
        self.canvas.focus_set()

    def _on_chord_target_selected(self, event=None):
        t_keys = list(CHORD_TARGET_MODES.keys())
        idx = self.chord_target_combo.current() if hasattr(self, 'chord_target_combo') else -1
        if 0 <= idx < len(t_keys):
            self.chord_target_var.set(t_keys[idx])
            self._stop_all_follow_key_voices()
            self._sync_system_chord_state(restore_scale_if_off=True)
        self.canvas.focus_set()

    def _on_chord_quality_selected(self, event=None):
        q_keys = list(CHORD_QUALITY_MODES.keys())
        idx = self.chord_quality_combo.current() if hasattr(self, 'chord_quality_combo') else -1
        if 0 <= idx < len(q_keys):
            self.chord_quality_var.set(q_keys[idx])
            self._stop_all_follow_key_voices()
            self._sync_system_chord_state(restore_scale_if_off=True)
        self.canvas.focus_set()

    def _toggle_chord_seventh(self):
        self.chord_add_seventh_var.set(not bool(self.chord_add_seventh_var.get()))
        self._stop_all_follow_key_voices()
        self._sync_system_chord_state(restore_scale_if_off=True)
        self.canvas.focus_set()

    def _play_keyboard_chord_voices(
        self,
        key_id: Optional[str],
        pitches: List[int],
        dur: float,
        info: Optional[Dict[str, Any]],
    ):
        """Plays 1 or more chord notes simultaneously (block) or staggered (strum)."""
        if not pitches:
            return
        c_mode = (
            self.chord_play_mode_var.get()
            if (hasattr(self, 'chord_play_mode_var') and len(pitches) > 1)
            else "off"
        )
        base_vel = 108 if len(pitches) <= 1 else (96 if c_mode == "strum" else 94)
        kb_timbre = self._get_keyboard_timbre()
        kb_decay = self._get_keyboard_decay()
        kb_pan = max(-1.0, min(1.0, float(self.kb_pan_var.get())))
        kb_vel = max(20, min(127, int(round(base_vel * float(self.kb_volume_var.get())))))

        if c_mode == "strum" and len(pitches) > 1:
            ratio = STRUM_PROGRESSIONS.get(self.strum_progression_var.get(), {}).get('ratio', 0.72)
            span = min(0.11, 0.028 * max(1, len(pitches) - 1))
            delays = compute_strum_delays(len(pitches), span, ratio)
        else:
            delays = [0.0] * len(pitches)

        for pt, dly in zip(pitches, delays):
            dt_ms = int(round(dly * 1000))
            if dt_ms <= 0:
                ch, rec_ev = self.audio_engine.play_note(
                    pitch=pt,
                    velocity=kb_vel,
                    duration=dur,
                    pan=kb_pan,
                    pendulum_index=KEYBOARD_VOICE_INDEX,
                    timbre=kb_timbre,
                    decay=kb_decay,
                )
                if info is not None:
                    info["voices"].append({"channel": ch, "rec_ev": rec_ev, "midi": pt, "timbre": kb_timbre})
            else:
                aid_holder: List[str] = []

                def _fire_deferred(
                    pt_i=pt,
                    v_i=kb_vel,
                    inf=info,
                    kid=key_id,
                    d_sec=dur,
                    pn_i=kb_pan,
                    t_i=kb_timbre,
                    dc_i=kb_decay,
                    a_hold=aid_holder,
                ):
                    aid_self = a_hold[0] if a_hold else None
                    if aid_self and aid_self in self.pending_strum_after_ids:
                        self.pending_strum_after_ids.remove(aid_self)
                    if inf is not None:
                        if aid_self and aid_self in inf.get("after_ids", []):
                            inf["after_ids"].remove(aid_self)
                        if (
                            inf.get("mode") == "hold"
                            and kid is not None
                            and self.follow_key_voices.get(kid) is not inf
                        ):
                            return
                    ch_i, rec_i = self.audio_engine.play_note(
                        pitch=pt_i,
                        velocity=v_i,
                        duration=d_sec,
                        pan=pn_i,
                        pendulum_index=KEYBOARD_VOICE_INDEX,
                        timbre=t_i,
                        decay=dc_i,
                    )
                    if inf is not None:
                        inf["voices"].append({"channel": ch_i, "rec_ev": rec_i, "midi": pt_i, "timbre": t_i})

                aid = self.root.after(dt_ms, _fire_deferred)
                aid_holder.append(aid)
                if info is not None:
                    info["after_ids"].append(aid)
                else:
                    self.pending_strum_after_ids.append(aid)

    def _trigger_piano_key_sound(self, key_id: str, note_midi: int):
        """Plays or arms live keyboard audition audio for a pressed piano key."""
        s_mode = self.keyboard_sound_mode_var.get()
        prev = self.follow_key_voices.pop(key_id, None)
        if prev:
            for aid in prev.get("after_ids", []):
                try:
                    self.root.after_cancel(aid)
                except Exception:
                    pass
            for v in prev.get("voices", []):
                if v.get("channel"):
                    self.audio_engine.stop_channel(v["channel"], fadeout_ms=40, timbre=v.get("timbre"))
            if prev.get("channel"):
                self.audio_engine.stop_channel(prev["channel"], fadeout_ms=40, timbre=prev.get("timbre"))

        if s_mode == "silent":
            return

        oct_shift = int(self.kb_octave_offset_var.get()) * 12
        sounding_midi = max(21, min(108, int(note_midi) + oct_shift))
        if self._is_chord_enabled_for_keyboard():
            pitches, _ = self._resolve_chord_for_midi(sounding_midi)
        else:
            pitches = [sounding_midi]

        kb_dur_mode = self.kb_duration_mode_var.get()
        fixed_dur = NOTE_DURATIONS.get(kb_dur_mode, {}).get('sec') if kb_dur_mode != 'auto' else None

        if s_mode == "hold":
            play_dur = float(fixed_dur) if fixed_dur is not None else 3.5
            info: Dict[str, Any] = {
                "start_time": time.time(),
                "midi": sounding_midi,
                "pitches": list(pitches),
                "voices": [],
                "after_ids": [],
                "mode": "hold",
                "fixed_duration": (fixed_dur is not None),
            }
            self.follow_key_voices[key_id] = info
            self._play_keyboard_chord_voices(key_id, pitches, play_dur, info)
        elif s_mode == "staccato":
            play_dur = float(fixed_dur) if fixed_dur is not None else 0.22
            info = {
                "start_time": time.time(),
                "midi": sounding_midi,
                "pitches": list(pitches),
                "voices": [],
                "after_ids": [],
                "mode": "staccato",
            }
            self.follow_key_voices[key_id] = info
            self._play_keyboard_chord_voices(key_id, pitches, play_dur, info)
        elif s_mode == "short_only":
            self.follow_key_voices[key_id] = {
                "start_time": time.time(),
                "midi": sounding_midi,
                "pitches": list(pitches),
                "voices": [],
                "after_ids": [],
                "mode": "short_only",
                "short_dur": float(fixed_dur) if fixed_dur is not None else 0.24,
            }

    def _release_piano_key_sound(self, key_id: str):
        """Stops sustained key voices or triggers short-only click audition on release."""
        info = self.follow_key_voices.pop(key_id, None)
        if not info:
            return
        elapsed = max(0.05, time.time() - info["start_time"])
        if info["mode"] == "hold":
            if info.get("fixed_duration", False):
                for aid in info.get("after_ids", []):
                    if aid not in self.pending_strum_after_ids:
                        self.pending_strum_after_ids.append(aid)
            else:
                for aid in info.get("after_ids", []):
                    try:
                        self.root.after_cancel(aid)
                    except Exception:
                        pass
                info.get("after_ids", []).clear()
                for v in info.get("voices", []):
                    if v.get("rec_ev"):
                        self.audio_engine.recorder.update_event_duration(
                            v["rec_ev"], max(0.08, elapsed)
                        )
                    if v.get("channel"):
                        self.audio_engine.stop_channel(
                            v["channel"], fadeout_ms=65, timbre=v.get("timbre")
                        )
                if info.get("rec_ev"):
                    self.audio_engine.recorder.update_event_duration(
                        info["rec_ev"], max(0.08, elapsed)
                    )
                if info.get("channel"):
                    self.audio_engine.stop_channel(
                        info["channel"], fadeout_ms=65, timbre=info.get("timbre")
                    )
        elif info["mode"] == "staccato":
            for aid in info.get("after_ids", []):
                if aid not in self.pending_strum_after_ids:
                    self.pending_strum_after_ids.append(aid)
        elif info["mode"] == "short_only":
            if elapsed <= (SHORT_CLICK_THRESHOLD_SEC + 0.03):
                self._play_keyboard_chord_voices(
                    None,
                    info.get("pitches") or [info["midi"]],
                    info.get("short_dur", 0.24),
                    None,
                )

    def _stop_all_follow_key_voices(self):
        for info in list(self.follow_key_voices.values()):
            for aid in info.get("after_ids", []):
                try:
                    self.root.after_cancel(aid)
                except Exception:
                    pass
            for v in info.get("voices", []):
                ch_v = v.get("channel")
                if ch_v:
                    self.audio_engine.stop_channel(ch_v, fadeout_ms=50, timbre=v.get("timbre"))
            ch = info.get("channel")
            if ch:
                self.audio_engine.stop_channel(ch, fadeout_ms=50, timbre=info.get("timbre"))
        self.follow_key_voices.clear()
        self._cancel_pending_strum_afters()

    def _get_keyboard_timbre(self) -> str:
        return self.kb_timbre_var.get().strip() or self.timbre_var.get()

    def _get_keyboard_decay(self) -> Optional[float]:
        if self.kb_decay_follow_var.get():
            return None
        return max(0.2, min(3.0, float(self.kb_decay_var.get())))

    def _has_custom_kb_voice_props(self) -> bool:
        return (
            (not self.kb_link_accompaniment_var.get())
            or bool(self.kb_timbre_var.get().strip())
            or (not self.kb_decay_follow_var.get())
            or (self.kb_duration_mode_var.get() != "auto")
            or (int(self.kb_octave_offset_var.get()) != 0)
            or (abs(float(self.kb_volume_var.get()) - 1.0) > 0.01)
            or (abs(float(self.kb_pan_var.get())) > 0.01)
        )

    def _update_kb_props_button(self):
        if not hasattr(self, 'btn_kb_props'):
            return
        if not self.kb_link_accompaniment_var.get():
            self.btn_kb_props.config(
                text="🎹 Props (Indep)",
                bg="#065f46",
                fg="#6ee7b7",
            )
        elif self._has_custom_kb_voice_props():
            self.btn_kb_props.config(
                text="🎹 Props⚡",
                bg="#1e3a5f",
                fg="#fde047",
            )
        else:
            self.btn_kb_props.config(
                text="🎹 Props",
                bg="#252b3b",
                fg="#38bdf8",
            )

    def _reset_keyboard_voice_props(self):
        self.kb_link_accompaniment_var.set(True)
        self.kb_timbre_var.set("")
        self.kb_decay_follow_var.set(True)
        self.kb_decay_var.set(1.0)
        self.kb_duration_mode_var.set("auto")
        self.kb_octave_offset_var.set(0)
        self.kb_volume_var.set(1.0)
        self.kb_pan_var.set(0.0)
        self._stop_all_follow_key_voices()
        self._update_kb_sound_controls()
        self._update_kb_props_button()
        self._update_follow_indicator()
        self._update_piano_keyboard_labels()

    def _update_kb_sound_controls(self):
        s_mode = self.keyboard_sound_mode_var.get()
        mode_keys = list(KEYBOARD_SOUND_MODES.keys())
        if hasattr(self, 'kb_sound_combo') and s_mode in mode_keys:
            self.kb_sound_combo.current(mode_keys.index(s_mode))
        if hasattr(self, 'btn_kb_sound'):
            if s_mode == "silent":
                self.btn_kb_sound.config(
                    text="🔇 Teclado",
                    bg="#334155",
                    fg="#94a3b8",
                )
            else:
                self.btn_kb_sound.config(
                    text="🔊 Teclado",
                    bg="#065f46",
                    fg="#6ee7b7",
                )
        self._update_kb_props_button()

    def _on_kb_sound_mode_selected(self, event=None):
        mode_keys = list(KEYBOARD_SOUND_MODES.keys())
        idx = self.kb_sound_combo.current() if hasattr(self, 'kb_sound_combo') else -1
        if 0 <= idx < len(mode_keys):
            s_mode = mode_keys[idx]
            self.keyboard_sound_mode_var.set(s_mode)
            if s_mode != "silent":
                self.keyboard_sound_last_active_mode = s_mode
            else:
                self._stop_all_follow_key_voices()
            self._update_kb_sound_controls()
            self._update_piano_keyboard_labels()
        self.canvas.focus_set()

    def _toggle_keyboard_sound(self):
        cur = self.keyboard_sound_mode_var.get()
        if cur == "silent":
            nxt = self.keyboard_sound_last_active_mode or "hold"
            if nxt == "silent":
                nxt = "hold"
        else:
            self.keyboard_sound_last_active_mode = cur
            nxt = "silent"
            self._stop_all_follow_key_voices()
        self.keyboard_sound_mode_var.set(nxt)
        self._update_kb_sound_controls()
        self._update_piano_keyboard_labels()
        self.canvas.focus_set()

    def _apply_accompaniment_pitch(self, target_midi: int):
        """Updates accompaniment root & octave (or active chord) in place without restarting pendulum phase."""
        target_midi = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, int(target_midi)))
        new_root = NOTE_NAMES[target_midi % 12]
        new_oct = (target_midi // 12) - 1
        self.root_key_var.set(new_root)
        self.octave_var.set(new_oct)
        self._cancel_pending_strum_afters()
        self.sounding_pendulum_pitches.clear()

        if self._is_chord_enabled_for_accompaniment():
            pitches, cname = self._resolve_chord_for_midi(target_midi, for_strum=False)
            if hasattr(self, 'system'):
                self.system.chord_play_mode = self.chord_play_mode_var.get()
                self.system.set_chord_pitches_inplace(new_root, new_oct, pitches)
            self.active_chord_pitches = list(pitches)
            self.active_chord_label = cname
        else:
            if hasattr(self, 'system'):
                self.system.chord_play_mode = 'off'
                self.system.chord_pitches = []
                self.system.set_root_pitch_inplace(new_root, new_oct)
            self.active_chord_pitches = []
            if self._is_chord_enabled_for_keyboard():
                _, self.active_chord_label = self._resolve_chord_for_midi(target_midi)
            else:
                self.active_chord_label = ""

        self._update_chord_controls()
        self._update_hud_info()
        self._update_follow_indicator()
        self._update_matrix_buttons()
        self._sync_side_panel_ball_names()
        self._update_piano_keyboard_labels()

    def _sync_side_panel_ball_names(self):
        if not hasattr(self, 'ball_selector_combo') or not hasattr(self, 'system'):
            return
        n = len(self.system.pendulums)
        if n == 0:
            return
        self.selected_ball_idx = max(0, min(n - 1, self.selected_ball_idx))
        ball_names = [
            f"Bola {i + 1} ({midi_to_note_name(p.base_pitch)})"
            for i, p in enumerate(self.system.pendulums)
        ]
        self.ball_selector_combo.config(values=ball_names)
        self.ball_selector_combo.current(self.selected_ball_idx)

    def _update_follow_indicator(self):
        if not hasattr(self, 'pitch_follow'):
            return
        active_name = midi_to_note_name(self.pitch_follow.active_midi)
        offset_str = format_semitone_offset(self.pitch_follow.transpose_semitones)
        pending_str = ""
        if self.pitch_follow.pending_midi is not None:
            pending_str = f" → {midi_to_note_name(self.pitch_follow.pending_midi)} ⏳"
        chord_tag = ""
        if (
            hasattr(self, 'chord_play_mode_var')
            and self.chord_play_mode_var.get() != "off"
            and getattr(self, 'active_chord_label', '')
        ):
            chord_tag = f" [{self.active_chord_label}]"
        kb_tag = ""
        if hasattr(self, 'kb_link_accompaniment_var'):
            custom_inst = self.kb_timbre_var.get().strip()
            oct_v = int(self.kb_octave_offset_var.get())
            oct_s = f" {oct_v:+d}oct" if oct_v != 0 else ""
            if not self.kb_link_accompaniment_var.get():
                inst_s = custom_inst or self.timbre_var.get()
                kb_tag = f" · Indep:{inst_s}{oct_s}"
            elif custom_inst or oct_v != 0:
                inst_s = custom_inst or self.timbre_var.get()
                kb_tag = f" · Tec:{inst_s}{oct_s}"
        if hasattr(self, 'follow_indicator'):
            self.follow_indicator.config(
                text=f"🎹 {active_name}{chord_tag}{pending_str} ({offset_str}{kb_tag})",
                fg="#facc15" if self.pitch_follow.pending_midi is not None else "#00f5d4",
            )
        if hasattr(self, 'lbl_transpose_status') and self.keyboard_mode not in ("strum_dd", "accel_ff"):
            low_n, high_n = self.pitch_follow.get_keyboard_range_names()
            shift = self.pitch_follow.transpose_semitones
            shift_tag = "0st" if shift == 0 else f"{shift:+d}st"
            self.lbl_transpose_status.config(
                text=f"{low_n}–{high_n} ({shift_tag})"
            )

    def _on_follow_note_press(self, key_id: str):
        rel_id = f"piano_{key_id}"
        if rel_id in self.pending_releases:
            try:
                self.root.after_cancel(self.pending_releases.pop(rel_id))
            except Exception:
                pass
            return

        if key_id in self.pitch_follow.held_piano_keys:
            return

        raw_midi = self.pitch_follow.midi_for_key(key_id)
        if raw_midi is not None:
            note_midi = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, raw_midi))
            self._trigger_piano_key_sound(key_id, note_midi)

        if self.kb_link_accompaniment_var.get():
            new_midi = self.pitch_follow.on_note_press(key_id, is_live_active=self.is_live_active)
            if new_midi is not None:
                self._apply_accompaniment_pitch(new_midi)
            else:
                self._update_follow_indicator()
                self._update_piano_keyboard_labels()
        else:
            if key_id not in self.pitch_follow.held_piano_keys:
                self.pitch_follow.held_piano_keys.append(key_id)
            self._update_follow_indicator()
            self._update_piano_keyboard_labels()
        self.canvas.focus_set()

    def _on_follow_note_release(self, key_id: str):
        self._schedule_follow_note_release(key_id)

    def _schedule_follow_note_release(self, key_id: str):
        rel_id = f"piano_{key_id}"
        if rel_id in self.pending_releases:
            try:
                self.root.after_cancel(self.pending_releases[rel_id])
            except Exception:
                pass
        self.pending_releases[rel_id] = self.root.after(
            25, lambda kid=key_id: self._execute_follow_note_release(kid)
        )

    def _execute_follow_note_release(self, key_id: str):
        rel_id = f"piano_{key_id}"
        self.pending_releases.pop(rel_id, None)
        self._release_piano_key_sound(key_id)
        if self.kb_link_accompaniment_var.get():
            new_midi = self.pitch_follow.on_note_release(key_id)
            if new_midi is not None:
                self._apply_accompaniment_pitch(new_midi)
            else:
                self._update_follow_indicator()
                self._update_piano_keyboard_labels()
        else:
            if key_id in self.pitch_follow.held_piano_keys:
                self.pitch_follow.held_piano_keys.remove(key_id)
            self._update_follow_indicator()
            self._update_piano_keyboard_labels()

    def _on_transpose_key_press(self, key_id: str, from_mouse: bool = False):
        rel_id = f"tr_{key_id}"
        if not from_mouse:
            if rel_id in self.pending_releases:
                try:
                    self.root.after_cancel(self.pending_releases.pop(rel_id))
                except Exception:
                    pass
                return
            if key_id in self.held_transpose_keys:
                return
            self.held_transpose_keys.add(key_id)

        delta = self.pitch_follow.get_transpose_delta(key_id, self.harmony_type_var.get())
        if delta is None:
            new_midi = self.pitch_follow.reset_transpose(
                apply_to_accompaniment=bool(self.kb_link_accompaniment_var.get())
            )
            if new_midi is not None:
                self._apply_accompaniment_pitch(new_midi)
            else:
                self._update_follow_indicator()
                self._update_piano_keyboard_labels()
        else:
            self._apply_transpose_shift(delta)
        self._flash_key_ui(key_id, "zm")
        if from_mouse:
            self.canvas.focus_set()

    def _apply_transpose_shift(self, delta_semitones: int):
        new_midi = self.pitch_follow.shift_keyboard(
            delta_semitones,
            apply_to_accompaniment=bool(self.kb_link_accompaniment_var.get()),
        )
        if new_midi is not None:
            self._apply_accompaniment_pitch(new_midi)
        else:
            self._update_follow_indicator()
            self._update_piano_keyboard_labels()

    def _schedule_transpose_key_release(self, key_id: str):
        rel_id = f"tr_{key_id}"
        if rel_id in self.pending_releases:
            try:
                self.root.after_cancel(self.pending_releases[rel_id])
            except Exception:
                pass
        self.pending_releases[rel_id] = self.root.after(
            25, lambda kid=key_id: self._execute_transpose_key_release(kid)
        )

    def _execute_transpose_key_release(self, key_id: str):
        rel_id = f"tr_{key_id}"
        self.pending_releases.pop(rel_id, None)
        self.held_transpose_keys.discard(key_id)

    def _on_follow_transition_selected(self, event=None):
        modes = list(FOLLOW_TRANSITION_MODES.keys())
        idx = self.follow_transition_combo.current() if hasattr(self, 'follow_transition_combo') else -1
        if 0 <= idx < len(modes):
            mode = modes[idx]
            self.follow_transition_var.set(mode)
            committed_midi = self.pitch_follow.set_transition_mode(mode)
            if committed_midi is not None:
                self._apply_accompaniment_pitch(committed_midi)
            else:
                self._update_follow_indicator()
                self._update_piano_keyboard_labels()
        self.canvas.focus_set()

    def _cycle_third_mode(self):
        modes = list(THIRD_INTERVAL_MODES.keys())
        cur = self.pitch_follow.third_mode
        nxt = modes[(modes.index(cur) + 1) % len(modes)] if cur in modes else "auto"
        self.pitch_follow.set_third_mode(nxt)
        self._update_piano_keyboard_labels()
        self.canvas.focus_set()

    def _on_root_key_selected(self):
        self._init_system(update_follow_home=True, recenter_keyboard=True)
        self.canvas.focus_set()

    def _on_octave_selected(self):
        self._init_system(update_follow_home=True, recenter_keyboard=True)
        self.canvas.focus_set()

    # -------------------------------------------------------------
    # LIVE PERFORMANCE MODAL KEYBOARD (AA Chords, SS Accents, DD Strum, FF Accel)
    # -------------------------------------------------------------
    def _get_active_ball_indices(self) -> List[int]:
        """Returns list of pendulum indices that are currently ON (not muted / silence)."""
        if not hasattr(self, 'system') or not self.system.pendulums:
            return []
        active = []
        n = len(self.system.pendulums)
        for i in range(n):
            mute_time = self.pendulum_mutes.get(i, 0.0)
            is_muted = (self.anim_time < mute_time)
            if not is_muted:
                active.append(i)
        if not active:
            active = list(range(n))
        return active

    def _get_strum_target_balls(self) -> List[int]:
        """Returns the list of balls affected by strum operations based on strum_target_mode."""
        active = self._get_active_ball_indices()
        if self.strum_target_mode == "even":
            res = [b for b in active if b % 2 == 0]
            return res if res else active
        elif self.strum_target_mode == "odd":
            res = [b for b in active if b % 2 == 1]
            return res if res else active
        elif self.strum_target_mode == "single":
            if self.selected_ball_idx in active:
                return [self.selected_ball_idx]
            return active[:1]
        return active

    def _is_pattern_all_mode(self) -> bool:
        """Returns True when Pattern mode [F4] is targeting ALL pendulums simultaneously."""
        return self.keyboard_mode == "strum_dd" and self.strum_target_mode == "all"

    def _get_pattern_target_balls(self, force_all: bool = False) -> List[int]:
        """Returns pendulum indices targeted by pattern edits (all balls or selected ball)."""
        if not hasattr(self, 'system') or not self.system.pendulums:
            return []
        n = len(self.system.pendulums)
        if force_all or self._is_pattern_all_mode():
            return list(range(n))
        return [max(0, min(n - 1, self.selected_ball_idx))]

    def _toggle_pattern_all_mode(self):
        """Toggles ALL-patterns mode ('all' vs 'single') inside [F4] Patrón via key 0."""
        if not hasattr(self, 'system') or not self.system.pendulums:
            return
        n = len(self.system.pendulums)
        if self.strum_target_mode == "all":
            self.strum_target_mode = "single"
            b = max(0, min(n - 1, self.selected_ball_idx))
            self.selected_ball_idx = b
            cur_l, cur_r = self._get_ball_steps(b)
            note = midi_to_note_name(self.system.pendulums[b].base_pitch)
            self.mode_banner_text = (
                f"🎯 Bola {b + 1} ({note}): ◄ [{format_pattern(cur_l)}] │ ► [{format_pattern(cur_r)}]"
            )
        else:
            self.strum_target_mode = "all"
            self.mode_banner_text = (
                f"🌐 MODO TODAS ({n} bolas) [0]: Q-I / A-K / O-P / L-Ñ / Z-. / Presets afectan TODOS los patrones"
            )
        self._sync_side_panel_controls()
        self._update_matrix_buttons()
        self._update_keyboard_labels()
        self._update_hud_info()
        self._flash_key_ui("0", "num")

    def _update_mode_buttons(self):
        if not hasattr(self, 'mode_buttons'):
            return
        active_colors = {
            "normal": ("#00f5d4", "#000000"),
            "chords_aa": ("#e11d48", "#ffffff"),
            "accent_ss": ("#f59e0b", "#000000"),
            "strum_dd": ("#9333ea", "#ffffff"),
            "accel_ff": ("#0284c7", "#ffffff"),
        }
        for m_key, btn in self.mode_buttons.items():
            if m_key == self.keyboard_mode:
                bg_c, fg_c = active_colors.get(m_key, ("#0284c7", "#ffffff"))
                btn.config(bg=bg_c, fg=fg_c, relief=tk.SUNKEN)
            else:
                btn.config(bg="#1e293b", fg="#94a3b8", relief=tk.FLAT)

    def _toggle_keyboard_mode(self, mode: str):
        if self.keyboard_mode == mode:
            self._exit_keyboard_mode()
        else:
            self._enter_keyboard_mode(mode)

    def _enter_keyboard_mode(self, mode: str):
        self._stop_all_follow_key_voices()
        if hasattr(self, 'pitch_follow'):
            self.pitch_follow.held_piano_keys.clear()
        if hasattr(self, 'held_transpose_keys'):
            self.held_transpose_keys.clear()
        for rel_k in list(self.pending_releases.keys()):
            if rel_k.startswith("piano_") or rel_k.startswith("tr_"):
                try:
                    self.root.after_cancel(self.pending_releases.pop(rel_k))
                except Exception:
                    self.pending_releases.pop(rel_k, None)

        self.keyboard_mode = mode

        if mode == "chords_aa":
            self._apply_chord_degree(self.active_chord_degree)
        elif mode == "accent_ss":
            cur_dyn = self.dynamic_mode_var.get()
            dyn_name = DYNAMIC_MODES.get(cur_dyn, {}).get("short", cur_dyn)
            self.mode_banner_text = f"⚡ Acentuación activa: {dyn_name}"
        elif mode == "strum_dd":
            self.strum_target_mode = "single"
            b = self.selected_ball_idx
            cur_l, cur_r = self._get_ball_steps(b)
            p = self.system.pendulums[b] if (hasattr(self, 'system') and b < len(self.system.pendulums)) else None
            note = midi_to_note_name(p.base_pitch) if p else ""
            self.mode_banner_text = (
                f"🎯 Bola {b+1} {note}: ◄ [{format_pattern(cur_l)}] │ ► [{format_pattern(cur_r)}]"
            )
        elif mode == "accel_ff":
            self.mode_banner_text = "🌪 Aceleración FF: Curvas [Q-P], Evolución [A-L], Span [Z-M]"

        self._update_mode_buttons()
        self._sync_side_panel_controls()
        self._update_matrix_buttons()
        self._update_keyboard_labels()
        self.canvas.focus_set()

    def _exit_keyboard_mode(self):
        self.keyboard_mode = "normal"
        self.strum_target_mode = "all"
        self.mode_banner_text = ""
        self._update_mode_buttons()
        self._sync_side_panel_controls()
        self._update_matrix_buttons()
        self._update_keyboard_labels()
        self.canvas.focus_set()

    def _apply_chord_degree(self, degree_idx: int):
        self._cancel_pending_strum_afters()
        self.active_chord_degree = degree_idx
        active_balls = self._get_active_ball_indices()
        n_active = len(active_balls)
        if n_active == 0:
            return

        pitches = build_degree_chord_pitches(
            root_key=self.root_key_var.get(),
            base_octave=self.octave_var.get(),
            harmony_type=self.harmony_type_var.get(),
            degree_idx=degree_idx,
            n_pitches=n_active,
            inversion=self.active_chord_inversion,
            add_seventh=self.active_chord_seventh
        )

        for idx_in_active, ball_idx in enumerate(active_balls):
            p = self.system.pendulums[ball_idx]
            p.base_pitch = pitches[idx_in_active]

        chord_n = 4 if self.active_chord_seventh else 3
        self.active_chord_pitches = build_degree_chord_pitches(
            root_key=self.root_key_var.get(),
            base_octave=self.octave_var.get(),
            harmony_type=self.harmony_type_var.get(),
            degree_idx=degree_idx,
            n_pitches=chord_n,
            inversion=self.active_chord_inversion,
            add_seventh=self.active_chord_seventh
        )
        if self._is_chord_enabled_for_accompaniment():
            self.system.chord_pitches = list(self.active_chord_pitches)
        self.sounding_pendulum_pitches.clear()

        chord_name = get_degree_chord_name(
            root_key=self.root_key_var.get(),
            harmony_type=self.harmony_type_var.get(),
            degree_idx=degree_idx,
            with_seventh=self.active_chord_seventh
        )
        self.active_chord_label = chord_name
        inv_str = f" [Inv {self.active_chord_inversion}]" if self.active_chord_inversion > 0 else ""
        self.mode_banner_text = f"🎹 Acorde: {chord_name}{inv_str} en {n_active} bolas ON"

        # Audition when paused or live
        if not self.is_live_active:
            for idx_in_active, ball_idx in enumerate(active_balls):
                p = self.system.pendulums[ball_idx]
                self.audio_engine.play_note(
                    pitch=p.base_pitch,
                    velocity=90,
                    duration=0.5,
                    pan=p.pan,
                    pendulum_index=ball_idx
                )

        self._update_chord_controls()
        self._update_follow_indicator()
        self._update_matrix_buttons()
        self._update_keyboard_labels()

    def _rotate_chord_inversion(self):
        self.active_chord_inversion = (self.active_chord_inversion + 1) % 3
        self._apply_chord_degree(self.active_chord_degree)

    def _toggle_seventh(self):
        self.active_chord_seventh = not self.active_chord_seventh
        self._apply_chord_degree(self.active_chord_degree)

    def _handle_chords_mode_key(self, key_char: str):
        key_char = key_char.lower()
        degree_map = {
            "a": 0,  # I
            "s": 1,  # II
            "d": 2,  # III
            "f": 3,  # IV
            "g": 4,  # V
            "h": 5,  # VI
            "j": 6,  # VII
        }
        if key_char in degree_map:
            self._apply_chord_degree(degree_map[key_char])
            self._flash_key_ui(key_char.upper(), "al")
        elif key_char == "k":
            self._rotate_chord_inversion()
            self._flash_key_ui("K", "al")
        elif key_char == "l":
            self._toggle_seventh()
            self._flash_key_ui("L", "al")

    def _handle_accent_mode_key(self, key_char: str):
        key_char = key_char.lower()
        active_balls = self._get_active_ball_indices()

        if key_char == "a":
            # [A]: Suave / Pianissimo (pp)
            self.dynamic_mode_var.set("delicado")
            for b in active_balls:
                self.ball_custom_dynamics[b] = "delicado"
                if hasattr(self, 'system'):
                    self.system.custom_ball_dynamics[b] = "delicado"
            self.mode_banner_text = "🌙 Acentuación: SUAVE (Pianissimo pp - Golpe Dulce/Sutil)"
            self._flash_key_ui("A", "al")

        elif key_char == "s":
            # [S]: Forte / Fortissimo (ff)
            self.dynamic_mode_var.set("forte")
            for b in active_balls:
                self.ball_custom_dynamics[b] = "forte"
                if hasattr(self, 'system'):
                    self.system.custom_ball_dynamics[b] = "forte"
            self.mode_banner_text = "🔥 Acentuación: FORTE (Fortissimo ff - Máximo Impacto)"
            self._flash_key_ui("S", "al")

        elif key_char == "d":
            # [D]: Marcato (Golpe 1 ff enérgico, resto pp sutil)
            self.dynamic_mode_var.set("marcato")
            for b in active_balls:
                self.ball_custom_dynamics[b] = "marcato"
                if hasattr(self, 'system'):
                    self.system.custom_ball_dynamics[b] = "marcato"
            self.mode_banner_text = "🎯 Acentuación: MARCATO (Acento Fuerte en 1, resto Suave)"
            self._flash_key_ui("D", "al")

        elif key_char == "f":
            # [F]: Síncopa (Contratiempos ff, tierra pp)
            self.dynamic_mode_var.set("sincopa")
            for b in active_balls:
                self.ball_custom_dynamics[b] = "sincopa"
                if hasattr(self, 'system'):
                    self.system.custom_ball_dynamics[b] = "sincopa"
            self.mode_banner_text = "⚡ Acentuación: SÍNCOPA (Contratiempos Fuertes)"
            self._flash_key_ui("F", "al")

        elif key_char == "g":
            # [G]: Crescendo (De suave a muy fuerte)
            self.dynamic_mode_var.set("crescendo")
            for b in active_balls:
                self.ball_custom_dynamics[b] = "crescendo"
                if hasattr(self, 'system'):
                    self.system.custom_ball_dynamics[b] = "crescendo"
            self.mode_banner_text = "📈 Acentuación: CRESCENDO (De Suave a Fuerte en el Compás)"
            self._flash_key_ui("G", "al")

        elif key_char == "h":
            # [H]: Decrescendo (De muy fuerte a suave)
            self.dynamic_mode_var.set("decrescendo")
            for b in active_balls:
                self.ball_custom_dynamics[b] = "decrescendo"
                if hasattr(self, 'system'):
                    self.system.custom_ball_dynamics[b] = "decrescendo"
            self.mode_banner_text = "📉 Acentuación: DECRESCENDO (De Fuerte a Suave)"
            self._flash_key_ui("H", "al")

        elif key_char == "j":
            # [J]: Ghost notes (Alternancia acento fuerte / fantasma)
            self.dynamic_mode_var.set("ghost_notes")
            for b in active_balls:
                self.ball_custom_dynamics[b] = "ghost_notes"
                if hasattr(self, 'system'):
                    self.system.custom_ball_dynamics[b] = "ghost_notes"
            self.mode_banner_text = "👻 Acentuación: GHOST NOTES (Fuerte / Susurro Alterno)"
            self._flash_key_ui("J", "al")

        elif key_char == "k":
            # [K]: + Sensibilidad de Acento de Rasgueo
            new_sens = min(1.0, self.system.strum_accent_sensitivity + 0.25)
            self.system.strum_accent_sensitivity = new_sens
            for b in active_balls:
                self.ball_custom_strum_sens[b] = new_sens
                if hasattr(self, 'system'):
                    self.system.custom_ball_strum_sens[b] = new_sens
            self.mode_banner_text = f"✨ Sensibilidad Acento Rasgueo: {int(new_sens*100)}%"
            self._flash_key_ui("K", "al")

        elif key_char == "l":
            # [L]: - Sensibilidad de Acento de Rasgueo
            new_sens = max(0.0, self.system.strum_accent_sensitivity - 0.25)
            self.system.strum_accent_sensitivity = new_sens
            for b in active_balls:
                self.ball_custom_strum_sens[b] = new_sens
                if hasattr(self, 'system'):
                    self.system.custom_ball_strum_sens[b] = new_sens
            self.mode_banner_text = f"✨ Sensibilidad Acento Rasgueo: {int(new_sens*100)}%"
            self._flash_key_ui("L", "al")

        # Instant audition preview if live simulation is paused
        if not self.is_live_active:
            for b in active_balls:
                p = self.system.pendulums[b]
                test_vel = compute_dynamic_velocity(self.dynamic_mode_var.get(), 0, 4)
                self.audio_engine.play_note(
                    pitch=p.base_pitch,
                    velocity=test_vel,
                    duration=0.5,
                    pan=p.pan,
                    pendulum_index=b
                )

        self._update_matrix_buttons()
        self._update_keyboard_labels()
        self._update_hud_info()

    def _audition_strum_targets(self, targets: List[int]):
        """Silenced to ensure clean key navigation without cut-off sounds."""
        pass

    def _apply_palette_to_targets(self, pal_key: str, targets: List[int], msg: str):
        self.fill_palette_var.set(pal_key)
        for b in targets:
            self.ball_custom_palettes[b] = pal_key
            if hasattr(self, 'system'):
                self.system.custom_ball_palettes[b] = pal_key
        self.mode_banner_text = f"{msg} en {len(targets)} bolas"
        self._update_palette_button()

    def _apply_strum_side_key(
        self,
        key_char: str,
        side: str,
        step_keys: Tuple[str, ...],
        len_keys: Tuple[str, str],
        row_type: str,
        is_shift: bool = False,
    ):
        key_char = key_char.lower()
        targets = self._get_pattern_target_balls()
        if not targets:
            return
        is_all = self._is_pattern_all_mode()
        side_idx = 0 if side == 'left' else 1
        side_label = "◄ IDA" if side == 'left' else "► VTA"

        if key_char in step_keys:
            step_num = step_keys.index(key_char)
            if is_all:
                if is_shift:
                    all_tie = all(
                        step_num < len(self._get_ball_steps(tb)[side_idx])
                        and is_tie(self._get_ball_steps(tb)[side_idx][step_num])
                        for tb in targets
                    )
                    target_val = STEP_REST if all_tie else STEP_TIE
                else:
                    all_hit = all(
                        step_num < len(self._get_ball_steps(tb)[side_idx])
                        and is_hit(self._get_ball_steps(tb)[side_idx][step_num])
                        for tb in targets
                    )
                    all_tie = all(
                        step_num < len(self._get_ball_steps(tb)[side_idx])
                        and is_tie(self._get_ball_steps(tb)[side_idx][step_num])
                        for tb in targets
                    )
                    if all_hit:
                        target_val = STEP_TIE
                    elif all_tie:
                        target_val = STEP_REST
                    else:
                        target_val = STEP_HIT
                for tb in targets:
                    cur_left, cur_right = self._get_ball_steps(tb)
                    if side == 'left':
                        cur_left = set_pattern_step(cur_left, step_num, target_val)
                    else:
                        cur_right = set_pattern_step(cur_right, step_num, target_val)
                    self.ball_custom_strikes[tb] = (list(cur_left), list(cur_right))
                    self.system.custom_ball_strikes[tb] = (list(cur_left), list(cur_right))
            else:
                tb = targets[0]
                cur_left, cur_right = self._get_ball_steps(tb)
                if side == 'left':
                    cur_left = (
                        toggle_pattern_tie(cur_left, step_num)
                        if is_shift
                        else cycle_pattern_step(cur_left, step_num)
                    )
                    target_val = cur_left[step_num] if step_num < len(cur_left) else STEP_REST
                else:
                    cur_right = (
                        toggle_pattern_tie(cur_right, step_num)
                        if is_shift
                        else cycle_pattern_step(cur_right, step_num)
                    )
                    target_val = cur_right[step_num] if step_num < len(cur_right) else STEP_REST
                self.ball_custom_strikes[tb] = (list(cur_left), list(cur_right))
                self.system.custom_ball_strikes[tb] = (list(cur_left), list(cur_right))

            state_lbl = "x" if target_val == STEP_HIT else ("~" if target_val == STEP_TIE else "-")
            if is_all:
                self.mode_banner_text = (
                    f"🌐 TODAS ({len(targets)}b) {side_label} P{step_num+1}={state_lbl}"
                )
            else:
                fb = targets[0]
                fl, fr = self.ball_custom_strikes[fb]
                if side == 'left':
                    self.mode_banner_text = (
                        f"🎯 Bola {fb+1} ◄ IDA P{step_num+1}={state_lbl}: [{format_pattern(fl)}] │ ► [{format_pattern(fr)}]"
                    )
                else:
                    self.mode_banner_text = (
                        f"🎯 Bola {fb+1} ► VTA P{step_num+1}={state_lbl}: ◄ [{format_pattern(fl)}] │ ► [{format_pattern(fr)}]"
                    )
            self._sync_side_panel_controls()
            self._update_keyboard_labels()
            self._update_matrix_buttons()
            self._update_hud_info()
            ui_key = "Ñ" if key_char == "ñ" else key_char.upper()
            self._flash_key_ui(ui_key, row_type)
            for tb in targets:
                self._flash_matrix_step(tb, side, step_num)
            return

        if key_char in len_keys:
            delta = -1 if key_char == len_keys[0] else +1
            new_lens = self._step_target_side_length(side, delta)
            if new_lens:
                if is_all:
                    if len(set(new_lens)) == 1:
                        self.mode_banner_text = (
                            f"🌐 TODAS ({len(targets)}b) Long. {side_label} = {new_lens[0]} pasos"
                        )
                    else:
                        self.mode_banner_text = (
                            f"🌐 TODAS ({len(targets)}b) Long. {side_label} ({min(new_lens)}..{max(new_lens)}p)"
                        )
                else:
                    fb = targets[0]
                    cur_left, cur_right = self._get_ball_steps(fb)
                    if side == 'left':
                        self.mode_banner_text = (
                            f"🎯 Bola {fb+1} Long. ◄ IDA={len(cur_left)}: [{format_pattern(cur_left)}] │ ► [{format_pattern(cur_right)}]"
                        )
                    else:
                        self.mode_banner_text = (
                            f"🎯 Bola {fb+1} Long. ► VTA={len(cur_right)}: ◄ [{format_pattern(cur_left)}] │ ► [{format_pattern(cur_right)}]"
                        )
                ui_key = "Ñ" if key_char == "ñ" else key_char.upper()
                self._flash_key_ui(ui_key, row_type)

    def _handle_strum_qp_key(self, key_char: str, is_shift: bool = False):
        self._apply_strum_side_key(
            key_char,
            side='left',
            step_keys=("q", "w", "e", "r", "t", "y", "u", "i"),
            len_keys=("o", "p"),
            row_type="qp",
            is_shift=is_shift,
        )

    def _handle_strum_mode_key(self, key_char: str, is_shift: bool = False):
        self._apply_strum_side_key(
            key_char,
            side='right',
            step_keys=("a", "s", "d", "f", "g", "h", "j", "k"),
            len_keys=("l", "ñ"),
            row_type="al",
            is_shift=is_shift,
        )

    def _handle_strum_zm_key(self, key_char: str, is_shift: bool = False):
        key_char = key_char.lower()
        if not hasattr(self, 'system'):
            return

        use_all = is_shift or self._is_pattern_all_mode()
        targets = self._get_pattern_target_balls(force_all=use_all)
        if not targets:
            return
        target_str = f"TODAS ({len(targets)} bolas)" if use_all else f"Bola {targets[0] + 1}"

        op_names = {
            "z": "⏪ Rotar Izq",
            "x": "⏩ Rotar Der",
            "c": "🌗 Invertir (x↔-)",
            "v": "📋 Copiar Ida → Vta",
            "b": "⇄ Espejo Ida ⇄ Vta",
            "n": "🥁 Euclidiano",
            "m": "🎲 Aleatorio",
            ",": "🔥 Rellenar (x)",
            ".": "↺ Reset 1+1",
        }
        if key_char not in op_names:
            return

        for b in targets:
            cur_l, cur_r = self._get_ball_steps(b)
            if key_char == "z":
                new_l, new_r = rotate_pattern(cur_l, -1), rotate_pattern(cur_r, -1)
            elif key_char == "x":
                new_l, new_r = rotate_pattern(cur_l, +1), rotate_pattern(cur_r, +1)
            elif key_char == "c":
                new_l, new_r = invert_pattern(cur_l), invert_pattern(cur_r)
            elif key_char == "v":
                new_l, new_r = list(cur_l), list(cur_l)
            elif key_char == "b":
                new_l, new_r = list(cur_r), list(cur_l)
            elif key_char == "n":
                new_l = generate_random_pattern_side(len(cur_l), "euclidean")
                new_r = generate_random_pattern_side(len(cur_r), "euclidean")
            elif key_char == "m":
                new_l = generate_random_pattern_side(len(cur_l), "random")
                new_r = generate_random_pattern_side(len(cur_r), "random")
            elif key_char == ",":
                new_l = [STEP_HIT] * len(cur_l)
                new_r = [STEP_HIT] * len(cur_r)
            else:  # "."
                new_l = [STEP_HIT] + [STEP_REST] * (DEFAULT_PATTERN_STEPS - 1)
                new_r = [STEP_HIT] + [STEP_REST] * (DEFAULT_PATTERN_STEPS - 1)

            self.ball_custom_strikes[b] = (list(new_l), list(new_r))
            self.system.custom_ball_strikes[b] = (list(new_l), list(new_r))

        first_b = targets[0]
        fl, fr = self.ball_custom_strikes[first_b]
        if use_all and key_char in ("n", "m"):
            self.mode_banner_text = f"{op_names[key_char]} ({target_str} — patrón independiente por bola)"
        elif use_all and key_char == ".":
            self.mode_banner_text = (
                f"↺ Todos a 1+1 ({target_str}): ◄ [{format_pattern(fl)}] │ ► [{format_pattern(fr)}]"
            )
        elif use_all:
            self.mode_banner_text = f"{op_names[key_char]} ({target_str})"
        else:
            self.mode_banner_text = (
                f"{op_names[key_char]} ({target_str}): ◄ [{format_pattern(fl)}] │ ► [{format_pattern(fr)}]"
            )
        self._sync_side_panel_controls()
        self._update_keyboard_labels()
        self._update_matrix_buttons()
        self._update_hud_info()
        self._flash_key_ui(key_char.upper(), "zm")

    def _handle_strum_num_key(self, num_char: str, is_shift: bool = False):
        """In strum_dd, 0 toggles ALL-patterns mode (Shift+0 selects Ball 10 if present), 1-9 select a ball."""
        if num_char == "0":
            if is_shift and hasattr(self, 'system') and len(self.system.pendulums) >= 10:
                idx = 9
                self.strum_target_mode = "single"
                self._select_ball(idx)
                p = self.system.pendulums[idx]
                cur_l, cur_r = self._get_ball_steps(idx)
                self.mode_banner_text = (
                    f"🎯 Bola {idx + 1} ({midi_to_note_name(p.base_pitch)}): "
                    f"◄ [{format_pattern(cur_l)}] │ ► [{format_pattern(cur_r)}]"
                )
                self._update_matrix_buttons()
                self._update_keyboard_labels()
                self._update_hud_info()
                self._flash_key_ui(num_char, "num")
            else:
                self._toggle_pattern_all_mode()
            return

        idx = int(num_char) - 1
        if hasattr(self, 'system') and idx < len(self.system.pendulums):
            self.strum_target_mode = "single"
            self._select_ball(idx)
            p = self.system.pendulums[idx]
            cur_l, cur_r = self._get_ball_steps(idx)
            self.mode_banner_text = (
                f"🎯 Bola {idx + 1} ({midi_to_note_name(p.base_pitch)}): "
                f"◄ [{format_pattern(cur_l)}] │ ► [{format_pattern(cur_r)}]"
            )
            self._update_matrix_buttons()
            self._update_keyboard_labels()
            self._update_hud_info()
            self._flash_key_ui(num_char, "num")

    def _handle_accel_qp_key(self, key_char: str):
        """Modo FF - Fila 1 [Q-P]: Curvas y Ratios de Aceleración Interna de Notas."""
        key_char = key_char.lower()
        targets = self._get_active_ball_indices()
        if not targets:
            return

        curve_map = {
            "q": ("uniform", 1.0, "⏱ UNIFORME (1.0 - Intervalos idénticos)", "Q"),
            "w": ("rasgueo_soft", 0.85, "🎸 ACELERANDO LEVE (0.85)", "W"),
            "e": ("rasgueo_guitar", 0.72, "🎸 GUITARRA CLÁSICA (0.72 - Acelerando)", "E"),
            "r": ("rasgueo_fast", 0.60, "🔥 FLAMENCO (0.60 - Rasgueo ágil)", "R"),
            "t": ("ultra_fast", 0.45, "⚡ FLAMENCO ULTRA-RÁPIDO (0.45 - Ráfaga)", "T"),
            "y": ("hyper_fast", 0.30, "🌪 RÁFAGA HIPER-RÁPIDA (0.30 - Tornado)", "Y"),
            "u": ("arpeggio_decel", 1.50, "🌊 DECELERANDO LEVE (1.50 - Apertura)", "U"),
            "i": ("decel_marked", 1.80, "🌊 DECELERANDO MARCADO (1.80)", "I"),
            "o": ("hyper_decel", 2.20, "🌊 FRENO FUERTE (2.20 - Desacelerando)", "O"),
            "p": ("ultra_open", 3.20, "✨ CASCADA HIPER-EXPANSIVA (3.20 - Abanico máximo)", "P"),
        }

        if key_char in curve_map:
            prog_key, ratio_val, desc, ui_key = curve_map[key_char]
            self.strum_progression_var.set(prog_key)
            for b in targets:
                self.ball_custom_strum_ratio[b] = ratio_val
                if hasattr(self, 'system'):
                    self.system.custom_ball_strum_ratio[b] = ratio_val
            self.mode_banner_text = f"Curva de Notas: {desc} en {len(targets)} bolas"
            self._flash_key_ui(ui_key, "qp")

        self._audition_strum_targets(targets)
        self._sync_side_panel_controls()
        self._update_keyboard_labels()
        self._update_hud_info()

    def _handle_accel_al_key(self, key_char: str):
        """Modo FF - Fila 2 [A-L]: Evolución Dinámica Cruce a Cruce."""
        key_char = key_char.lower()
        evol_map = {
            "a": ("off", "DESACTIVADA (Estático / Sin evolución)", "A"),
            "s": ("accel", "ACELERANDO ↗ (Cada cruce se acelera en ciclo de 4 pasos)", "S"),
            "d": ("decel", "DECELERANDO ↘ (Cada cruce se expande y frena)", "D"),
            "f": ("breathe", "RESPIRACIÓN ∿ (Modulación sinusoidal según el compás)", "F"),
            "g": ("altern", "ALTERNANTE ⇄ (Ida en ráfaga rápida, vuelta decelerando)", "G"),
            "h": ("chaos", "CAOS 🎲 (Micro-variaciones orgánicas +/- 25%)", "H"),
            "j": ("wave", "ONDA TRIANGULAR ⋀ (Crescendo/Decrescendo en 8 compases)", "J"),
            "k": ("pairs_alt", "PARES / IMPARES ⇅ (Pares aceleran, impares frenan)", "K"),
            "l": ("retro_flip", "RETRO-FLIP ↺ (Invierte la curva entre ida y vuelta)", "L"),
        }

        if key_char in evol_map:
            mode_key, desc, ui_key = evol_map[key_char]
            self.strum_evolving_mode = mode_key
            self.mode_banner_text = f"🌊 Evolución Temporal: {desc}"
            self._flash_key_ui(ui_key, "al")

        targets = self._get_active_ball_indices()
        self._audition_strum_targets(targets)
        self._sync_side_panel_controls()
        self._update_keyboard_labels()
        self._update_hud_info()

    def _handle_accel_zm_key(self, key_char: str):
        """Modo FF - Fila 3 [Z-M]: Multiplicador de Velocidad de Recorrido (Span)."""
        key_char = key_char.lower()
        targets = self._get_active_ball_indices()

        span_map = {
            "z": (0.3, "0.3x (Micro-ráfaga instantánea 25-40ms)", "Z"),
            "x": (0.5, "0.5x (Ultrarrápido 50-80ms)", "X"),
            "c": (0.8, "0.8x (Ágil / Fluido 100-130ms)", "C"),
            "v": (1.0, "1.0x (Normal / Tiempo Estándar ~160ms)", "V"),
            "b": (1.6, "1.6x (Amplio / Espaciado ~250ms)", "B"),
            "n": (2.5, "2.5x (Dilatado / Cascada Lenta ~400ms)", "N"),
            "m": (3.5, "3.5x (Hiper-Dilatado / Despliegue Máximo ~600ms)", "M"),
        }

        if key_char in span_map:
            spd_val, desc, ui_key = span_map[key_char]
            self.strum_speed_factor = spd_val
            self.mode_banner_text = f"⚡ Velocidad Span de Notas: {desc}"
            self._flash_key_ui(ui_key, "zm")

        self._audition_strum_targets(targets)
        self._sync_side_panel_controls()
        self._update_keyboard_labels()
        self._update_hud_info()

    def _on_al_button_click(self, key_char: str):
        key_char = key_char.lower()
        if self.keyboard_mode == "chords_aa":
            self._handle_chords_mode_key(key_char)
        elif self.keyboard_mode == "accent_ss":
            self._handle_accent_mode_key(key_char)
        elif self.keyboard_mode == "strum_dd":
            self._handle_strum_mode_key(key_char)
        elif self.keyboard_mode == "accel_ff":
            self._handle_accel_al_key(key_char)
        else:
            self._on_solo_press(key_char)

    def _on_al_button_release(self, key_char: str):
        key_char = key_char.lower()
        if self.keyboard_mode == "normal":
            self._schedule_solo_release(key_char)

    # -------------------------------------------------------------
    # BEAT-QUANTIZED MELODIC SOLO LEAD (Compás Sync & Bar Closure)
    # -------------------------------------------------------------
    def _set_solo_ui_state(self, key_char: str, state: str):
        if not hasattr(self, 'al_labels') or key_char not in self.al_labels:
            return
        lbl = self.al_labels[key_char]
        if state == "idle":
            lbl.config(bg="#193327", fg="#6ee7b7", relief=tk.RAISED)
        elif state == "queued":
            # Amber/gold ready tint: user pressed, waiting for upcoming beat of compás
            lbl.config(bg="#065f46", fg="#facc15", relief=tk.SUNKEN)
        elif state == "sounding":
            # Glowing emerald: sounding actively on the beat
            lbl.config(bg="#34d399", fg="#000000", relief=tk.SUNKEN)

    def _on_solo_press(self, active_k: str):
        active_k = active_k.lower()
        key_id = f"al_{active_k}"

        # Cancel any pending release from OS key repeat debounce
        if key_id in self.pending_releases:
            try:
                self.root.after_cancel(self.pending_releases.pop(key_id))
            except Exception:
                pass
            return "break"

        if active_k in self.solo_held_keys:
            return "break"

        self.solo_held_keys.add(active_k)

        # If live simulation is paused, allow immediate sound audition
        if not self.is_live_active:
            self._trigger_solo_preview(active_k)
            return "break"

        # When live active: quantize onset strictly to the beats of the compás
        beat_sec = 60.0 / self.system.tempo_bpm
        sig_data = TIME_SIGNATURES.get(self.time_sig_var.get(), TIME_SIGNATURES['4/4'])
        numerator = sig_data['numerator']

        current_total_beat = int(math.floor(self.anim_time / beat_sec))
        beat_in_bar = current_total_beat % numerator
        time_into_beat = self.anim_time - current_total_beat * beat_sec
        grace_window = min(0.08, beat_sec * 0.18)

        if time_into_beat <= grace_window:
            # Within musical onset tolerance of current beat -> trigger immediately on this beat
            for other_k, note_info in list(self.solo_active_notes.items()):
                dur_sec = max(0.08, note_info['beats_played'] * beat_sec)
                ch = note_info.get('channel')
                if ch:
                    if self.sustain_pedal_active:
                        self.sustained_channels.append(ch)
                    else:
                        self.audio_engine.stop_channel(ch, fadeout_ms=40)
                rec_ev = note_info.get('rec_ev')
                if rec_ev:
                    self.audio_engine.recorder.update_event_duration(rec_ev, dur_sec)
                del self.solo_active_notes[other_k]
                self._set_solo_ui_state(other_k.upper(), "idle")

            self._trigger_solo_note_sound(active_k, current_total_beat, beat_in_bar, numerator, beat_sec)
        else:
            # Mid-beat: queue to strike synchronously on the upcoming beat of the compás
            next_total_beat = current_total_beat + 1
            self.solo_queued_triggers[active_k] = {
                'target_total_beat': next_total_beat
            }
            self._set_solo_ui_state(active_k.upper(), "queued")

        return "break"

    def _schedule_solo_release(self, active_k: str):
        active_k = active_k.lower()
        key_id = f"al_{active_k}"
        if key_id in self.pending_releases:
            try:
                self.root.after_cancel(self.pending_releases[key_id])
            except Exception:
                pass
        after_id = self.root.after(25, lambda: self._execute_solo_release(active_k))
        self.pending_releases[key_id] = after_id

    def _execute_solo_release(self, active_k: str):
        key_id = f"al_{active_k}"
        self.pending_releases.pop(key_id, None)
        self.solo_held_keys.discard(active_k)

        # If live simulation is paused and was previewing:
        if not self.is_live_active:
            info = self.held_notes.pop(key_id, None)
            if info and info.get('channel'):
                self.audio_engine.stop_channel(info['channel'], fadeout_ms=60)
            self._set_solo_ui_state(active_k.upper(), "idle")
            return

        # When live active: duration is quantized to the beat.
        # If active note is playing, it will cleanly sustain until the end of the current beat
        # (or last beat of compás) inside _on_beat_advance.
        # If neither active nor queued, restore idle UI.
        if active_k not in self.solo_active_notes and active_k not in self.solo_queued_triggers:
            self._set_solo_ui_state(active_k.upper(), "idle")

    def _trigger_solo_preview(self, active_k: str):
        al_keys = ["a", "s", "d", "f", "g", "h", "j", "k", "l"]
        if active_k not in al_keys:
            return
        idx = al_keys.index(active_k)
        pool = self.system.scale_notes
        base_p = pool[idx % len(pool)]
        octave = (idx // len(pool) + 1) * 12
        pitch = min(108, base_p + octave)
        key_id = f"al_{active_k}"

        p_idx = idx if self.timbre_var.get() == "drums" else (idx % self.system.n_pendulums)
        ch, rec_ev = self.audio_engine.play_note(
            pitch=pitch,
            velocity=115,
            duration=1.5,
            pan=0.0,
            pendulum_index=p_idx
        )
        self.held_notes[key_id] = {
            'start_time': time.time(),
            'channel': ch,
            'rec_ev': rec_ev,
            'row_type': 'al',
            'char': active_k.upper()
        }
        self._set_solo_ui_state(active_k.upper(), "sounding")

    def _trigger_solo_note_sound(self, active_k: str, b_total: int, beat_in_bar: int, numerator: int, beat_sec: float):
        al_keys = ["a", "s", "d", "f", "g", "h", "j", "k", "l"]
        if active_k not in al_keys:
            return
        idx = al_keys.index(active_k)
        pool = self.system.scale_notes
        base_p = pool[idx % len(pool)]
        octave = (idx // len(pool) + 1) * 12
        pitch = min(108, base_p + octave)

        # Max duration in current bar: from current beat to the end of the last beat of the compás
        beats_until_bar_end = max(1, numerator - beat_in_bar)
        sound_dur = max(1.0, beats_until_bar_end * beat_sec + 0.5)

        p_idx = idx if self.timbre_var.get() == "drums" else (idx % self.system.n_pendulums)
        ch, rec_ev = self.audio_engine.play_note(
            pitch=pitch,
            velocity=115,
            duration=sound_dur,
            pan=0.0,
            pendulum_index=p_idx
        )

        self.solo_active_notes[active_k] = {
            'key': active_k,
            'pitch': pitch,
            'channel': ch,
            'rec_ev': rec_ev,
            'start_beat_total': b_total,
            'start_beat_in_bar': beat_in_bar,
            'beats_played': 1,
            'start_time': time.time()
        }

        self._set_solo_ui_state(active_k.upper(), "sounding")

    def _on_beat_advance(self, b_total: int, numerator: int, beat_sec: float):
        if not hasattr(self, 'pitch_follow'):
            return
        beat_in_bar = b_total % max(1, numerator)
        committed_midi = self.pitch_follow.on_beat_advance(b_total, beat_in_bar, numerator)
        if committed_midi is not None:
            self._apply_accompaniment_pitch(committed_midi)

    def _cycle_timbre(self):
        timbres = self._get_instrument_list()
        cur = self.timbre_var.get()
        nxt = timbres[(timbres.index(cur) + 1) % len(timbres)] if cur in timbres else timbres[0]
        self.timbre_var.set(nxt)
        self._on_timbre_change()

    def _cycle_harmony(self):
        harm_keys = list(HARMONIC_TYPES.keys())
        cur = self.harmony_type_var.get()
        nxt = harm_keys[(harm_keys.index(cur) + 1) % len(harm_keys)] if cur in harm_keys else harm_keys[0]
        self.harmony_type_var.set(nxt)
        self.harm_combo.current(harm_keys.index(nxt))
        self._init_system()

    def _cycle_time_signature(self):
        sigs = list(TIME_SIGNATURES.keys())
        cur = self.time_sig_var.get()
        nxt = sigs[(sigs.index(cur) + 1) % len(sigs)] if cur in sigs else "4/4"
        self.time_sig_var.set(nxt)
        self._init_system()

    def _cycle_dynamic(self, delta: int = 1):
        modes = list(DYNAMIC_MODES.keys())
        cur = self.dynamic_mode_var.get()
        idx = modes.index(cur) if cur in modes else 0
        nxt = modes[(idx + delta) % len(modes)]
        self.dynamic_mode_var.set(nxt)
        if hasattr(self, 'dyn_combo'):
            self.dyn_combo.current(modes.index(nxt))
        self.system.set_dynamic_mode(nxt)
        self._update_hud_info()

    def _on_dynamic_selected(self, event=None):
        modes = list(DYNAMIC_MODES.keys())
        sel_idx = self.dyn_combo.current() if hasattr(self, 'dyn_combo') else -1
        if 0 <= sel_idx < len(modes):
            nxt = modes[sel_idx]
            self.dynamic_mode_var.set(nxt)
            self.system.set_dynamic_mode(nxt)
            self._update_hud_info()
        self.canvas.focus_set()

    def _toggle_voicing(self):
        cur = self.voicing_var.get()
        nxt = "open" if cur == "linear" else "linear"
        self.voicing_var.set(nxt)
        self._init_system()

    def _update_strike_button(self):
        pat = self.strike_pattern_var.get()
        mode = self.strike_mode_var.get()
        mode_prefix = "🎯 Unís" if mode == "unison" else "⇄ Bilat"
        pat_name = STRIKE_PATTERNS.get(pat, {}).get('short', pat)
        color_map = {
            '1+1': '#334155' if mode != 'unison' else '#d97706',
            '1+2': '#0284c7',
            '2+1': '#7c3aed',
            '2+2': '#ea580c',
            '1+3': '#059669',
            '3+1': '#db2777',
            '3+3': '#8b5cf6',
            '1+4': '#0891b2',
            '4+1': '#c026d3',
            '4+4': '#e11d48',
            '1+5': '#0d9488',
            '5+1': '#d97706',
            '5+5': '#4f46e5',
            '1+6': '#059669',
            '6+1': '#b91c1c',
            '6+6': '#059669',
            '6+0': '#047857',
            '0+6': '#047857',
            '1+0': '#475569',
            '0+1': '#475569',
        }
        bg_col = color_map.get(pat, '#334155')
        if hasattr(self, 'btn_strike'):
            self.btn_strike.config(
                text=f"{mode_prefix} [{pat_name}]",
                bg=bg_col,
                fg="#ffffff"
            )

    def _toggle_strike_mode(self):
        cycle_patterns = [
            ("bilateral", "1+1"),
            ("bilateral", "1+2"),
            ("bilateral", "2+1"),
            ("bilateral", "2+2"),
            ("bilateral", "1+3"),
            ("bilateral", "3+1"),
            ("bilateral", "3+3"),
            ("bilateral", "1+6"),
            ("bilateral", "6+1"),
            ("bilateral", "6+6"),
            ("unison", "1+1"),
            ("unison", "1+2"),
            ("unison", "2+1"),
            ("unison", "6+6"),
        ]
        cur = (self.strike_mode_var.get(), self.strike_pattern_var.get())
        if cur in cycle_patterns:
            nxt_idx = (cycle_patterns.index(cur) + 1) % len(cycle_patterns)
        else:
            nxt_idx = 0
        nxt_mode, nxt_pat = cycle_patterns[nxt_idx]
        self.strike_mode_var.set(nxt_mode)
        self.strike_pattern_var.set(nxt_pat)
        self._update_strike_button()
        self._init_system()

    def _show_strike_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        menu.add_command(label="🎯 TIPOS DE GOLPE (HASTA 6 COMO GUITARRA)", state="disabled")
        menu.add_separator()

        cur_mode = self.strike_mode_var.get()
        cur_pat = self.strike_pattern_var.get()

        # Categorize patterns for easier selection
        guitar_keys = ['6+6', '6+1', '1+6', '6+0', '0+6']
        guitar_sub = tk.Menu(menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        for pk in guitar_keys:
            if pk in STRIKE_PATTERNS:
                p_info = STRIKE_PATTERNS[pk]
                mark = "✓ " if (cur_pat == pk) else "   "
                guitar_sub.add_command(
                    label=f"{mark}{p_info['name']} - {p_info['desc']}",
                    command=lambda k=pk: self._select_strike_pattern(k)
                )
        menu.add_cascade(label="🎸 Guitarra (6 Cuerdas / Arpegio y Rasgueo)", menu=guitar_sub)

        multi_keys = ['1+1', '1+2', '2+1', '2+2', '1+3', '3+1', '3+3', '1+4', '4+1', '4+4', '1+5', '5+1', '5+5']
        std_sub = tk.Menu(menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        for pk in multi_keys:
            if pk in STRIKE_PATTERNS:
                p_info = STRIKE_PATTERNS[pk]
                mark = "✓ " if (cur_pat == pk) else "   "
                std_sub.add_command(
                    label=f"{mark}{p_info['name']} - {p_info['desc']}",
                    command=lambda k=pk: self._select_strike_pattern(k)
                )
        menu.add_cascade(label="🎼 Estándar, Dobles, Tresillos, Cuatrillos, Quintillos", menu=std_sub)

        solo_keys = ['1+0', '0+1', '2+0', '0+2', '3+0', '0+3', '4+0', '0+4', '5+0', '0+5', '6+0', '0+6']
        solo_sub = tk.Menu(menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        for pk in solo_keys:
            if pk in STRIKE_PATTERNS:
                p_info = STRIKE_PATTERNS[pk]
                mark = "✓ " if (cur_pat == pk) else "   "
                solo_sub.add_command(
                    label=f"{mark}{p_info['name']} - {p_info['desc']}",
                    command=lambda k=pk: self._select_strike_pattern(k)
                )
        menu.add_cascade(label="⏸ Silencios Unilaterales (Solo Izq / Solo Der)", menu=solo_sub)

        menu.add_separator()
        mode_label = "Cambiar a Unísono (Mismo Tono)" if cur_mode == "bilateral" else "Cambiar a Bilateral (Alterna Tono)"
        menu.add_command(
            label=f"⇄ {mode_label}",
            command=self._toggle_harmonic_strike_mode
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _select_strike_pattern(self, pattern_key: str):
        self.strike_pattern_var.set(pattern_key)
        self._update_strike_button()
        self._init_system()

    def _toggle_harmonic_strike_mode(self):
        cur = self.strike_mode_var.get()
        self.strike_mode_var.set("unison" if cur == "bilateral" else "bilateral")
        self._update_strike_button()
        self._init_system()

    def _update_palette_button(self):
        pal_k = self.fill_palette_var.get()
        p_info = HARMONIC_FILL_PALETTES.get(pal_k, {})
        short_name = p_info.get('short', p_info.get('name', pal_k))
        color_map = {
            'chord_arpeggio': '#4338ca',
            'guitar_strum': '#10b981',
            'scale_run_loop': '#059669',
            'scale_run_oneshot': '#d97706',
            'scale_run_pingpong': '#7c3aed',
            'scale_run_pingpong_oneshot': '#9333ea',
            'scale_run_pool': '#0891b2',
            'scale_step': '#0284c7',
            'power_fifths': '#6366f1',
            'ornament': '#db2777',
            'unison': '#334155',
        }
        bg_col = color_map.get(pal_k, '#4338ca')
        if hasattr(self, 'btn_palette'):
            self.btn_palette.config(
                text=f"🎨 {short_name}",
                bg=bg_col,
                fg="#ffffff"
            )

    def _reset_ball_strike_counter(self, ball_idx=None):
        self._cancel_pending_strum_afters(include_strums=False)
        self._arm_scale_run_on_ida(ball_idx=ball_idx, reset_clock_if_paused=True)
        self._update_keyboard_labels()
        self._update_hud_info()
        self._update_matrix_buttons()

    def _cycle_fill_palette(self):
        keys = list(HARMONIC_FILL_PALETTES.keys())
        cur = self.fill_palette_var.get()
        nxt_idx = (keys.index(cur) + 1) % len(keys) if cur in keys else 0
        self.fill_palette_var.set(keys[nxt_idx])
        self._update_palette_button()
        self._init_system()

    def _select_fill_palette(self, pal_key: str):
        self.fill_palette_var.set(pal_key)
        self._update_palette_button()
        self._init_system()

    def _show_fill_palette_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        menu.add_command(label="🎨 PALETA ARMÓNICA DE MULTI-GOLPES", state="disabled")
        menu.add_separator()

        cur_pal = self.fill_palette_var.get()
        for pk, p_info in HARMONIC_FILL_PALETTES.items():
            is_active = (cur_pal == pk)
            mark = "✓ " if is_active else "   "
            menu.add_command(
                label=f"{mark}{p_info['name']} - {p_info['desc']}",
                command=lambda k=pk: self._select_fill_palette(k)
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _set_ball_palette(self, ball_idx: int, pal_key: str):
        if pal_key == "global" or pal_key is None:
            self.ball_custom_palettes.pop(ball_idx, None)
            if hasattr(self, 'system'):
                self.system.custom_ball_palettes.pop(ball_idx, None)
        else:
            self.ball_custom_palettes[ball_idx] = pal_key
            if hasattr(self, 'system'):
                self.system.custom_ball_palettes[ball_idx] = pal_key
        self._arm_scale_run_on_ida(ball_idx=ball_idx, reset_clock_if_paused=True)
        self._update_keyboard_labels()

    def _trigger_secondary_strike(self, idx: int, pitch: int, vel: int, dur: float, pan: float, side: str = 'right', strike_idx: int = 1):
        if not self.is_live_active:
            return
        if self.anim_time < self.pendulum_mutes.get(idx, 0.0):
            return
        self.audio_engine.play_note(
            pitch=pitch,
            velocity=vel,
            duration=dur,
            pan=pan,
            pendulum_index=idx
        )
        self.active_flashes[idx] = 10
        if hasattr(self, 'pilot_flashes') and idx in self.pilot_flashes:
            if strike_idx < len(self.pilot_flashes[idx][side]):
                self.pilot_flashes[idx][side][strike_idx] = 10
            self.pilot_flashes[idx]['last_dir'] = side

    def _update_rhythm_button(self):
        nxt = self.rhythm_mode_var.get()
        if nxt == "sync":
            self.btn_rhythm.config(text="🔒 Ritmo Compás", bg="#2ec4b6", fg="#0f1117")
        elif nxt == "gaps":
            self.btn_rhythm.config(text="🌌 Huecos y Respiros", bg="#0284c7", fg="#ffffff")
        elif nxt == "beat_pulse":
            self.btn_rhythm.config(text="⚡ Pulso Beat (Sin silencios)", bg="#f43f5e", fg="#ffffff")
        elif nxt == "wave":
            self.btn_rhythm.config(text="🌊 Onda Armónica", bg="#8338ec", fg="#ffffff")

    def _toggle_rhythm_mode(self):
        modes = ["sync", "gaps", "beat_pulse", "wave"]
        cur = self.rhythm_mode_var.get()
        nxt = modes[(modes.index(cur) + 1) % len(modes)] if cur in modes else "sync"
        self.rhythm_mode_var.set(nxt)
        self._update_rhythm_button()
        self._init_system()

    def _show_soundscape_menu(self):
        menu = tk.Menu(
            self.root, tearoff=0, bg="#1e2230", fg="#cad3f5",
            activebackground="#0d9488", activeforeground="#ffffff"
        )
        menu.add_command(label="🌌 PAISAJES SONOROS DE ÓRGANO", state="disabled")
        menu.add_separator()
        for key, info in SOUNDSCAPE_PRESETS.items():
            mark = "✓ " if self.timbre_var.get() == info['timbre'] else "   "
            menu.add_command(
                label=f"{mark}{info['label']} ({info['timbre']} • {info['root']}{info['octave']})",
                command=lambda k=key: self._apply_soundscape_preset(k)
            )

        organ_banks = [inst for inst in self._get_instrument_list() if 'organ' in inst.lower()]
        if organ_banks:
            menu.add_separator()
            bank_sub = tk.Menu(
                menu, tearoff=0, bg="#1e2230", fg="#cad3f5",
                activebackground="#0d9488", activeforeground="#ffffff"
            )
            for inst in organ_banks:
                mark = "✓ " if self.timbre_var.get() == inst else "   "
                bank_sub.add_command(
                    label=f"{mark}{inst}",
                    command=lambda name=inst: self._select_organ_instrument(name)
                )
            menu.add_cascade(label="🎹 Cambiar Solo Timbre de Órgano", menu=bank_sub)

        x = self.btn_paisajes.winfo_rootx()
        y = self.btn_paisajes.winfo_rooty() + self.btn_paisajes.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _select_organ_instrument(self, inst_name: str):
        self.timbre_var.set(inst_name)
        self._on_timbre_change()
        self.canvas.focus_set()

    def _apply_soundscape_preset(self, preset_key: str):
        p = SOUNDSCAPE_PRESETS.get(preset_key)
        if not p:
            return

        # Clear per-ball overrides so the soundscape voice balance is cohesive
        self.ball_custom_strikes.clear()
        self.ball_custom_dynamics.clear()
        self.ball_custom_durations.clear()
        self.ball_custom_palettes.clear()
        self.ball_custom_drum_voices.clear()
        self.pendulum_mutes.clear()
        bank_obj = get_sample_engine().get_bank(p['timbre'], load=False)
        if bank_obj:
            bank_obj.custom_pendulum_map.clear()

        # Apply preset state to all Tk variables
        self.timbre_var.set(p['timbre'])
        self.root_key_var.set(p['root'])
        self.octave_var.set(p['octave'])
        self.harmony_type_var.set(p['harmony'])
        self.voicing_var.set(p['voicing'])
        self.n_pendulums_var.set(p['n_pendulums'])
        self.rhythm_mode_var.set(p['rhythm_mode'])
        self.strike_mode_var.set(p['strike_mode'])
        self.strike_pattern_var.set(p['strike_pattern'])
        self.fill_palette_var.set(p['fill_palette'])
        self.duration_mode_var.set(p['duration_mode'])
        self.dynamic_mode_var.set(p['dynamic_mode'])
        self.bpm_var.set(p['bpm'])
        self.decay_var.set(p['decay'])

        # Sync widgets and audio controls
        harm_keys = list(HARMONIC_TYPES.keys())
        if hasattr(self, 'harm_combo') and p['harmony'] in harm_keys:
            self.harm_combo.current(harm_keys.index(p['harmony']))

        dur_keys = list(NOTE_DURATIONS.keys())
        if hasattr(self, 'dur_combo') and p['duration_mode'] in dur_keys:
            self.dur_combo.current(dur_keys.index(p['duration_mode']))

        dyn_keys = list(DYNAMIC_MODES.keys())
        if hasattr(self, 'dyn_combo') and p['dynamic_mode'] in dyn_keys:
            self.dyn_combo.current(dyn_keys.index(p['dynamic_mode']))

        if hasattr(self, 'bpm_label'):
            self.bpm_label.config(text=self._format_bpm(p['bpm']))

        if hasattr(self, 'decay_label'):
            self.decay_label.config(text=f"{p['decay']:.1f}x")
        self.audio_engine.set_decay(p['decay'])

        self._update_rhythm_button()
        self._update_strike_button()
        self._update_palette_button()
        self.mode_banner_text = f"🌌 Paisaje Activo: {p['label']}"

        self._init_system(update_follow_home=True, recenter_keyboard=True)
        self._on_timbre_change()
        self.canvas.focus_set()

    def _parse_silence_bars(self) -> Optional[int]:
        """Returns integer bars from silence_bars_var, or None for Permanente."""
        val = str(self.silence_bars_var.get()).strip()
        if val.lower().startswith("perm"):
            return None
        try:
            return max(1, int(val))
        except (ValueError, TypeError):
            return 2

    def _on_silence_bars_changed(self, event=None):
        self._update_pause_button()
        self.canvas.focus_set()

    def _toggle_ball_silence(self, ball_index: int):
        """Silences or unmutes an individual ball for a predetermined duration in bars or permanently."""
        if ball_index >= self.system.n_pendulums:
            return
        now = self.anim_time

        if now < self.pendulum_mutes.get(ball_index, 0.0):
            # Already muted -> Unmute immediately!
            self.pendulum_mutes[ball_index] = 0.0
        else:
            silence_bars = self._parse_silence_bars()
            if silence_bars is None:
                self.pendulum_mutes[ball_index] = float('inf')
            else:
                bar_sec = max(0.5, self.system.bar_duration_sec)
                self.pendulum_mutes[ball_index] = now + (silence_bars * bar_sec)

        # Update button text/appearance
        if hasattr(self, 'btn_mute_b1') and ball_index == 0:
            is_m = self.anim_time < self.pendulum_mutes.get(0, 0.0)
            self.btn_mute_b1.config(bg="#ef4444" if is_m else "#252b3b", fg="#ffffff" if is_m else "#f87171")
        if hasattr(self, 'btn_mute_b2') and ball_index == 1:
            is_m = self.anim_time < self.pendulum_mutes.get(1, 0.0)
            self.btn_mute_b2.config(bg="#ef4444" if is_m else "#252b3b", fg="#ffffff" if is_m else "#f87171")
        self._update_keyboard_labels()

    def _show_ball_properties_menu(self, event, ball_idx: int):
        """Right-click popup context menu to configure individual dynamism and duration per ball."""
        if ball_idx >= self.system.n_pendulums:
            return
        p = self.system.pendulums[ball_idx]
        note_name = midi_to_note_name(p.base_pitch)

        menu = tk.Menu(self.root, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        menu.add_command(label=f"🎵 BOLA {ball_idx + 1} ({note_name}) - PROPIEDADES", state="disabled")
        menu.add_separator()

        # Dinamismo submenu
        dyn_menu = tk.Menu(menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        cur_dyn = self.ball_custom_dynamics.get(ball_idx)
        for k_dyn, d_info in DYNAMIC_MODES.items():
            mark = "✓ " if cur_dyn == k_dyn else "   "
            dyn_menu.add_command(
                label=f"{mark}{d_info['name']}",
                command=lambda d=k_dyn: self._set_ball_dynamic(ball_idx, d)
            )
        dyn_summary = 'Global' if cur_dyn is None else DYNAMIC_MODES.get(cur_dyn, {}).get('short', cur_dyn)
        menu.add_cascade(label=f"⚡ Dinamismo Propio: [{dyn_summary}]", menu=dyn_menu)

        # Duración submenu
        dur_menu = tk.Menu(menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        cur_dur = self.ball_custom_durations.get(ball_idx)
        for k_dur, dur_info in NOTE_DURATIONS.items():
            mark = "✓ " if cur_dur == k_dur else "   "
            dur_menu.add_command(
                label=f"{mark}{dur_info['name']}",
                command=lambda d=k_dur: self._set_ball_duration(ball_idx, d)
            )
        dur_summary = 'Global' if cur_dur is None else NOTE_DURATIONS.get(cur_dur, {}).get('name', cur_dur)
        menu.add_cascade(label=f"⏱ Duración Propia: [{dur_summary}]", menu=dur_menu)

        # Golpes Ida/Vuelta submenu (hasta 6 como la guitarra)
        strike_menu = tk.Menu(menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        cur_strike = self.ball_custom_strikes.get(ball_idx)
        cur_left = cur_strike[0] if cur_strike is not None else None
        cur_right = cur_strike[1] if cur_strike is not None else None

        mark_glob = "✓ " if cur_strike is None else "   "
        strike_menu.add_command(
            label=f"{mark_glob}(Global - Seguir General)",
            command=lambda: self._set_ball_strikes(ball_idx, None)
        )
        strike_menu.add_separator()

        # Guitar Presets
        guitar_menu = tk.Menu(strike_menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        guitar_presets = [
            ("🎸 6 Izq + 6 Der (Guitarra Completa 6 Cuerdas)", (6, 6)),
            ("🎸 6 Izq + 1 Der (Guitarra 6 Izq + 1 Der)", (6, 1)),
            ("🎸 1 Izq + 6 Der (1 Izq + Guitarra 6 Der)", (1, 6)),
            ("🎸 6 Izq + 0 Der (Guitarra 6 Solo Izquierda)", (6, 0)),
            ("🎸 0 Izq + 6 Der (Guitarra 6 Solo Derecha)", (0, 6)),
        ]
        for g_name, g_val in guitar_presets:
            mark = "✓ " if cur_strike == g_val else "   "
            guitar_menu.add_command(
                label=f"{mark}{g_name}",
                command=lambda val=g_val: self._set_ball_strikes(ball_idx, val)
            )
        strike_menu.add_cascade(label="🎸 Presets Guitarra (6 Cuerdas)", menu=guitar_menu)

        # Standard Presets
        std_menu = tk.Menu(strike_menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        std_presets = [
            ("1 Izq + 1 Der (Estándar)", (1, 1)),
            ("1 Izq + 2 Der (Rebote Retorno)", (1, 2)),
            ("2 Izq + 1 Der (Impulso Entrada)", (2, 1)),
            ("2 Izq + 2 Der (Doble Continuo)", (2, 2)),
            ("1 Izq + 3 Der (Tresillo Retorno)", (1, 3)),
            ("3 Izq + 1 Der (Tresillo Entrada)", (3, 1)),
            ("3 Izq + 3 Der (Sextillo Bilateral)", (3, 3)),
            ("1 Izq + 4 Der (Cuatrillo Retorno)", (1, 4)),
            ("4 Izq + 1 Der (Cuatrillo Entrada)", (4, 1)),
            ("4 Izq + 4 Der (Cuatrillo Doble)", (4, 4)),
            ("1 Izq + 5 Der (Quintillo Retorno)", (1, 5)),
            ("5 Izq + 1 Der (Quintillo Entrada)", (5, 1)),
            ("5 Izq + 5 Der (Quintillo Doble)", (5, 5)),
            ("1 Izq + 0 Der (Solo Izquierda)", (1, 0)),
            ("0 Izq + 1 Der (Solo Derecha)", (0, 1)),
            ("2 Izq + 0 Der (Doble Solo Izq)", (2, 0)),
            ("0 Izq + 2 Der (Doble Solo Der)", (0, 2)),
            ("3 Izq + 0 Der (Tresillo Solo Izq)", (3, 0)),
            ("0 Izq + 3 Der (Tresillo Solo Der)", (0, 3)),
            ("4 Izq + 0 Der (Cuatrillo Solo Izq)", (4, 0)),
            ("0 Izq + 4 Der (Cuatrillo Solo Der)", (0, 4)),
            ("5 Izq + 0 Der (Quintillo Solo Izq)", (5, 0)),
            ("0 Izq + 5 Der (Quintillo Solo Der)", (0, 5)),
        ]
        for s_name, s_val in std_presets:
            mark = "✓ " if cur_strike == s_val else "   "
            std_menu.add_command(
                label=f"{mark}{s_name}",
                command=lambda val=s_val: self._set_ball_strikes(ball_idx, val)
            )
        strike_menu.add_cascade(label="🎼 Presets Estándar y Múltiples (1 a 5)", menu=std_menu)

        strike_menu.add_separator()

        # Direct independent Left & Right strikes submenus (0 to 6)
        left_sub = tk.Menu(strike_menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        for count in range(7):
            mark = "✓ " if (cur_left == count) else "   "
            tag = " (Silencio)" if count == 0 else (" (🎸 Guitarra 6 Cuerdas)" if count == 6 else "")
            left_sub.add_command(
                label=f"{mark}{count} Golpes a la Izquierda{tag}",
                command=lambda c=count: self._set_ball_left_strikes(ball_idx, c)
            )
        strike_menu.add_cascade(label="◄ Fijar Golpes Izquierda (0 a 6)", menu=left_sub)

        right_sub = tk.Menu(strike_menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        for count in range(7):
            mark = "✓ " if (cur_right == count) else "   "
            tag = " (Silencio)" if count == 0 else (" (🎸 Guitarra 6 Cuerdas)" if count == 6 else "")
            right_sub.add_command(
                label=f"{mark}{count} Golpes a la Derecha{tag}",
                command=lambda c=count: self._set_ball_right_strikes(ball_idx, c)
            )
        strike_menu.add_cascade(label="► Fijar Golpes Derecha (0 a 6)", menu=right_sub)

        if cur_strike is None:
            strike_summary = 'Global'
        else:
            left_disp = format_pattern(cur_strike[0]) if isinstance(cur_strike[0], (list, tuple)) else cur_strike[0]
            right_disp = format_pattern(cur_strike[1]) if isinstance(cur_strike[1], (list, tuple)) else cur_strike[1]
            strike_summary = f"{left_disp} Izq + {right_disp} Der"
        menu.add_cascade(label=f"🎯 Golpes Izq/Der (hasta 6): [{strike_summary}]", menu=strike_menu)

        # Paleta Armónica Propia submenu
        pal_menu = tk.Menu(menu, tearoff=0, bg="#1e2230", fg="#cad3f5", activebackground="#38bdf8", activeforeground="#0f1117")
        cur_pal = self.ball_custom_palettes.get(ball_idx)
        mark_glob_pal = "✓ " if cur_pal is None else "   "
        pal_menu.add_command(
            label=f"{mark_glob_pal}(Global - Seguir General)",
            command=lambda: self._set_ball_palette(ball_idx, None)
        )
        pal_menu.add_separator()
        for pk, p_info in HARMONIC_FILL_PALETTES.items():
            mark = "✓ " if cur_pal == pk else "   "
            pal_menu.add_command(
                label=f"{mark}{p_info['name']} - {p_info['desc']}",
                command=lambda k=pk: self._set_ball_palette(ball_idx, k)
            )
        pal_summary = 'Global' if cur_pal is None else HARMONIC_FILL_PALETTES.get(cur_pal, {}).get('name', cur_pal)
        menu.add_cascade(label=f"🎨 Relleno Armónico Propio: [{pal_summary}]", menu=pal_menu)

        menu.add_separator()
        menu.add_command(
            label="⏮ Reiniciar Recorrido de Escala (a Nota 1)",
            command=lambda: self._reset_ball_strike_counter(ball_idx)
        )
        menu.add_command(
            label="🔄 Restablecer a Global (Seguir controles generales)",
            command=lambda: self._reset_ball_properties(ball_idx)
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _set_ball_left_strikes(self, ball_idx: int, left_count: int):
        _, cur_r = self._get_ball_steps(ball_idx)
        self._set_ball_strikes(ball_idx, (int(left_count), cur_r))

    def _set_ball_right_strikes(self, ball_idx: int, right_count: int):
        cur_l, _ = self._get_ball_steps(ball_idx)
        self._set_ball_strikes(ball_idx, (cur_l, int(right_count)))

    def _set_ball_dynamic(self, ball_idx: int, dyn_mode: str):
        self.ball_custom_dynamics[ball_idx] = dyn_mode
        if hasattr(self, 'system'):
            self.system.custom_ball_dynamics[ball_idx] = dyn_mode
        self._update_keyboard_labels()
        self._sync_side_panel_controls()

    def _set_ball_duration(self, ball_idx: int, dur_mode: str):
        self.ball_custom_durations[ball_idx] = dur_mode
        if hasattr(self, 'system'):
            self.system.custom_ball_durations[ball_idx] = dur_mode
        self._update_keyboard_labels()
        self._sync_side_panel_controls()

    def _set_ball_strikes(self, ball_idx: int, strikes_tuple):
        if strikes_tuple is None:
            self.ball_custom_strikes.pop(ball_idx, None)
            if hasattr(self, 'system'):
                self.system.custom_ball_strikes.pop(ball_idx, None)
        else:
            l_steps = resolve_strike_steps(strikes_tuple[0])
            r_steps = resolve_strike_steps(strikes_tuple[1])
            self.ball_custom_strikes[ball_idx] = (l_steps, r_steps)
            if hasattr(self, 'system'):
                self.system.custom_ball_strikes[ball_idx] = (l_steps, r_steps)
        self._update_keyboard_labels()
        self._update_matrix_buttons()

    def _reset_ball_properties(self, ball_idx: int):
        self.ball_custom_dynamics.pop(ball_idx, None)
        self.ball_custom_durations.pop(ball_idx, None)
        self.ball_custom_strikes.pop(ball_idx, None)
        self.ball_custom_palettes.pop(ball_idx, None)
        self.ball_custom_strum_ratio.pop(ball_idx, None)
        self.ball_custom_strum_sens.pop(ball_idx, None)
        self.ball_custom_drum_voices.pop(ball_idx, None)
        get_sample_engine().set_pendulum_drum_voice(ball_idx, None, self.timbre_var.get())
        self.ball_strike_counts[ball_idx] = 0
        self.ball_cross_count.pop(ball_idx, None)
        if hasattr(self, 'system'):
            self.system.custom_ball_dynamics.pop(ball_idx, None)
            self.system.custom_ball_durations.pop(ball_idx, None)
            self.system.custom_ball_strikes.pop(ball_idx, None)
            self.system.custom_ball_palettes.pop(ball_idx, None)
            self.system.custom_ball_strum_ratio.pop(ball_idx, None)
            self.system.custom_ball_strum_sens.pop(ball_idx, None)
        self._update_keyboard_labels()
        self._sync_side_panel_controls()
        self._update_matrix_buttons()

    def _build_permanent_side_panel(self):
        # Top Header & Ball Selector
        prop_header = tk.Frame(self.side_panel, bg="#131622")
        prop_header.pack(fill=tk.X, pady=(0, 4))

        self.lbl_side_ball_header = tk.Label(
            prop_header,
            text="⚙ BOLA:",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#131622"
        )
        self.lbl_side_ball_header.pack(side=tk.LEFT)

        self.ball_selector_combo = ttk.Combobox(prop_header, state="readonly", width=14)
        self.ball_selector_combo.pack(side=tk.LEFT, padx=(4, 4))
        self.ball_selector_combo.bind("<<ComboboxSelected>>", self._on_selected_ball_changed)

        self.btn_side_mute = tk.Button(
            prop_header,
            text="🔊 Activo",
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b",
            fg="#38bdf8",
            relief=tk.FLAT,
            padx=5,
            pady=0,
            cursor="hand2",
            command=self._toggle_active_ball_silence
        )
        self.btn_side_mute.pack(side=tk.RIGHT)

        # Active Ball Properties Controls (Permanently Open)
        prop_grid = tk.Frame(self.side_panel, bg="#161a27", padx=6, pady=4, bd=1, relief=tk.RIDGE)
        prop_grid.pack(fill=tk.X, pady=(0, 4))

        # Dinámica
        r1 = tk.Frame(prop_grid, bg="#161a27")
        r1.pack(fill=tk.X, pady=1)
        tk.Label(r1, text="Dinámica:", font=("Segoe UI", 8, "bold"), fg="#cad3f5", bg="#161a27", width=9, anchor="w").pack(side=tk.LEFT)
        dyn_vals = ["(Global - Seguir General)"] + [DYNAMIC_MODES[k]['name'] for k in DYNAMIC_MODES]
        self.side_dyn_combo = ttk.Combobox(r1, values=dyn_vals, state="readonly", width=25)
        self.side_dyn_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.side_dyn_combo.bind("<<ComboboxSelected>>", self._on_side_dyn_selected)

        # Duración
        r2 = tk.Frame(prop_grid, bg="#161a27")
        r2.pack(fill=tk.X, pady=1)
        tk.Label(r2, text="Duración:", font=("Segoe UI", 8, "bold"), fg="#cad3f5", bg="#161a27", width=9, anchor="w").pack(side=tk.LEFT)
        dur_vals = ["(Global - Seguir General)"] + [NOTE_DURATIONS[k]['name'] for k in NOTE_DURATIONS]
        self.side_dur_combo = ttk.Combobox(r2, values=dur_vals, state="readonly", width=25)
        self.side_dur_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.side_dur_combo.bind("<<ComboboxSelected>>", self._on_side_dur_selected)

        # Paleta Armónica
        r3 = tk.Frame(prop_grid, bg="#161a27")
        r3.pack(fill=tk.X, pady=1)
        tk.Label(r3, text="Armonía:", font=("Segoe UI", 8, "bold"), fg="#cad3f5", bg="#161a27", width=9, anchor="w").pack(side=tk.LEFT)
        pal_vals = ["(Global - Seguir General)"] + [p['name'] for p in HARMONIC_FILL_PALETTES.values()]
        tk.Button(
            r3,
            text="⏮",
            font=("Segoe UI", 8, "bold"),
            bg="#232a3b",
            fg="#38bdf8",
            width=2,
            relief=tk.FLAT,
            padx=2,
            pady=0,
            cursor="hand2",
            command=lambda: self._reset_ball_strike_counter(self.selected_ball_idx)
        ).pack(side=tk.RIGHT, padx=(3, 0))
        self.side_pal_combo = ttk.Combobox(r3, values=pal_vals, state="readonly", width=22)
        self.side_pal_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.side_pal_combo.bind("<<ComboboxSelected>>", self._on_side_pal_selected)

        # Presets Rápidos (patrones con longitud variable 1..8 y silencios reales)
        r4 = tk.Frame(prop_grid, bg="#161a27")
        r4.pack(fill=tk.X, pady=(3, 1))
        tk.Label(r4, text="Presets:", font=("Segoe UI", 7, "bold"), fg="#94a3b8", bg="#161a27").pack(side=tk.LEFT, padx=(0, 2))
        preset_quick = [
            ("6+6", ("xxxxxx", "xxxxxx")),
            ("1+1", ("x-----", "x-----")),
            ("7:xx-xx--", ("xx-xx--", "x------")),
            ("7:x-x-x-x", ("x-x-x-x", "x-x-xxx")),
            ("Sín", ("-x-x--", "-x--x-")),
            ("Global", None),
        ]
        for p_txt, p_val in preset_quick:
            tk.Button(
                r4,
                text=p_txt,
                font=("Segoe UI", 7, "bold"),
                bg="#232a3b",
                fg="#38bdf8" if p_txt.startswith("7:") else "#cad3f5",
                relief=tk.FLAT,
                padx=3,
                pady=0,
                cursor="hand2",
                command=lambda val=p_val: self._apply_side_preset(val)
            ).pack(side=tk.LEFT, padx=1)

        # Longitud de pasos por lado para la bola seleccionada (1..8)
        r4b = tk.Frame(prop_grid, bg="#161a27")
        r4b.pack(fill=tk.X, pady=(1, 2))
        tk.Label(r4b, text="Pasos:", font=("Segoe UI", 7, "bold"), fg="#94a3b8", bg="#161a27", width=9, anchor="w").pack(side=tk.LEFT)
        tk.Label(r4b, text="◄Ida", font=("Segoe UI", 7, "bold"), fg="#00f5d4", bg="#161a27").pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(
            r4b, text="-", font=("Consolas", 7, "bold"), bg="#1e293b", fg="#cbd5e1",
            width=2, relief=tk.FLAT, padx=0, pady=0, cursor="hand2",
            command=lambda: self._step_target_side_length("left", -1)
        ).pack(side=tk.LEFT)
        self.lbl_side_len_left = tk.Label(r4b, text="6", font=("Consolas", 8, "bold"), fg="#00f5d4", bg="#161a27", width=2)
        self.lbl_side_len_left.pack(side=tk.LEFT)
        tk.Button(
            r4b, text="+", font=("Consolas", 7, "bold"), bg="#1e293b", fg="#cbd5e1",
            width=2, relief=tk.FLAT, padx=0, pady=0, cursor="hand2",
            command=lambda: self._step_target_side_length("left", +1)
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(r4b, text="│ ►Vta", font=("Segoe UI", 7, "bold"), fg="#f72585", bg="#161a27").pack(side=tk.LEFT, padx=(0, 2))
        tk.Button(
            r4b, text="-", font=("Consolas", 7, "bold"), bg="#1e293b", fg="#cbd5e1",
            width=2, relief=tk.FLAT, padx=0, pady=0, cursor="hand2",
            command=lambda: self._step_target_side_length("right", -1)
        ).pack(side=tk.LEFT)
        self.lbl_side_len_right = tk.Label(r4b, text="6", font=("Consolas", 8, "bold"), fg="#f72585", bg="#161a27", width=2)
        self.lbl_side_len_right.pack(side=tk.LEFT)
        tk.Button(
            r4b, text="+", font=("Consolas", 7, "bold"), bg="#1e293b", fg="#cbd5e1",
            width=2, relief=tk.FLAT, padx=0, pady=0, cursor="hand2",
            command=lambda: self._step_target_side_length("right", +1)
        ).pack(side=tk.LEFT)
        tk.Button(
            r4b, text="8:Esc~", font=("Segoe UI", 7, "bold"), bg="#422006", fg="#fde047",
            relief=tk.FLAT, padx=4, pady=0, cursor="hand2",
            command=lambda: self._apply_side_preset(("xxxxxxxx", "~~xxxxxx"))
        ).pack(side=tk.RIGHT, padx=(4, 0))

        # Razón de progresión del rasgueo propio
        r5 = tk.Frame(prop_grid, bg="#161a27")
        r5.pack(fill=tk.X, pady=1)
        tk.Label(r5, text="Rasgueo:", font=("Segoe UI", 8, "bold"), fg="#fb923c", bg="#161a27", width=9, anchor="w").pack(side=tk.LEFT)
        ratio_vals = ["(Global - Seguir General)"] + [v['name'] for v in STRUM_PROGRESSIONS.values()]
        self.side_strum_ratio_combo = ttk.Combobox(r5, values=ratio_vals, state="readonly", width=25)
        self.side_strum_ratio_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.side_strum_ratio_combo.bind("<<ComboboxSelected>>", self._on_side_strum_ratio_selected)

        # Sensibilidad de acento propia
        r6 = tk.Frame(prop_grid, bg="#161a27")
        r6.pack(fill=tk.X, pady=1)
        tk.Label(r6, text="Acento:", font=("Segoe UI", 8, "bold"), fg="#f472b6", bg="#161a27", width=9, anchor="w").pack(side=tk.LEFT)
        sens_vals = ["(Global - Seguir General)"] + [v['name'] for v in STRUM_ACCENT_SENSITIVITIES.values()]
        self.side_strum_sens_combo = ttk.Combobox(r6, values=sens_vals, state="readonly", width=25)
        self.side_strum_sens_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.side_strum_sens_combo.bind("<<ComboboxSelected>>", self._on_side_strum_sens_selected)

        # Voz de Percusión / Batería (para instrumentos drums/perc)
        r_drum = tk.Frame(prop_grid, bg="#161a27")
        r_drum.pack(fill=tk.X, pady=1)
        tk.Label(r_drum, text="Voz Drum:", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#161a27", width=9, anchor="w").pack(side=tk.LEFT)
        self.side_drum_combo = ttk.Combobox(r_drum, values=["(Auto / Seguir Kit)"], state="readonly", width=25)
        self.side_drum_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.side_drum_combo.bind("<<ComboboxSelected>>", self._on_side_drum_selected)

        # Section 3: Drum Machine Matrix Header
        mat_header = tk.Frame(self.side_panel, bg="#131622")
        mat_header.pack(fill=tk.X, pady=(4, 2))
        tk.Label(
            mat_header,
            text="🥁 MATRIZ RÍTMICA (1–8 PASOS)",
            font=("Segoe UI", 9, "bold"),
            fg="#00f5d4",
            bg="#131622"
        ).pack(side=tk.LEFT)

        tk.Label(
            mat_header,
            text="Izq: -/x/~ • Der: long.",
            font=("Segoe UI", 7, "italic"),
            fg="#64748b",
            bg="#131622"
        ).pack(side=tk.RIGHT)

        # Column Headers
        cols_bar = tk.Frame(self.side_panel, bg="#1a1e2d", padx=2, pady=2)
        cols_bar.pack(fill=tk.X, pady=(0, 2))
        tk.Label(cols_bar, text="VOZ", font=("Segoe UI", 7, "bold"), fg="#94a3b8", bg="#1a1e2d", width=5, anchor="w").pack(side=tk.LEFT)
        tk.Label(cols_bar, text="◄ IDA (1..8)", font=("Segoe UI", 7, "bold"), fg="#00f5d4", bg="#1a1e2d", width=18, anchor="center").pack(side=tk.LEFT, padx=(1, 1))
        tk.Label(cols_bar, text="► VUELTA (1..8)", font=("Segoe UI", 7, "bold"), fg="#f72585", bg="#1a1e2d", width=18, anchor="center").pack(side=tk.LEFT, padx=(1, 1))
        tk.Label(cols_bar, text="◄ ► M", font=("Segoe UI", 7, "bold"), fg="#94a3b8", bg="#1a1e2d", width=8, anchor="center").pack(side=tk.LEFT)

        # Matrix rows container
        self.matrix_rows_frame = tk.Frame(self.side_panel, bg="#131622")
        self.matrix_rows_frame.pack(fill=tk.BOTH, expand=True)

    def _build_drum_matrix_rows(self):
        for widget in self.matrix_rows_frame.winfo_children():
            widget.destroy()

        self.matrix_step_buttons.clear()
        self.matrix_vox_buttons.clear()
        self.matrix_mute_buttons.clear()
        self.matrix_len_buttons.clear()

        n = len(self.system.pendulums)
        for i in range(n):
            p = self.system.pendulums[i]
            note = midi_to_note_name(p.base_pitch)
            is_selected = (i == self.selected_ball_idx)

            row_f = tk.Frame(self.matrix_rows_frame, bg="#131622", pady=1)
            row_f.pack(fill=tk.X)

            # Voice Selector Button
            vox_bg = "#22314e" if is_selected else "#181d2a"
            vox_fg = "#ffffff" if is_selected else p.color
            vox_bd = 1 if is_selected else 0
            btn_vox = tk.Button(
                row_f,
                text=f"[{i+1}]{note}",
                font=("Consolas", 7, "bold"),
                bg=vox_bg,
                fg=vox_fg,
                width=5,
                relief=tk.SOLID if is_selected else tk.FLAT,
                bd=vox_bd,
                padx=0,
                pady=1,
                cursor="hand2",
                command=lambda idx=i: self._select_ball(idx, exit_all_mode=True)
            )
            btn_vox.bind("<Button-3>", lambda e, idx=i: self._cycle_ball_drum_voice(idx))
            btn_vox.pack(side=tk.LEFT, padx=(0, 2))
            self.matrix_vox_buttons[i] = btn_vox

            # Left Steps (1 to 8)
            f_left = tk.Frame(row_f, bg="#131622")
            f_left.pack(side=tk.LEFT, padx=(0, 1))
            for s in range(MAX_PATTERN_STEPS):
                btn_st = tk.Button(
                    f_left,
                    text="x",
                    font=("Consolas", 7, "bold"),
                    bg="#1a2030",
                    fg="#64748b",
                    width=1,
                    relief=tk.FLAT,
                    bd=0,
                    padx=1,
                    pady=1,
                    cursor="hand2",
                    command=lambda idx=i, st=s: self._toggle_matrix_step(idx, 'left', st)
                )
                btn_st.bind("<Button-2>", lambda e, idx=i, st=s: self._toggle_matrix_step_tie(idx, 'left', st))
                btn_st.bind("<Button-3>", lambda e, idx=i, st=s: self._set_ball_side_length(idx, 'left', st + 1))
                btn_st.pack(side=tk.LEFT, padx=0)
                self.matrix_step_buttons[(i, 'left', s)] = btn_st

            # Divider
            tk.Label(row_f, text="│", font=("Segoe UI", 8), fg="#252c3f", bg="#131622").pack(side=tk.LEFT, padx=1)

            # Right Steps (1 to 8)
            f_right = tk.Frame(row_f, bg="#131622")
            f_right.pack(side=tk.LEFT, padx=(0, 1))
            for s in range(MAX_PATTERN_STEPS):
                btn_st = tk.Button(
                    f_right,
                    text="x",
                    font=("Consolas", 7, "bold"),
                    bg="#1a2030",
                    fg="#64748b",
                    width=1,
                    relief=tk.FLAT,
                    bd=0,
                    padx=1,
                    pady=1,
                    cursor="hand2",
                    command=lambda idx=i, st=s: self._toggle_matrix_step(idx, 'right', st)
                )
                btn_st.bind("<Button-2>", lambda e, idx=i, st=s: self._toggle_matrix_step_tie(idx, 'right', st))
                btn_st.bind("<Button-3>", lambda e, idx=i, st=s: self._set_ball_side_length(idx, 'right', st + 1))
                btn_st.pack(side=tk.LEFT, padx=0)
                self.matrix_step_buttons[(i, 'right', s)] = btn_st

            # Per-Side Step Length Cycle + Mute (◄N / ►N / M)
            f_acc = tk.Frame(row_f, bg="#131622")
            f_acc.pack(side=tk.LEFT, padx=(2, 0))

            btn_ll = tk.Button(
                f_acc,
                text="◄6",
                font=("Consolas", 7, "bold"),
                bg="#1e2433",
                fg="#94a3b8",
                width=2,
                relief=tk.FLAT,
                bd=0,
                padx=0,
                pady=1,
                cursor="hand2",
                command=lambda idx=i: self._cycle_ball_side_length(idx, "left", +1)
            )
            btn_ll.bind("<Button-3>", lambda e, idx=i: self._cycle_ball_side_length(idx, "left", -1))
            btn_ll.pack(side=tk.LEFT, padx=1)
            self.matrix_len_buttons[(i, "left")] = btn_ll

            btn_rl = tk.Button(
                f_acc,
                text="►6",
                font=("Consolas", 7, "bold"),
                bg="#1e2433",
                fg="#94a3b8",
                width=2,
                relief=tk.FLAT,
                bd=0,
                padx=0,
                pady=1,
                cursor="hand2",
                command=lambda idx=i: self._cycle_ball_side_length(idx, "right", +1)
            )
            btn_rl.bind("<Button-3>", lambda e, idx=i: self._cycle_ball_side_length(idx, "right", -1))
            btn_rl.pack(side=tk.LEFT, padx=1)
            self.matrix_len_buttons[(i, "right")] = btn_rl

            btn_m = tk.Button(
                f_acc,
                text="M",
                font=("Segoe UI", 6, "bold"),
                bg="#232736",
                fg="#f87171",
                width=2,
                relief=tk.FLAT,
                bd=0,
                padx=0,
                pady=1,
                cursor="hand2",
                command=lambda idx=i: self._toggle_ball_silence(idx)
            )
            btn_m.pack(side=tk.LEFT, padx=1)
            self.matrix_mute_buttons[i] = btn_m

        self._update_matrix_buttons()

    def _select_ball(self, ball_idx: int, exit_all_mode: bool = False):
        n = len(self.system.pendulums)
        if 0 <= ball_idx < n:
            self.selected_ball_idx = ball_idx
            exited_all = False
            if exit_all_mode and self._is_pattern_all_mode():
                self.strum_target_mode = "single"
                cur_l, cur_r = self._get_ball_steps(ball_idx)
                note = midi_to_note_name(self.system.pendulums[ball_idx].base_pitch)
                self.mode_banner_text = (
                    f"🎯 Bola {ball_idx + 1} ({note}): ◄ [{format_pattern(cur_l)}] │ ► [{format_pattern(cur_r)}]"
                )
                exited_all = True
            if hasattr(self, 'ball_selector_combo'):
                self.ball_selector_combo.current(ball_idx)
            self._sync_side_panel_controls()
            self._update_matrix_buttons()
            if exited_all:
                self._update_keyboard_labels()
                self._update_hud_info()

    def _cycle_selected_ball(self, delta: int):
        n = len(self.system.pendulums) if hasattr(self, 'system') else 12
        if n <= 0:
            return
        new_idx = (self.selected_ball_idx + delta) % n
        self._select_ball(new_idx, exit_all_mode=True)
        p = self.system.pendulums[new_idx]
        cur_l, cur_r = self._get_ball_steps(new_idx)
        nl = sum(cur_l)
        nr = sum(cur_r)
        self.mode_banner_text = f"🎯 Péndulo Seleccionado: Bola {new_idx + 1} ({midi_to_note_name(p.base_pitch)}) [{nl}+{nr}]"
        self._update_matrix_buttons()
        self._update_keyboard_labels()
        self._update_hud_info()

    def _audition_ball_pattern(self, ball_idx: int):
        """Silenced to ensure clean key navigation without cut-off rasgueos."""
        pass

    def _sync_side_panel_controls(self):
        if not hasattr(self, 'ball_selector_combo') or not hasattr(self, 'system'):
            return
        n = len(self.system.pendulums)
        if n == 0:
            return
        self.selected_ball_idx = max(0, min(n - 1, self.selected_ball_idx))

        ball_names = [f"Bola {i + 1} ({midi_to_note_name(p.base_pitch)})" for i, p in enumerate(self.system.pendulums)]
        self.ball_selector_combo.config(values=ball_names)
        self.ball_selector_combo.current(self.selected_ball_idx)

        idx = self.selected_ball_idx
        is_all_pat = self._is_pattern_all_mode()
        if hasattr(self, 'lbl_side_ball_header'):
            if is_all_pat:
                self.lbl_side_ball_header.config(text="🌐 TODAS:", fg="#facc15")
            else:
                self.lbl_side_ball_header.config(text="⚙ BOLA:", fg="#38bdf8")

        # Dinámica
        cur_dyn = self.ball_custom_dynamics.get(idx)
        dyn_keys = list(DYNAMIC_MODES.keys())
        if cur_dyn in dyn_keys:
            self.side_dyn_combo.current(dyn_keys.index(cur_dyn) + 1)
        else:
            self.side_dyn_combo.current(0)

        # Duración
        cur_dur = self.ball_custom_durations.get(idx)
        dur_keys = list(NOTE_DURATIONS.keys())
        if cur_dur in dur_keys:
            self.side_dur_combo.current(dur_keys.index(cur_dur) + 1)
        else:
            self.side_dur_combo.current(0)

        # Paleta
        cur_pal = self.ball_custom_palettes.get(idx)
        pal_keys = list(HARMONIC_FILL_PALETTES.keys())
        if cur_pal in pal_keys:
            self.side_pal_combo.current(pal_keys.index(cur_pal) + 1)
        else:
            self.side_pal_combo.current(0)

        # Rasgueo Ratio propio
        if hasattr(self, 'side_strum_ratio_combo'):
            cur_ratio = self.ball_custom_strum_ratio.get(idx)
            ratio_keys = list(STRUM_PROGRESSIONS.keys())
            matched_idx = 0
            if cur_ratio is not None:
                for k_i, k_p in enumerate(ratio_keys):
                    if abs(STRUM_PROGRESSIONS[k_p]['ratio'] - cur_ratio) < 0.01:
                        matched_idx = k_i + 1
                        break
            self.side_strum_ratio_combo.current(matched_idx)

        # Sensibilidad de Acento propia
        if hasattr(self, 'side_strum_sens_combo'):
            cur_sens = self.ball_custom_strum_sens.get(idx)
            sens_keys = list(STRUM_ACCENT_SENSITIVITIES.keys())
            matched_s = 0
            if cur_sens is not None:
                for s_i, s_k in enumerate(sens_keys):
                    if abs(STRUM_ACCENT_SENSITIVITIES[s_k]['value'] - cur_sens) < 0.01:
                        matched_s = s_i + 1
                        break
            self.side_strum_sens_combo.current(matched_s)

        # Mute button & step lengths
        is_muted = (self.anim_time < self.pendulum_mutes.get(idx, 0.0))
        if hasattr(self, 'btn_side_mute'):
            self.btn_side_mute.config(
                text="🔇 Silenciado" if is_muted else "🔊 Activo",
                bg="#7f1d1d" if is_muted else "#1e293b",
                fg="#fca5a5" if is_muted else "#38bdf8"
            )
        if hasattr(self, 'lbl_side_len_left') and hasattr(self, 'lbl_side_len_right'):
            if is_all_pat:
                left_lens = {len(self._get_ball_steps(bi)[0]) for bi in range(n)}
                right_lens = {len(self._get_ball_steps(bi)[1]) for bi in range(n)}
                l_txt = str(next(iter(left_lens))) if len(left_lens) == 1 else "*"
                r_txt = str(next(iter(right_lens))) if len(right_lens) == 1 else "*"
                self.lbl_side_len_left.config(text=l_txt)
                self.lbl_side_len_right.config(text=r_txt)
            else:
                cl, cr = self._get_ball_steps(idx)
                self.lbl_side_len_left.config(text=str(len(cl)))
                self.lbl_side_len_right.config(text=str(len(cr)))

        # Voz de Percusión / Batería
        if hasattr(self, 'side_drum_combo'):
            inst = self.timbre_var.get()
            sample_eng = get_sample_engine()
            bank = sample_eng.get_bank(inst)
            if bank and (bank.is_drums or bank.is_mix):
                avail_voices = sample_eng.get_available_drum_voices(inst)
                self._side_drum_keys = avail_voices
                drum_display_vals = ["(Auto / Seguir Kit)"] + [
                    (f"🎶 {k[8:].replace('_', ' ').capitalize()} (Nota)" if k.startswith("melodic:") else DRUM_VOICE_LABELS.get(k, f"🥁 {k.capitalize()}"))
                    for k in avail_voices
                ]
                self.side_drum_combo.config(values=drum_display_vals, state="readonly")
                cur_v = self.ball_custom_drum_voices.get(idx)
                if cur_v and cur_v in avail_voices:
                    self.side_drum_combo.current(avail_voices.index(cur_v) + 1)
                else:
                    self.side_drum_combo.current(0)
            else:
                self.side_drum_combo.config(values=["(Solo en modo Batería/Perc)"], state="disabled")

    def _on_side_dyn_selected(self, event=None):
        idx = self.selected_ball_idx
        d_idx = self.side_dyn_combo.current()
        dyn_keys = list(DYNAMIC_MODES.keys())
        if d_idx > 0:
            self._set_ball_dynamic(idx, dyn_keys[d_idx - 1])
        else:
            self.ball_custom_dynamics.pop(idx, None)
            if hasattr(self, 'system'):
                self.system.custom_ball_dynamics.pop(idx, None)
        self._update_keyboard_labels()
        self._sync_side_panel_controls()

    def _on_side_dur_selected(self, event=None):
        idx = self.selected_ball_idx
        t_idx = self.side_dur_combo.current()
        dur_keys = list(NOTE_DURATIONS.keys())
        if t_idx > 0:
            self._set_ball_duration(idx, dur_keys[t_idx - 1])
        else:
            self.ball_custom_durations.pop(idx, None)
            if hasattr(self, 'system'):
                self.system.custom_ball_durations.pop(idx, None)
        self._update_keyboard_labels()
        self._sync_side_panel_controls()

    def _on_side_pal_selected(self, event=None):
        idx = self.selected_ball_idx
        p_idx = self.side_pal_combo.current()
        pal_keys = list(HARMONIC_FILL_PALETTES.keys())
        if p_idx > 0:
            self._set_ball_palette(idx, pal_keys[p_idx - 1])
        else:
            self.ball_custom_palettes.pop(idx, None)
            if hasattr(self, 'system'):
                self.system.custom_ball_palettes.pop(idx, None)
        self._update_keyboard_labels()
        self._sync_side_panel_controls()

    def _on_side_strum_ratio_selected(self, event=None):
        idx = self.selected_ball_idx
        r_idx = self.side_strum_ratio_combo.current()
        ratio_keys = list(STRUM_PROGRESSIONS.keys())
        if r_idx > 0:
            val = STRUM_PROGRESSIONS[ratio_keys[r_idx - 1]]['ratio']
            self.ball_custom_strum_ratio[idx] = val
            if hasattr(self, 'system'):
                self.system.custom_ball_strum_ratio[idx] = val
        else:
            self.ball_custom_strum_ratio.pop(idx, None)
            if hasattr(self, 'system'):
                self.system.custom_ball_strum_ratio.pop(idx, None)
        self._sync_side_panel_controls()

    def _on_side_strum_sens_selected(self, event=None):
        idx = self.selected_ball_idx
        s_idx = self.side_strum_sens_combo.current()
        sens_keys = list(STRUM_ACCENT_SENSITIVITIES.keys())
        if s_idx > 0:
            val = STRUM_ACCENT_SENSITIVITIES[sens_keys[s_idx - 1]]['value']
            self.ball_custom_strum_sens[idx] = val
            if hasattr(self, 'system'):
                self.system.custom_ball_strum_sens[idx] = val
        else:
            self.ball_custom_strum_sens.pop(idx, None)
            if hasattr(self, 'system'):
                self.system.custom_ball_strum_sens.pop(idx, None)
        self._sync_side_panel_controls()

    def _on_side_drum_selected(self, event=None):
        idx = self.selected_ball_idx
        sel_idx = self.side_drum_combo.current()
        inst = self.timbre_var.get()
        sample_eng = get_sample_engine()
        if sel_idx > 0 and hasattr(self, '_side_drum_keys') and sel_idx - 1 < len(self._side_drum_keys):
            voice_key = self._side_drum_keys[sel_idx - 1]
            self.ball_custom_drum_voices[idx] = voice_key
            sample_eng.set_pendulum_drum_voice(idx, voice_key, inst)
        else:
            self.ball_custom_drum_voices.pop(idx, None)
            sample_eng.set_pendulum_drum_voice(idx, None, inst)
        self._update_matrix_buttons()

    def _cycle_ball_drum_voice(self, ball_idx: int):
        inst = self.timbre_var.get()
        sample_eng = get_sample_engine()
        bank = sample_eng.get_bank(inst)
        if not bank or not (bank.is_drums or bank.is_mix):
            return
        avail_voices = sample_eng.get_available_drum_voices(inst)
        if not avail_voices:
            return
        cur_v = sample_eng.get_pendulum_drum_voice(ball_idx, inst)
        if cur_v in avail_voices:
            nxt_idx = (avail_voices.index(cur_v) + 1) % len(avail_voices)
        else:
            nxt_idx = 0
        new_v = avail_voices[nxt_idx]
        self.ball_custom_drum_voices[ball_idx] = new_v
        sample_eng.set_pendulum_drum_voice(ball_idx, new_v, inst)
        self._sync_side_panel_controls()
        self._update_matrix_buttons()

    def _on_global_strum_prog_selected(self, event=None):
        idx = self.strum_prog_combo.current()
        keys = list(STRUM_PROGRESSIONS.keys())
        if 0 <= idx < len(keys):
            self.strum_progression_var.set(keys[idx])
            if hasattr(self, 'system'):
                self.system.strum_progression_ratio = STRUM_PROGRESSIONS[keys[idx]]['ratio']
        self.canvas.focus_set()

    def _on_global_strum_sens_selected(self, event=None):
        idx = self.strum_sens_combo.current()
        keys = list(STRUM_ACCENT_SENSITIVITIES.keys())
        if 0 <= idx < len(keys):
            self.strum_sensitivity_var.set(keys[idx])
            if hasattr(self, 'system'):
                self.system.strum_accent_sensitivity = STRUM_ACCENT_SENSITIVITIES[keys[idx]]['value']
        self.canvas.focus_set()

    def _on_selected_ball_changed(self, event=None):
        new_idx = self.ball_selector_combo.current()
        if 0 <= new_idx < len(self.system.pendulums):
            self._select_ball(new_idx, exit_all_mode=True)

    def _toggle_active_ball_silence(self):
        self._toggle_ball_silence(self.selected_ball_idx)
        self._sync_side_panel_controls()
        self._update_matrix_buttons()

    def _apply_side_preset(self, preset_tuple):
        if self._is_pattern_all_mode():
            targets = self._get_pattern_target_balls()
            if not targets:
                return
            if preset_tuple is None:
                for b in targets:
                    self.ball_custom_strikes.pop(b, None)
                    if hasattr(self, 'system'):
                        self.system.custom_ball_strikes.pop(b, None)
                self.mode_banner_text = f"🌐 Preset Global aplicado a TODAS ({len(targets)} bolas)"
            else:
                l_steps = resolve_strike_steps(preset_tuple[0])
                r_steps = resolve_strike_steps(preset_tuple[1])
                for b in targets:
                    self.ball_custom_strikes[b] = (list(l_steps), list(r_steps))
                    if hasattr(self, 'system'):
                        self.system.custom_ball_strikes[b] = (list(l_steps), list(r_steps))
                    if is_scale_run_palette(self._get_effective_ball_palette(b)):
                        self._arm_scale_run_on_ida(ball_idx=b, reset_clock_if_paused=True)
                self.mode_banner_text = (
                    f"🌐 Preset [{format_pattern(l_steps)} │ {format_pattern(r_steps)}] en TODAS ({len(targets)} bolas)"
                )
            self._sync_side_panel_controls()
            self._update_matrix_buttons()
            self._update_keyboard_labels()
            self._update_hud_info()
            return
        self._apply_ball_preset(self.selected_ball_idx, preset_tuple)

    def _apply_ball_preset(self, ball_idx: int, preset_tuple):
        if preset_tuple is None:
            self.ball_custom_strikes.pop(ball_idx, None)
            if hasattr(self, 'system'):
                self.system.custom_ball_strikes.pop(ball_idx, None)
        else:
            l_steps = resolve_strike_steps(preset_tuple[0])
            r_steps = resolve_strike_steps(preset_tuple[1])
            self.ball_custom_strikes[ball_idx] = (l_steps, r_steps)
            if hasattr(self, 'system'):
                self.system.custom_ball_strikes[ball_idx] = (l_steps, r_steps)
            if is_scale_run_palette(self._get_effective_ball_palette(ball_idx)):
                self._arm_scale_run_on_ida(ball_idx=ball_idx, reset_clock_if_paused=True)

        self._select_ball(ball_idx)
        self._update_matrix_buttons()
        self._update_keyboard_labels()

    def _get_ball_steps(self, ball_idx: int):
        if ball_idx in self.ball_custom_strikes:
            conf = self.ball_custom_strikes[ball_idx]
            l_spec, r_spec = conf[0], conf[1]
            return resolve_strike_steps(l_spec), resolve_strike_steps(r_spec)
        else:
            pat_data = STRIKE_PATTERNS.get(self.strike_pattern_var.get(), {'ida': 1, 'vuelta': 1, 'izq': 1, 'der': 1})
            l_spec = pat_data.get('izq', pat_data.get('ida', 1))
            r_spec = pat_data.get('der', pat_data.get('vuelta', 1))
            return resolve_strike_steps(l_spec), resolve_strike_steps(r_spec)

    def _toggle_matrix_step(self, ball_idx: int, side: str, step_idx: int):
        cur_left, cur_right = self._get_ball_steps(ball_idx)
        if side == 'left':
            cur_left = cycle_pattern_step(cur_left, step_idx)
        else:
            cur_right = cycle_pattern_step(cur_right, step_idx)

        self.ball_custom_strikes[ball_idx] = (list(cur_left), list(cur_right))
        if hasattr(self, 'system'):
            self.system.custom_ball_strikes[ball_idx] = (list(cur_left), list(cur_right))

        self._select_ball(ball_idx)
        self._update_matrix_buttons()
        self._update_keyboard_labels()

    def _toggle_matrix_step_tie(self, ball_idx: int, side: str, step_idx: int):
        cur_left, cur_right = self._get_ball_steps(ball_idx)
        if side == 'left':
            cur_left = toggle_pattern_tie(cur_left, step_idx)
        else:
            cur_right = toggle_pattern_tie(cur_right, step_idx)

        self.ball_custom_strikes[ball_idx] = (list(cur_left), list(cur_right))
        if hasattr(self, 'system'):
            self.system.custom_ball_strikes[ball_idx] = (list(cur_left), list(cur_right))

        self._select_ball(ball_idx)
        self._update_matrix_buttons()
        self._update_keyboard_labels()

    def _set_ball_side_length(self, ball_idx: int, side: str, new_len: int):
        if not hasattr(self, 'system') or not (0 <= ball_idx < len(self.system.pendulums)):
            return
        cur_left, cur_right = self._get_ball_steps(ball_idx)
        if side == 'left':
            cur_left = resize_pattern(cur_left, new_len)
        else:
            cur_right = resize_pattern(cur_right, new_len)
        self.ball_custom_strikes[ball_idx] = (list(cur_left), list(cur_right))
        self.system.custom_ball_strikes[ball_idx] = (list(cur_left), list(cur_right))
        self._select_ball(ball_idx)
        self._update_matrix_buttons()
        self._update_keyboard_labels()
        self._update_hud_info()

    def _step_ball_side_length(self, ball_idx: int, side: str, delta: int):
        cur_left, cur_right = self._get_ball_steps(ball_idx)
        cur_len = len(cur_left) if side == 'left' else len(cur_right)
        target_len = max(MIN_PATTERN_STEPS, min(MAX_PATTERN_STEPS, cur_len + delta))
        self._set_ball_side_length(ball_idx, side, target_len)

    def _step_target_side_length(self, side: str, delta: int) -> List[int]:
        if not hasattr(self, 'system') or not self.system.pendulums:
            return []
        targets = self._get_pattern_target_balls()
        if not targets:
            return []
        new_lens: List[int] = []
        for b in targets:
            cur_left, cur_right = self._get_ball_steps(b)
            cur_len = len(cur_left) if side == 'left' else len(cur_right)
            target_len = max(MIN_PATTERN_STEPS, min(MAX_PATTERN_STEPS, cur_len + delta))
            if side == 'left':
                cur_left = resize_pattern(cur_left, target_len)
            else:
                cur_right = resize_pattern(cur_right, target_len)
            self.ball_custom_strikes[b] = (list(cur_left), list(cur_right))
            self.system.custom_ball_strikes[b] = (list(cur_left), list(cur_right))
            new_lens.append(target_len)
        self._sync_side_panel_controls()
        self._update_matrix_buttons()
        self._update_keyboard_labels()
        self._update_hud_info()
        return new_lens

    def _cycle_ball_side_length(self, ball_idx: int, side: str, delta: int = 1):
        cur_left, cur_right = self._get_ball_steps(ball_idx)
        cur_len = len(cur_left) if side == 'left' else len(cur_right)
        span = MAX_PATTERN_STEPS - MIN_PATTERN_STEPS + 1
        target_len = ((cur_len - MIN_PATTERN_STEPS + delta) % span) + MIN_PATTERN_STEPS
        self._set_ball_side_length(ball_idx, side, target_len)

    def _get_matrix_step_colors(
        self, ball_idx: int, side: str, is_active_slot: bool, step_state: int, is_muted: bool, side_count: int = 1
    ) -> Tuple[str, str, str, str]:
        if not is_active_slot:
            return "·", "#0e1017", "#272e40", tk.FLAT
        if is_tie(step_state):
            if is_muted:
                bg_m, fg_m = ("#134e48", "#6ee7b7") if side == 'left' else ("#4c0519", "#fda4af")
                return "~", bg_m, fg_m, tk.GROOVE
            return "~", "#78350f", "#fde047", tk.GROOVE
        if not is_hit(step_state):
            if is_muted:
                bg_m, fg_m = ("#134e48", "#6ee7b7") if side == 'left' else ("#4c0519", "#fda4af")
                return "-", bg_m, fg_m, tk.FLAT
            return "-", "#1a2030", "#64748b", tk.FLAT
        if is_muted:
            bg_m, fg_m = ("#134e48", "#6ee7b7") if side == 'left' else ("#4c0519", "#fda4af")
            return "x", bg_m, fg_m, tk.RAISED
        accomp_mode = self.chord_play_mode_var.get() if self._is_chord_enabled_for_accompaniment() else "off"
        if accomp_mode == "block" and side_count >= 2:
            return "x", "#e11d48", "#ffffff", tk.RAISED
        if accomp_mode == "strum" and side_count >= 2:
            return "x", "#d97706", "#ffffff", tk.RAISED
        return "x", self.system.pendulums[ball_idx].color, "#0f1117", tk.RAISED

    def _update_matrix_buttons(self):
        if not hasattr(self, 'matrix_rows_frame') or not hasattr(self, 'system'):
            return
        n = len(self.system.pendulums)
        is_all_pat = self._is_pattern_all_mode()
        for i in range(n):
            p = self.system.pendulums[i]
            is_muted = (self.anim_time < self.pendulum_mutes.get(i, 0.0))
            is_selected = (i == self.selected_ball_idx)

            if i in self.matrix_vox_buttons:
                v_btn = self.matrix_vox_buttons[i]
                if is_all_pat:
                    v_bg = "#2a1810" if is_muted else "#451a03"
                    v_fg = "#f87171" if is_muted else "#fde047"
                    v_relief = tk.SOLID
                    v_bd = 1
                else:
                    v_bg = "#293a5a" if is_selected else ("#181a24" if is_muted else "#161b27")
                    v_fg = "#ffffff" if is_selected else ("#f87171" if is_muted else p.color)
                    v_relief = tk.SOLID if is_selected else tk.FLAT
                    v_bd = 1 if is_selected else 0

                # Dynamic text: drum voice or note name
                sample_eng = get_sample_engine()
                bank = sample_eng.get_bank(self.timbre_var.get())
                if bank and (bank.is_drums or bank.is_mix):
                    v_key = sample_eng.get_pendulum_drum_voice(i, self.timbre_var.get())
                    if v_key == "__melodic__":
                        btn_text = f"[{i+1}]{midi_to_note_name(p.base_pitch)}"
                    elif v_key.startswith("melodic:"):
                        btn_text = f"[{i+1}]{v_key[8:11].capitalize()}"
                    else:
                        lbl = DRUM_VOICE_SHORT.get(v_key, v_key[:3].capitalize())
                        btn_text = f"[{i+1}]{lbl}"
                else:
                    btn_text = f"[{i+1}]{midi_to_note_name(p.base_pitch)}"

                v_btn.config(
                    text=btn_text,
                    bg=v_bg,
                    fg=v_fg,
                    relief=v_relief,
                    bd=v_bd
                )

            if i in self.matrix_mute_buttons:
                m_btn = self.matrix_mute_buttons[i]
                m_btn.config(
                    bg="#7f1d1d" if is_muted else "#232736",
                    fg="#fca5a5" if is_muted else "#94a3b8"
                )

            left_steps, right_steps = self._get_ball_steps(i)
            for side_n, side_arr in (("left", left_steps), ("right", right_steps)):
                l_btn = self.matrix_len_buttons.get((i, side_n))
                if l_btn:
                    s_len = len(side_arr)
                    arrow = "◄" if side_n == "left" else "►"
                    is_custom_len = (s_len != DEFAULT_PATTERN_STEPS)
                    l_btn.config(
                        text=f"{arrow}{s_len}",
                        bg="#164e63" if (side_n == "left" and is_custom_len) else ("#7c2d12" if (side_n == "right" and is_custom_len) else "#1e2433"),
                        fg="#67e8f9" if (side_n == "left" and is_custom_len) else ("#fdba74" if (side_n == "right" and is_custom_len) else "#94a3b8"),
                    )

            left_count = count_hits(left_steps)
            right_count = count_hits(right_steps)
            for s in range(MAX_PATTERN_STEPS):
                b_left = self.matrix_step_buttons.get((i, 'left', s))
                if b_left:
                    in_l = (s < len(left_steps))
                    txt_l, bg_col, fg_col, rel_l = self._get_matrix_step_colors(
                        i, 'left', in_l, left_steps[s] if in_l else STEP_REST, is_muted, left_count
                    )
                    b_left.config(text=txt_l, bg=bg_col, fg=fg_col, relief=rel_l)

                b_right = self.matrix_step_buttons.get((i, 'right', s))
                if b_right:
                    in_r = (s < len(right_steps))
                    txt_r, bg_col, fg_col, rel_r = self._get_matrix_step_colors(
                        i, 'right', in_r, right_steps[s] if in_r else STEP_REST, is_muted, right_count
                    )
                    b_right.config(text=txt_r, bg=bg_col, fg=fg_col, relief=rel_r)

    def _flash_matrix_step(self, ball_idx: int, side: str, step_idx: int, flash_ms: int = 85):
        btn = self.matrix_step_buttons.get((ball_idx, side, step_idx))
        if not btn:
            return
        try:
            btn.config(bg="#ffffff", fg="#000000")
        except Exception:
            return

        k = (ball_idx, side, step_idx)
        if k in self.matrix_step_flash_resets:
            self.root.after_cancel(self.matrix_step_flash_resets[k])

        def revert():
            if hasattr(self, 'system') and ball_idx < len(self.system.pendulums):
                is_muted = (self.anim_time < self.pendulum_mutes.get(ball_idx, 0.0))
                left_steps, right_steps = self._get_ball_steps(ball_idx)
                side_steps = left_steps if side == 'left' else right_steps
                in_bounds = (0 <= step_idx < len(side_steps))
                step_st = side_steps[step_idx] if in_bounds else STEP_REST
                txt_c, bg_col, fg_col, rel_c = self._get_matrix_step_colors(
                    ball_idx, side, in_bounds, step_st, is_muted, count_hits(side_steps)
                )
                try:
                    btn.config(text=txt_c, bg=bg_col, fg=fg_col, relief=rel_c)
                except Exception:
                    pass
            self.matrix_step_flash_resets.pop(k, None)

        self.matrix_step_flash_resets[k] = self.root.after(max(60, int(flash_ms)), revert)

    def _trigger_secondary_strike_matrix(
        self, idx: int, pitch: int, vel: int, dur: float, pan: float,
        side: str = 'right', strike_idx: int = 1, allow_when_paused: bool = False,
        flash_ms: int = 85
    ):
        if (not self.is_live_active and not allow_when_paused) or self.anim_time < self.pendulum_mutes.get(idx, 0.0):
            return
        self.audio_engine.play_note(
            pitch=pitch,
            velocity=vel,
            duration=dur,
            pan=pan,
            pendulum_index=idx
        )
        self._register_sounding_pendulum_pitch(pitch, dur)
        self.active_flashes[idx] = 10
        self._flash_matrix_step(idx, side, strike_idx, flash_ms=flash_ms)
        if hasattr(self, 'pilot_flashes') and idx in self.pilot_flashes:
            if strike_idx < len(self.pilot_flashes[idx][side]):
                self.pilot_flashes[idx][side][strike_idx] = 10
            self.pilot_flashes[idx]['last_dir'] = side

    def _open_keyboard_props_dialog(self):
        """Opens a dialog window to configure the live keyboard voice (linked or independent)."""
        existing = getattr(self, '_kb_props_win', None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                self._kb_props_win = None

        win = tk.Toplevel(self.root)
        self._kb_props_win = win
        win.title("🎹 Propiedades del Piano / Teclado")
        win.geometry("500x540")
        win.configure(bg="#161922")
        win.transient(self.root)

        def _close_win():
            if getattr(self, '_kb_props_win', None) is win:
                self._kb_props_win = None
            try:
                win.destroy()
            except Exception:
                pass
            if hasattr(self, 'canvas'):
                self.canvas.focus_set()

        win.protocol("WM_DELETE_WINDOW", _close_win)

        tk.Label(
            win,
            text="🎹 Configuración de Voz del Piano / Teclado",
            font=("Segoe UI", 11, "bold"),
            fg="#38bdf8",
            bg="#161922"
        ).pack(pady=(12, 4))

        tk.Label(
            win,
            text="Cambia instrumento y propiedades de la voz del teclado de forma independiente o ligada:",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#161922"
        ).pack(pady=(0, 8))

        # Section 1: Link / Independent Mode
        link_frame = tk.LabelFrame(
            win,
            text=" 🔗 Enlace con el Acompañamiento ",
            font=("Segoe UI", 9, "bold"),
            fg="#00f5d4",
            bg="#1a1f2e",
            padx=10,
            pady=6,
        )
        link_frame.pack(padx=16, pady=(0, 10), fill=tk.X)

        link_var = tk.BooleanVar(value=bool(self.kb_link_accompaniment_var.get()))
        tk.Radiobutton(
            link_frame,
            text="🔗 Ligado al acompañamiento (cambia tono y acordes de las bolas)",
            variable=link_var,
            value=True,
            font=("Segoe UI", 8, "bold"),
            fg="#e2e8f0",
            bg="#1a1f2e",
            selectcolor="#0f172a",
            activebackground="#1a1f2e",
            activeforeground="#38bdf8",
            anchor="w",
        ).pack(fill=tk.X, pady=2)

        tk.Radiobutton(
            link_frame,
            text="🎹 Independiente — Solista libre (no altera el tono ni las bolas)",
            variable=link_var,
            value=False,
            font=("Segoe UI", 8, "bold"),
            fg="#6ee7b7",
            bg="#1a1f2e",
            selectcolor="#0f172a",
            activebackground="#1a1f2e",
            activeforeground="#6ee7b7",
            anchor="w",
        ).pack(fill=tk.X, pady=2)

        # Section 2: Voice Properties
        frame = tk.LabelFrame(
            win,
            text=" 🎛 Propiedades de la Voz del Teclado ",
            font=("Segoe UI", 9, "bold"),
            fg="#ffd166",
            bg="#161922",
            padx=12,
            pady=8,
        )
        frame.pack(padx=16, fill=tk.X)
        frame.columnconfigure(1, weight=1)

        # Row 0: Instrument / Timbre
        tk.Label(frame, text="Instrumento / Timbre:", font=("Segoe UI", 9, "bold"), fg="#cad3f5", bg="#161922").grid(row=0, column=0, sticky=tk.W, pady=6, padx=(0, 8))
        inst_list = self._get_instrument_list()
        timbre_vals = ["(Seguir Acompañamiento)"] + inst_list
        timbre_combo = ttk.Combobox(frame, values=timbre_vals, state="readonly", width=28)
        timbre_combo.grid(row=0, column=1, sticky=tk.EW, pady=6)

        # Row 1: Sound Mode
        tk.Label(frame, text="Modo de Sonido:", font=("Segoe UI", 9, "bold"), fg="#cad3f5", bg="#161922").grid(row=1, column=0, sticky=tk.W, pady=6, padx=(0, 8))
        s_keys = list(KEYBOARD_SOUND_MODES.keys())
        sound_combo = ttk.Combobox(
            frame,
            values=[KEYBOARD_SOUND_MODES[k]["name"] for k in s_keys],
            state="readonly",
            width=28,
        )
        sound_combo.grid(row=1, column=1, sticky=tk.EW, pady=6)

        # Row 2: Duration / Sustain
        tk.Label(frame, text="Duración / Sustain:", font=("Segoe UI", 9, "bold"), fg="#cad3f5", bg="#161922").grid(row=2, column=0, sticky=tk.W, pady=6, padx=(0, 8))
        dur_keys = [k for k in NOTE_DURATIONS.keys() if k != 'auto']
        dur_vals = ["(Auto - Hold / Clic)"] + [NOTE_DURATIONS[k]['name'] for k in dur_keys]
        dur_combo = ttk.Combobox(frame, values=dur_vals, state="readonly", width=28)
        dur_combo.grid(row=2, column=1, sticky=tk.EW, pady=6)

        # Row 3: Octave Offset
        tk.Label(frame, text="Octava del Teclado:", font=("Segoe UI", 9, "bold"), fg="#cad3f5", bg="#161922").grid(row=3, column=0, sticky=tk.W, pady=6, padx=(0, 8))
        oct_opts = [
            (-2, "-2 octavas (-24 st)"),
            (-1, "-1 octava (-12 st)"),
            (0, "0 (Misma octava)"),
            (1, "+1 octava (+12 st)"),
            (2, "+2 octavas (+24 st)"),
        ]
        oct_combo = ttk.Combobox(frame, values=[o[1] for o in oct_opts], state="readonly", width=28)
        oct_combo.grid(row=3, column=1, sticky=tk.EW, pady=6)

        # Row 4: Decay / Resonance
        tk.Label(frame, text="Decay / Resonancia:", font=("Segoe UI", 9, "bold"), fg="#cad3f5", bg="#161922").grid(row=4, column=0, sticky=tk.W, pady=6, padx=(0, 8))
        decay_row = tk.Frame(frame, bg="#161922")
        decay_row.grid(row=4, column=1, sticky=tk.EW, pady=6)
        decay_follow_var = tk.BooleanVar(value=bool(self.kb_decay_follow_var.get()))
        decay_val_var = tk.DoubleVar(value=float(self.kb_decay_var.get()))
        lbl_decay_val = tk.Label(decay_row, text="", font=("Consolas", 8, "bold"), fg="#00f5d4", bg="#161922", width=5, anchor="e")
        lbl_decay_val.pack(side=tk.RIGHT)
        decay_scale = tk.Scale(
            decay_row,
            from_=0.2,
            to=3.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            variable=decay_val_var,
            showvalue=False,
            bg="#161922",
            fg="#00f5d4",
            troughcolor="#0f172a",
            highlightthickness=0,
            bd=0,
            length=120,
        )
        decay_scale.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 4))

        def _sync_decay_widgets(*_args):
            if decay_follow_var.get():
                decay_scale.config(state=tk.DISABLED)
                lbl_decay_val.config(text=f"{float(self.decay_var.get()):.1f}x", fg="#64748b")
            else:
                decay_scale.config(state=tk.NORMAL)
                lbl_decay_val.config(text=f"{float(decay_val_var.get()):.1f}x", fg="#00f5d4")

        chk_decay_follow = tk.Checkbutton(
            decay_row,
            text="Seguir",
            variable=decay_follow_var,
            command=_sync_decay_widgets,
            font=("Segoe UI", 8),
            fg="#cbd5e1",
            bg="#161922",
            selectcolor="#0f172a",
            activebackground="#161922",
            activeforeground="#38bdf8",
        )
        chk_decay_follow.pack(side=tk.LEFT)
        decay_scale.config(command=lambda _v: _sync_decay_widgets())

        # Row 5: Volume / Force
        tk.Label(frame, text="Volumen / Fuerza:", font=("Segoe UI", 9, "bold"), fg="#cad3f5", bg="#161922").grid(row=5, column=0, sticky=tk.W, pady=6, padx=(0, 8))
        vol_row = tk.Frame(frame, bg="#161922")
        vol_row.grid(row=5, column=1, sticky=tk.EW, pady=6)
        vol_pct_var = tk.IntVar(value=int(round(float(self.kb_volume_var.get()) * 100)))
        lbl_vol_val = tk.Label(vol_row, text=f"{vol_pct_var.get()}%", font=("Consolas", 8, "bold"), fg="#ffd166", bg="#161922", width=5, anchor="e")
        lbl_vol_val.pack(side=tk.RIGHT)
        vol_scale = tk.Scale(
            vol_row,
            from_=20,
            to=150,
            resolution=5,
            orient=tk.HORIZONTAL,
            variable=vol_pct_var,
            showvalue=False,
            bg="#161922",
            fg="#ffd166",
            troughcolor="#0f172a",
            highlightthickness=0,
            bd=0,
            command=lambda v: lbl_vol_val.config(text=f"{int(float(v))}%"),
        )
        vol_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        # Row 6: Stereo Pan
        tk.Label(frame, text="Paneo Estéreo:", font=("Segoe UI", 9, "bold"), fg="#cad3f5", bg="#161922").grid(row=6, column=0, sticky=tk.W, pady=6, padx=(0, 8))
        pan_row = tk.Frame(frame, bg="#161922")
        pan_row.grid(row=6, column=1, sticky=tk.EW, pady=6)
        pan_pct_var = tk.IntVar(value=int(round(float(self.kb_pan_var.get()) * 100)))

        def _format_pan(val_i: int) -> str:
            if val_i == 0:
                return "Centro"
            return f"Izq {abs(val_i)}%" if val_i < 0 else f"Der {val_i}%"

        lbl_pan_val = tk.Label(pan_row, text=_format_pan(pan_pct_var.get()), font=("Consolas", 8, "bold"), fg="#38bdf8", bg="#161922", width=8, anchor="e")
        lbl_pan_val.pack(side=tk.RIGHT)
        pan_scale = tk.Scale(
            pan_row,
            from_=-100,
            to=100,
            resolution=10,
            orient=tk.HORIZONTAL,
            variable=pan_pct_var,
            showvalue=False,
            bg="#161922",
            fg="#38bdf8",
            troughcolor="#0f172a",
            highlightthickness=0,
            bd=0,
            command=lambda v: lbl_pan_val.config(text=_format_pan(int(float(v)))),
        )
        pan_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        def _load_widgets_from_state():
            link_var.set(bool(self.kb_link_accompaniment_var.get()))
            cur_t = self.kb_timbre_var.get().strip()
            if cur_t and cur_t in inst_list:
                timbre_combo.current(inst_list.index(cur_t) + 1)
            else:
                timbre_combo.current(0)

            cur_s = self.keyboard_sound_mode_var.get()
            sound_combo.current(s_keys.index(cur_s) if cur_s in s_keys else 0)

            cur_d = self.kb_duration_mode_var.get()
            if cur_d in dur_keys:
                dur_combo.current(dur_keys.index(cur_d) + 1)
            else:
                dur_combo.current(0)

            cur_oct = int(self.kb_octave_offset_var.get())
            oct_vals_only = [o[0] for o in oct_opts]
            oct_combo.current(oct_vals_only.index(cur_oct) if cur_oct in oct_vals_only else 2)

            decay_follow_var.set(bool(self.kb_decay_follow_var.get()))
            decay_val_var.set(float(self.kb_decay_var.get()))
            _sync_decay_widgets()

            vol_pct_var.set(int(round(float(self.kb_volume_var.get()) * 100)))
            lbl_vol_val.config(text=f"{vol_pct_var.get()}%")

            pan_pct_var.set(int(round(float(self.kb_pan_var.get()) * 100)))
            lbl_pan_val.config(text=_format_pan(pan_pct_var.get()))

        _load_widgets_from_state()

        def _resolve_dialog_params():
            t_idx = timbre_combo.current()
            chosen_timbre = "" if t_idx <= 0 else inst_list[t_idx - 1]
            s_idx = sound_combo.current()
            chosen_sound = s_keys[s_idx] if 0 <= s_idx < len(s_keys) else "hold"
            d_idx = dur_combo.current()
            chosen_dur = "auto" if d_idx <= 0 else dur_keys[d_idx - 1]
            o_idx = oct_combo.current()
            chosen_oct = oct_opts[o_idx][0] if 0 <= o_idx < len(oct_opts) else 0
            return {
                "link": bool(link_var.get()),
                "timbre": chosen_timbre,
                "sound_mode": chosen_sound,
                "dur_mode": chosen_dur,
                "oct_offset": chosen_oct,
                "decay_follow": bool(decay_follow_var.get()),
                "decay_val": max(0.2, min(3.0, float(decay_val_var.get()))),
                "volume": max(0.2, min(1.5, float(vol_pct_var.get()) / 100.0)),
                "pan": max(-1.0, min(1.0, float(pan_pct_var.get()) / 100.0)),
            }

        def preview_note():
            cfg = _resolve_dialog_params()
            eff_inst = cfg["timbre"] or self.timbre_var.get()
            eff_decay = None if cfg["decay_follow"] else cfg["decay_val"]
            base_midi = (
                self.pitch_follow.keyboard_base_midi
                if hasattr(self, 'pitch_follow')
                else note_name_to_midi(self.root_key_var.get(), self.octave_var.get())
            )
            test_midi = max(21, min(108, int(base_midi) + int(cfg["oct_offset"]) * 12))
            dur_s = (
                float(NOTE_DURATIONS.get(cfg["dur_mode"], {}).get('sec') or 0.9)
                if cfg["dur_mode"] != "auto"
                else 0.9
            )
            test_vel = max(20, min(127, int(round(108 * cfg["volume"]))))
            try:
                timbre_alias = {'chimes': 'celesta', 'pluck': 'guitar-nylon', 'percussion': 'drums'}
                target_inst = timbre_alias.get(eff_inst.lower(), eff_inst.lower())
                get_sample_engine().get_bank(target_inst, load=True)
            except Exception:
                pass
            self.audio_engine.play_note(
                pitch=test_midi,
                velocity=test_vel,
                duration=dur_s,
                pan=cfg["pan"],
                pendulum_index=KEYBOARD_VOICE_INDEX,
                timbre=eff_inst,
                decay=eff_decay,
            )

        def apply_changes():
            cfg = _resolve_dialog_params()
            self.kb_link_accompaniment_var.set(cfg["link"])
            self.kb_timbre_var.set(cfg["timbre"])
            self.kb_duration_mode_var.set(cfg["dur_mode"])
            self.kb_octave_offset_var.set(cfg["oct_offset"])
            self.kb_decay_follow_var.set(cfg["decay_follow"])
            self.kb_decay_var.set(cfg["decay_val"])
            self.kb_volume_var.set(cfg["volume"])
            self.kb_pan_var.set(cfg["pan"])

            self.keyboard_sound_mode_var.set(cfg["sound_mode"])
            if cfg["sound_mode"] != "silent":
                self.keyboard_sound_last_active_mode = cfg["sound_mode"]

            eff_inst = cfg["timbre"].strip()
            if eff_inst:
                try:
                    timbre_alias = {'chimes': 'celesta', 'pluck': 'guitar-nylon', 'percussion': 'drums'}
                    target_inst = timbre_alias.get(eff_inst.lower(), eff_inst.lower())
                    get_sample_engine().get_bank(target_inst, load=True)
                except Exception:
                    pass

            self._stop_all_follow_key_voices()
            self._update_kb_sound_controls()
            self._update_kb_props_button()
            self._update_follow_indicator()
            self._update_piano_keyboard_labels()
            _close_win()

        def reset_to_accompaniment():
            self._reset_keyboard_voice_props()
            _load_widgets_from_state()

        btn_box = tk.Frame(win, bg="#161922")
        btn_box.pack(pady=16)
        tk.Button(btn_box, text="🔊 Probar Nota", font=("Segoe UI", 8, "bold"), bg="#065f46", fg="#6ee7b7", padx=8, pady=3, relief=tk.FLAT, cursor="hand2", command=preview_note).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_box, text="Aplicar", font=("Segoe UI", 9, "bold"), bg="#38bdf8", fg="#0f1117", padx=12, pady=3, relief=tk.FLAT, cursor="hand2", command=apply_changes).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_box, text="Igualar al Acomp.", font=("Segoe UI", 8), bg="#252b3b", fg="#cad3f5", padx=8, pady=3, relief=tk.FLAT, cursor="hand2", command=reset_to_accompaniment).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_box, text="Cerrar", font=("Segoe UI", 8), bg="#252b3b", fg="#94a3b8", padx=8, pady=3, relief=tk.FLAT, cursor="hand2", command=_close_win).pack(side=tk.LEFT, padx=4)

    def _open_custom_props_dialog(self):
        self._open_keyboard_props_dialog()

    def _toggle_view_mode(self):
        if self.view_mode_var.get() == "uniform":
            self.view_mode_var.set("cascade")
            self.btn_view.config(text="📶 Cascada", bg="#f72585")
        else:
            self.view_mode_var.set("uniform")
            self.btn_view.config(text="📏 Misma Altura", bg="#3a86ff")

    def _modulate_key(self, delta: int):
        cur_midi = note_name_to_midi(self.root_key_var.get(), self.octave_var.get())
        target_midi = max(MIN_FOLLOW_MIDI, min(MAX_FOLLOW_MIDI, cur_midi + int(delta)))
        new_key = NOTE_NAMES[target_midi % 12]
        new_oct = (target_midi // 12) - 1
        self.root_key_var.set(new_key)
        self.octave_var.set(new_oct)
        if hasattr(self, 'system'):
            self.system.set_root_pitch_inplace(new_key, new_oct)
        if hasattr(self, 'pitch_follow'):
            self.pitch_follow.sync_external_root(
                target_midi, update_home=True, recenter_keyboard=True
            )
        self._update_hud_info()
        self._update_follow_indicator()
        self._update_matrix_buttons()
        self._sync_side_panel_ball_names()
        self._update_piano_keyboard_labels()

    def _on_harmony_selected(self, event):
        idx = self.harm_combo.current()
        harm_keys = list(HARMONIC_TYPES.keys())
        if 0 <= idx < len(harm_keys):
            self.harmony_type_var.set(harm_keys[idx])
            self._init_system()
        self.canvas.focus_set()

    def _pluck_pendulum(self, idx: int, hold: bool = False):
        if idx < len(self.system.pendulums):
            p = self.system.pendulums[idx]
            dur = 4.5 if hold else self.system.get_current_note_duration(idx)
            ch, rec_ev = self.audio_engine.play_note(
                pitch=p.base_pitch,
                velocity=120,
                duration=dur,
                pan=p.pan,
                pendulum_index=idx
            )
            self._register_sounding_pendulum_pitch(p.base_pitch, dur)
            self.active_flashes[idx] = 16
            # Apply visual pendulum kick impulse!
            self.pendulum_impulses[idx] = 0.35
            return ch, rec_ev
        return None, None

    def _strum_wave(self):
        def strum_task():
            for i, p in enumerate(self.system.pendulums):
                dur = self.system.get_current_note_duration(i)
                self.audio_engine.play_note(
                    pitch=p.base_pitch,
                    velocity=112,
                    duration=dur,
                    pan=p.pan,
                    pendulum_index=i
                )
                self.active_flashes[i] = 14
                self.pendulum_impulses[i] = 0.28
                time.sleep(0.045)
        threading.Thread(target=strum_task, daemon=True).start()

    def _on_duration_selected(self, event=None):
        idx = self.dur_combo.current()
        keys = list(NOTE_DURATIONS.keys())
        if 0 <= idx < len(keys):
            self.duration_mode_var.set(keys[idx])
            self.system.set_note_duration(keys[idx])
            self._update_hud_info()
            self.canvas.focus_set()

    def _cycle_duration(self, delta: int = 1):
        keys = list(NOTE_DURATIONS.keys())
        cur = self.duration_mode_var.get()
        idx = keys.index(cur) if cur in keys else 0
        new_idx = (idx + delta) % len(keys)
        nxt = keys[new_idx]
        self.duration_mode_var.set(nxt)
        self.dur_combo.current(new_idx)
        self.system.set_note_duration(nxt)
        self._update_hud_info()
        self.canvas.focus_set()

    def _dampen_all(self):
        self._cancel_pending_strum_afters()
        self.space_silence_active = False
        self.space_silence_until = 0.0
        self._pre_space_mutes.clear()
        self._backing_paused_by_space = False
        self.active_flashes = {i: 0 for i in range(self.system.n_pendulums)}
        self.pilot_flashes = {
            i: {'left': [0] * MAX_PATTERN_STEPS, 'right': [0] * MAX_PATTERN_STEPS, 'last_dir': 'right'}
            for i in range(self.system.n_pendulums)
        }
        self.pendulum_impulses = {i: 0.0 for i in range(self.system.n_pendulums)}
        self.held_notes.clear()
        self.sustained_channels.clear()
        self.pendulum_mutes.clear()
        if hasattr(self, 'sounding_pendulum_pitches'):
            self.sounding_pendulum_pitches.clear()
        if hasattr(self, 'follow_key_voices'):
            self._stop_all_follow_key_voices()
        if hasattr(self, 'held_transpose_keys'):
            self.held_transpose_keys.clear()
        if hasattr(self, 'pitch_follow'):
            self.pitch_follow.pending_midi = None
            self.pitch_follow.held_piano_keys.clear()
        if hasattr(self, 'btn_mute_b1'):
            self.btn_mute_b1.config(bg="#252b3b", fg="#f87171")
        if hasattr(self, 'btn_mute_b2'):
            self.btn_mute_b2.config(bg="#252b3b", fg="#f87171")
        for after_id in list(self.pending_releases.values()):
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        self.pending_releases.clear()
        if pygame.mixer.get_init():
            pygame.mixer.stop()
        if hasattr(self, 'audio_engine') and self.audio_engine.backing_mgr.is_loaded:
            self.audio_engine.backing_mgr.is_playing = False
            self.audio_engine.backing_mgr.accumulated_pos = 0.0
            self.backing_manually_paused = True
        self._update_pause_button()
        self._update_backing_controls()
        self._update_follow_indicator()
        self._update_piano_keyboard_labels()
        self._update_num_labels()
        self._update_matrix_buttons()

    def _update_pause_button(self):
        if not hasattr(self, 'btn_pause'):
            return
        if not self.is_live_active:
            state = ("▶ Play [Espacio]", "#f59e0b", "#ffffff")
        elif self.space_silence_active:
            bar_sec = max(0.5, self.system.bar_duration_sec) if hasattr(self, 'system') else 2.0
            rem_bars = max(1, int(math.ceil(max(0.0, self.space_silence_until - self.anim_time) / bar_sec)))
            state = (f"🔇 Silencio {rem_bars}c [Espacio]", "#991b1b", "#fecaca")
        else:
            bars = self._parse_silence_bars()
            txt = "⏸ Pausa [Espacio]" if bars is None else f"⏸ Silenc. {bars}c [Espacio]"
            state = (txt, "#252b3b", "#cad3f5")
        if state != self._last_pause_btn_state:
            self._last_pause_btn_state = state
            self.btn_pause.config(text=state[0], bg=state[1], fg=state[2])

    def _end_space_silence(self, early_cancel: bool = False):
        self.space_silence_active = False
        self.space_silence_until = 0.0
        if early_cancel and hasattr(self, 'system'):
            n = self.system.n_pendulums
            all_were_perm = (n > 0 and all(self._pre_space_mutes.get(i, 0.0) == float('inf') for i in range(n)))
            for i in range(n):
                if not all_were_perm and self._pre_space_mutes.get(i, 0.0) == float('inf'):
                    self.pendulum_mutes[i] = float('inf')
                else:
                    self.pendulum_mutes[i] = 0.0
        self._pre_space_mutes.clear()
        if self._backing_paused_by_space:
            self._backing_paused_by_space = False
            if (
                hasattr(self, 'audio_engine')
                and self.audio_engine.backing_mgr.is_loaded
                and not self.audio_engine.backing_mgr.is_playing
            ):
                self._resume_backing_track()
        self._update_pause_button()
        self._update_backing_controls()
        self._update_num_labels()
        self._update_matrix_buttons()
        if self.keyboard_mode == "normal":
            self._update_piano_keyboard_labels()

    def _hard_pause_for_recording_stop(self):
        """Stops live pendulums and backing track cleanly when finishing a recording."""
        self.is_live_active = False
        self.space_silence_active = False
        self.space_silence_until = 0.0
        self._pre_space_mutes.clear()
        self._cancel_pending_strum_afters(include_strums=False)
        if (
            hasattr(self, 'audio_engine')
            and self.audio_engine.backing_mgr.is_loaded
            and self.audio_engine.backing_mgr.is_playing
        ):
            self.audio_engine.backing_mgr.pause()
            self._backing_paused_by_space = True
        self._update_pause_button()
        self._update_backing_controls()
        self._update_num_labels()
        self._update_matrix_buttons()
        if self.keyboard_mode == "normal":
            self._update_piano_keyboard_labels()

    def _toggle_pause(self):
        if not self.is_live_active:
            self.is_live_active = True
            self.space_silence_active = False
            self.space_silence_until = 0.0
            self._pre_space_mutes.clear()
            if getattr(self, 'is_finishing_recording', False):
                self._finalize_live_recording()
            if (
                hasattr(self, 'audio_engine')
                and self.audio_engine.backing_mgr.is_loaded
                and not self.audio_engine.backing_mgr.is_playing
            ):
                if self._backing_paused_by_space or not self.backing_manually_paused:
                    self._resume_backing_track()
                    self._backing_paused_by_space = False
                    self.backing_manually_paused = False
        elif self.space_silence_active:
            self._end_space_silence(early_cancel=True)
            self.canvas.focus_set()
            return
        else:
            silence_bars = self._parse_silence_bars()
            # Detener pasos futuros pero dejar terminar los rasgueos ya iniciados y todas las notas sonando hasta su fin natural
            self._cancel_pending_strum_afters(include_strums=False)
            if silence_bars is None:
                self.is_live_active = False
                self.space_silence_active = False
                self.space_silence_until = 0.0
            else:
                bar_sec = max(0.5, self.system.bar_duration_sec)
                until = self.anim_time + (silence_bars * bar_sec)
                self._pre_space_mutes = dict(self.pendulum_mutes)
                for i in range(self.system.n_pendulums):
                    prev = self.pendulum_mutes.get(i, 0.0)
                    self.pendulum_mutes[i] = float('inf') if prev == float('inf') else max(prev, until)
                self.space_silence_active = True
                self.space_silence_until = until

            if (
                self.space_stops_backing_var.get()
                and hasattr(self, 'audio_engine')
                and self.audio_engine.backing_mgr.is_loaded
                and self.audio_engine.backing_mgr.is_playing
            ):
                self.audio_engine.backing_mgr.pause()
                self._backing_paused_by_space = True

        self._update_pause_button()
        self._update_backing_controls()
        self._update_num_labels()
        self._update_matrix_buttons()
        if self.keyboard_mode == "normal":
            self._update_piano_keyboard_labels()
        self.canvas.focus_set()

    def _format_bpm(self, val: float) -> str:
        rounded = round(val)
        if abs(val - rounded) < 1e-4:
            return f"{int(rounded)}"
        if val >= 10.0:
            return f"{val:.1f}"
        return f"{val:.2f}".rstrip('0').rstrip('.')

    def _set_bpm(self, new_bpm: float):
        # Sin límites superior ni inferior (estrictamente > 0 para física y cálculos temporales)
        new_bpm = max(0.01, float(new_bpm))
        if new_bpm >= 10.0:
            new_bpm = round(new_bpm, 1)
        else:
            new_bpm = round(new_bpm, 2)
        if abs(new_bpm - round(new_bpm)) < 1e-4:
            new_bpm = float(round(new_bpm))
        self.bpm_var.set(new_bpm)
        self.bpm_label.config(text=self._format_bpm(new_bpm))
        self.system.set_tempo(float(new_bpm))

    def _prompt_exact_bpm(self, event=None):
        import tkinter.simpledialog as sd
        res = sd.askfloat(
            "Ajustar BPM",
            "Introduce el tempo BPM deseado (sin límites):",
            initialvalue=float(self.bpm_var.get()),
            minvalue=0.01,
            parent=self.root
        )
        if res is not None:
            self._set_bpm(res)

    def _adjust_bpm(self, delta: float):
        try:
            cur = float(self.bpm_var.get())
        except (ValueError, TypeError):
            cur = 96.0

        # If currently has decimal and delta is integer, snap to next integer in that direction
        if (cur % 1 != 0) and abs(delta) >= 1.0:
            if delta > 0:
                new_bpm = math.floor(cur) + delta
            else:
                new_bpm = math.ceil(cur) + delta
        else:
            new_bpm = cur + delta

        self._set_bpm(new_bpm)

    def _half_bpm(self):
        try:
            cur = float(self.bpm_var.get())
        except (ValueError, TypeError):
            cur = 96.0
        self._set_bpm(cur / 2.0)

    def _double_bpm(self):
        try:
            cur = float(self.bpm_var.get())
        except (ValueError, TypeError):
            cur = 96.0
        self._set_bpm(cur * 2.0)

    def _snap_bpm_integer(self, event=None):
        try:
            cur = float(self.bpm_var.get())
        except (ValueError, TypeError):
            cur = 96.0
        self._set_bpm(round(cur))

    def _adjust_pendulums(self, delta: int):
        """Ajusta el número de péndulos en tiempo real (+1 o -1, rango 1 a 20)."""
        try:
            cur = int(self.n_pendulums_var.get())
        except (ValueError, TypeError):
            cur = len(self.system.pendulums) if hasattr(self, 'system') and self.system.pendulums else 2
        new_val = max(1, min(20, cur + delta))
        if new_val != cur:
            self.n_pendulums_var.set(new_val)
            self._init_system()
            self.canvas.focus_set()

    def _on_timbre_change(self):
        self.audio_engine.set_timbre(self.timbre_var.get())
        if hasattr(self, 'timbre_combo'):
            self.timbre_combo['values'] = self._get_instrument_list()
        self._update_keyboard_labels()
        if hasattr(self, 'side_panel'):
            self._sync_side_panel_controls()
        self._update_matrix_buttons()

    def _update_hud_info(self):
        harm_name = HARMONIC_TYPES[self.harmony_type_var.get()]['name']
        harm_short = (harm_name[:22] + "…") if len(harm_name) > 24 else harm_name
        key_str = f"{self.root_key_var.get()}{self.octave_var.get()}"
        sig_str = self.time_sig_var.get()
        self.harmony_badge.config(text=f"[{key_str} • {sig_str} • {harm_short}]")

    def _update_num_labels(self):
        if not hasattr(self, 'num_labels') or not hasattr(self, 'system'):
            return
        bar_sec = max(0.5, self.system.bar_duration_sec)
        n = self.system.n_pendulums

        if self.keyboard_mode == "strum_dd":
            is_all = (self.strum_target_mode == "all")
            if hasattr(self, 'lbl_num_title'):
                self.lbl_num_title.config(
                    text="🌐 [0] TODAS ON:" if is_all else "[1-9]Bola [0]ALL:",
                    fg="#facc15" if is_all else "#38bdf8"
                )
            for idx, k in enumerate(["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]):
                if k not in self.num_labels:
                    continue
                if k == "0":
                    self.num_labels[k].config(
                        text="[0] ★TODAS" if is_all else "[0] TODAS",
                        bg="#f59e0b" if is_all else "#3b2608",
                        fg="#000000" if is_all else "#fde047",
                        relief=tk.SUNKEN if is_all else tk.RAISED
                    )
                    continue
                if idx >= n:
                    self.num_labels[k].config(
                        text=f"[{k}]",
                        bg="#141722",
                        fg="#334155",
                        relief=tk.FLAT
                    )
                else:
                    c_pat = self.ball_custom_strikes.get(idx)
                    if c_pat:
                        nl = count_hits(c_pat[0]) if isinstance(c_pat[0], (list, tuple)) else c_pat[0]
                        nr = count_hits(c_pat[1]) if isinstance(c_pat[1], (list, tuple)) else c_pat[1]
                        tag = f"({nl}+{nr})"
                    else:
                        tag = "(1+1)"
                    if is_all:
                        self.num_labels[k].config(
                            text=f"[{k}] B{idx+1} {tag}",
                            bg="#78350f",
                            fg="#fef08a",
                            relief=tk.SUNKEN
                        )
                    else:
                        is_sel = (idx == self.selected_ball_idx)
                        self.num_labels[k].config(
                            text=f"[{k}] B{idx+1} {tag}",
                            bg="#0284c7" if is_sel else "#162032",
                            fg="#ffffff" if is_sel else "#93c5fd",
                            relief=tk.SUNKEN if is_sel else tk.RAISED
                        )
            return

        if hasattr(self, 'lbl_num_title'):
            self.lbl_num_title.config(text="[1-0] Silenciar:", fg="#f87171")

        for idx, k in enumerate(["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]):
            if k not in self.num_labels:
                continue
            if idx >= n:
                self.num_labels[k].config(
                    text=f"[{k}]",
                    bg="#141722",
                    fg="#334155",
                    relief=tk.FLAT
                )
                continue

            mute_time = self.pendulum_mutes.get(idx, 0.0)
            is_muted = (self.anim_time < mute_time)
            has_custom = (
                idx in self.ball_custom_dynamics or
                idx in self.ball_custom_durations or
                idx in self.ball_custom_strikes or
                idx in self.ball_custom_palettes or
                idx in self.ball_custom_strum_ratio or
                idx in self.ball_custom_strum_sens
            )
            c_pat = self.ball_custom_strikes.get(idx)
            if c_pat:
                nl = count_hits(c_pat[0]) if isinstance(c_pat[0], (list, tuple)) else c_pat[0]
                nr = count_hits(c_pat[1]) if isinstance(c_pat[1], (list, tuple)) else c_pat[1]
                pat_tag = f"({nl}+{nr})"
            else:
                pat_tag = ""

            c_pal = self.ball_custom_palettes.get(idx)
            pal_tag = f"[{HARMONIC_FILL_PALETTES.get(c_pal, {}).get('short', c_pal[:3])}]" if c_pal else ""
            tag_str = f"{pat_tag}{pal_tag}".strip()

            if is_muted:
                if mute_time == float('inf'):
                    lbl_text = f"[{k}] 🔇"
                else:
                    rem_sec = max(0.0, mute_time - self.anim_time)
                    rem_bars = rem_sec / bar_sec
                    lbl_text = f"[{k}] 🔇{rem_bars:.0f}c"
                if has_custom:
                    lbl_text += "⚡"
                self.num_labels[k].config(
                    text=lbl_text,
                    bg="#7f1d1d",
                    fg="#fca5a5",
                    relief=tk.SUNKEN
                )
            else:
                cust_badge = "⚡" if has_custom else ""
                lbl_text = f"[{k}] P{idx+1} {tag_str}{cust_badge}".strip()
                self.num_labels[k].config(
                    text=lbl_text,
                    bg="#1e3a5f" if has_custom else "#1e2230",
                    fg="#38bdf8" if has_custom else "#93c5fd",
                    relief=tk.RAISED
                )

    def _get_keyboard_red_pitches(self) -> Tuple[Set[int], Set[int], Set[int]]:
        """Returns (exact_midi_pitches, pitch_classes, sounding_exact) to highlight on the piano keyboard."""
        if not hasattr(self, 'system') or not self.system.pendulums or self.system.harmony_type == 'drum_kit':
            return set(), set(), set()

        unmuted_indices = [
            i
            for i in range(len(self.system.pendulums))
            if not (self.anim_time < self.pendulum_mutes.get(i, 0.0))
        ]
        if not unmuted_indices:
            return set(), set(), set()

        exact_red: Set[int] = {self.system.pendulums[i].base_pitch for i in unmuted_indices}
        if getattr(self, 'active_chord_pitches', None):
            exact_red.update(self.active_chord_pitches)

        now = time.time()
        sounding_exact: Set[int] = {
            midi_p
            for midi_p, exp in getattr(self, 'sounding_pendulum_pitches', {}).items()
            if exp > now
        }
        exact_red.update(sounding_exact)

        red_pcs = {m % 12 for m in exact_red}
        return exact_red, red_pcs, sounding_exact

    def _register_sounding_pendulum_pitch(self, pitch: int, duration: float):
        """Records a temporarily sounding pendulum pitch and refreshes piano red/gold keys if needed."""
        if not hasattr(self, 'system') or self.system.harmony_type == 'drum_kit':
            return
        ttl = min(max(float(duration) * 0.90, 0.16), 3.0)
        self.sounding_pendulum_pitches[int(pitch)] = time.time() + ttl
        if self.keyboard_mode == "normal":
            exact_red, red_pcs, sounding_exact = self._get_keyboard_red_pitches()
            state = (frozenset(exact_red), frozenset(red_pcs), frozenset(sounding_exact))
            if state != self._last_piano_red_state:
                self._update_piano_keyboard_labels()

    def _style_piano_key_label(
        self,
        lbl: tk.Label,
        txt: str,
        midi_val: Optional[int],
        is_black: bool,
        is_active: bool,
        is_pending: bool,
        is_held: bool,
        exact_red: Set[int],
        red_pcs: Set[int],
        sounding_exact: Optional[Set[int]] = None,
    ):
        """Styles a virtual piano key according to held/pending/sounding/red-chord/active priority."""
        if is_held:
            bg, fg, relief, hb = "#00f5d4", "#000000", tk.SUNKEN, "#ffffff"
        elif is_pending:
            bg, fg, relief, hb = "#f59e0b", "#000000", tk.SUNKEN, "#fef08a"
        elif midi_val is not None and sounding_exact and midi_val in sounding_exact:
            bg, fg, relief, hb = "#fde047", "#0f1117", tk.SUNKEN, "#ffffff"
        elif midi_val is not None and midi_val in exact_red:
            if is_active:
                bg, fg, relief, hb = "#ef4444", "#ffffff", tk.SUNKEN, "#00f5d4"
            elif is_black:
                bg, fg, relief, hb = "#b91c1c", "#ffffff", tk.RAISED, "#f87171"
            else:
                bg, fg, relief, hb = "#dc2626", "#ffffff", tk.RAISED, "#fca5a5"
        elif midi_val is not None and (midi_val % 12) in red_pcs:
            if is_active:
                bg, fg, relief, hb = "#ef4444", "#ffffff", tk.SUNKEN, "#00f5d4"
            elif is_black:
                bg, fg, relief, hb = "#7f1d1d", "#fecaca", tk.RAISED, "#b91c1c"
            else:
                bg, fg, relief, hb = "#991b1b", "#fee2e2", tk.RAISED, "#dc2626"
        elif is_active:
            bg, fg, relief, hb = "#00f5d4", "#000000", tk.SUNKEN, "#00f5d4"
        elif is_black:
            bg, fg, relief, hb = "#12151f", "#c084fc", tk.RAISED, "#13161f"
        else:
            bg, fg, relief, hb = "#232d3f", "#f1f5f9", tk.RAISED, "#13161f"

        lbl.config(text=txt, bg=bg, fg=fg, relief=relief, highlightbackground=hb, cursor="hand2")

    def _update_strum_step_row(
        self,
        labels_dict: Dict[str, tk.Label],
        title_lbl: tk.Label,
        step_keys: Tuple[str, ...],
        len_keys: Tuple[str, str],
        side_idx: int,
        is_all: bool,
        title_dir: str,
        title_arrow: str,
        title_single_fg: str,
        on_bg: str,
        mix_bg: str,
        mix_fg: str,
        off_bg: str,
        off_fg: str,
        on_hb: str,
        single_len_bg: str,
        single_len_fg: str,
    ):
        """Renders Row 2 (Q-P) or Row 3 (A-Ñ) step pads in [F4] Patrón for single or ALL mode."""
        n_balls = len(self.system.pendulums) if hasattr(self, 'system') else 0
        if is_all and n_balls > 0:
            all_side = [self._get_ball_steps(bi)[side_idx] for bi in range(n_balls)]
            lens = {len(s) for s in all_side}
            len_tag = str(next(iter(lens))) if len(lens) == 1 else "var"
            title_lbl.config(
                text=f"[{step_keys[0]}-{step_keys[-1]}] ALL{title_arrow}({len_tag}):",
                fg="#facc15"
            )
            for key_id, lbl in labels_dict.items():
                if key_id in step_keys:
                    s_i = step_keys.index(key_id)
                    vals = [s[s_i] for s in all_side if s_i < len(s)]
                    if not vals:
                        sym, bg_c, fg_c, rel_c, hb_c = "·", "#141722", "#334155", tk.FLAT, "#13161f"
                    elif len(vals) == n_balls and all(is_hit(v) for v in vals):
                        sym, bg_c, fg_c, rel_c, hb_c = "x", on_bg, "#ffffff", tk.SUNKEN, "#facc15"
                    elif len(vals) == n_balls and all(is_tie(v) for v in vals):
                        sym, bg_c, fg_c, rel_c, hb_c = "~", "#78350f", "#fde047", tk.GROOVE, "#facc15"
                    elif len(vals) == n_balls and all(v == STEP_REST for v in vals):
                        sym, bg_c, fg_c, rel_c, hb_c = "-", off_bg, off_fg, tk.RAISED, "#13161f"
                    else:
                        sym, bg_c, fg_c, rel_c, hb_c = "*", mix_bg, mix_fg, tk.RAISED, "#f59e0b"
                    lbl.config(
                        text=f"[{key_id}] {s_i+1}:{sym}",
                        bg=bg_c,
                        fg=fg_c,
                        relief=rel_c,
                        highlightbackground=hb_c,
                        cursor="hand2"
                    )
                elif key_id in len_keys:
                    delta_txt = "-1" if key_id == len_keys[0] else "+1"
                    lbl.config(
                        text=f"[{key_id}] {delta_txt}",
                        bg="#3b2608",
                        fg="#fde047",
                        relief=tk.RAISED,
                        highlightbackground="#13161f",
                        cursor="hand2"
                    )
            return

        b = self.selected_ball_idx
        steps = self._get_ball_steps(b)[side_idx]
        s_len = len(steps)
        title_lbl.config(
            text=f"[{step_keys[0]}-{step_keys[-1]}] B{b+1} {title_dir} ({s_len}):",
            fg=title_single_fg
        )
        for key_id, lbl in labels_dict.items():
            if key_id in step_keys:
                s_i = step_keys.index(key_id)
                in_bounds = (s_i < s_len)
                st = steps[s_i] if in_bounds else STEP_REST
                if not in_bounds:
                    sym, bg_c, fg_c, rel_c, hb_c = "·", "#141722", "#334155", tk.FLAT, "#13161f"
                elif is_hit(st):
                    sym, bg_c, fg_c, rel_c, hb_c = "x", on_bg, "#ffffff", tk.SUNKEN, on_hb
                elif is_tie(st):
                    sym, bg_c, fg_c, rel_c, hb_c = "~", "#78350f", "#fde047", tk.GROOVE, "#facc15"
                else:
                    sym, bg_c, fg_c, rel_c, hb_c = "-", off_bg, off_fg, tk.RAISED, "#13161f"
                lbl.config(
                    text=f"[{key_id}] {s_i+1}:{sym}",
                    bg=bg_c,
                    fg=fg_c,
                    relief=rel_c,
                    highlightbackground=hb_c,
                    cursor="hand2"
                )
            elif key_id in len_keys:
                delta_txt = "-1" if key_id == len_keys[0] else "+1"
                lbl.config(
                    text=f"[{key_id}] {delta_txt}",
                    bg=single_len_bg,
                    fg=single_len_fg,
                    relief=tk.RAISED,
                    highlightbackground="#13161f",
                    cursor="hand2"
                )

    def _update_piano_keyboard_labels(self):
        if not hasattr(self, 'pitch_follow'):
            return
        self._update_mode_buttons()
        self._update_kb_sound_controls()

        mode = self.keyboard_mode
        third = get_third_semitones(self.pitch_follow.third_mode, self.harmony_type_var.get())
        if mode == "normal":
            exact_red, red_pcs, sounding_exact = self._get_keyboard_red_pitches()
            self._last_piano_red_state = (frozenset(exact_red), frozenset(red_pcs), frozenset(sounding_exact))
        else:
            exact_red, red_pcs, sounding_exact = set(), set(), set()

        # --- Row 2 [Q-P] ---
        if hasattr(self, 'qp_labels') and hasattr(self, 'lbl_qp_title'):
            if mode == "normal":
                self.lbl_qp_title.config(text="[Q-P] Negras (#):", fg="#c084fc")
                active_key = self.pitch_follow.key_for_midi(self.pitch_follow.active_midi)
                pending_key = self.pitch_follow.key_for_midi(self.pitch_follow.pending_midi)
                held_set = set(self.pitch_follow.held_piano_keys)
                for key_id, lbl in self.qp_labels.items():
                    if key_id not in PIANO_NOTE_OFFSETS:
                        lbl.config(text="", bg="#13161f", fg="#334155", relief=tk.FLAT, highlightbackground="#13161f", cursor="")
                        continue
                    midi_val = self.pitch_follow.midi_for_key(key_id)
                    note_str = midi_to_note_name(midi_val) if midi_val is not None else ""
                    txt = f"[{key_id}] {note_str}".strip()
                    self._style_piano_key_label(
                        lbl,
                        txt,
                        midi_val,
                        is_black=True,
                        is_active=(key_id == active_key),
                        is_pending=(key_id == pending_key),
                        is_held=(key_id in held_set),
                        exact_red=exact_red,
                        red_pcs=red_pcs,
                        sounding_exact=sounding_exact,
                    )
            elif mode == "strum_dd":
                self._update_strum_step_row(
                    labels_dict=self.qp_labels,
                    title_lbl=self.lbl_qp_title,
                    step_keys=("Q", "W", "E", "R", "T", "Y", "U", "I"),
                    len_keys=("O", "P"),
                    side_idx=0,
                    is_all=(self.strum_target_mode == "all"),
                    title_dir="◄IDA",
                    title_arrow="◄",
                    title_single_fg="#06b6d4",
                    on_bg="#0891b2",
                    mix_bg="#155e75",
                    mix_fg="#fde047",
                    off_bg="#1a2436",
                    off_fg="#67e8f9",
                    on_hb="#06b6d4",
                    single_len_bg="#1e293b",
                    single_len_fg="#38bdf8",
                )
            elif mode == "accel_ff":
                self.lbl_qp_title.config(text="[Q-P] Curva Ratio:", fg="#38bdf8")
                cur_prog = self.strum_progression_var.get()
                qp_accel_map = {
                    "Q": ("1.0", cur_prog == "uniform"),
                    "W": (".85", cur_prog == "rasgueo_soft"),
                    "E": (".72", cur_prog == "rasgueo_guitar"),
                    "R": (".60", cur_prog == "rasgueo_fast"),
                    "T": (".45", cur_prog == "ultra_fast"),
                    "Y": (".30", cur_prog == "hyper_fast"),
                    "U": ("1.5", cur_prog == "arpeggio_decel"),
                    "I": ("1.8", cur_prog == "decel_marked"),
                    "O": ("2.2", cur_prog == "hyper_decel"),
                    "P": ("3.2", cur_prog == "ultra_open"),
                }
                for key_id, lbl in self.qp_labels.items():
                    name, is_act = qp_accel_map.get(key_id, (key_id, False))
                    lbl.config(
                        text=f"[{key_id}] {name}",
                        bg="#0284c7" if is_act else "#0c4a6e",
                        fg="#ffffff" if is_act else "#7dd3fc",
                        relief=tk.SUNKEN if is_act else tk.RAISED,
                        highlightbackground="#13161f",
                        cursor="hand2"
                    )
            else:
                self.lbl_qp_title.config(text="[Q-P] (Inactivo):", fg="#475569")
                for key_id, lbl in self.qp_labels.items():
                    lbl.config(text=f"[{key_id}]", bg="#161922", fg="#334155", relief=tk.FLAT, highlightbackground="#13161f", cursor="")

        # --- Row 3 [A-Ñ] ---
        if hasattr(self, 'al_labels') and hasattr(self, 'lbl_al_title'):
            if mode == "chords_aa":
                self.lbl_al_title.config(text="🎵 [ACORDES AA]:", fg="#f43f5e")
                chord_name = get_degree_chord_name(
                    self.root_key_var.get(),
                    self.harmony_type_var.get(),
                    self.active_chord_degree,
                    self.active_chord_seventh
                )
                inv_tag = f" [Inv{self.active_chord_inversion}]" if self.active_chord_inversion > 0 else ""
                if hasattr(self, 'lbl_al_hint'):
                    self.lbl_al_hint.config(
                        text=f"🎹 {chord_name}{inv_tag} • [ESC/F1]=Piano",
                        fg="#fb7185"
                    )
                degree_labels = {"A": "I", "S": "II", "D": "III", "F": "IV", "G": "V", "H": "VI", "J": "VII"}
                degree_map = {"A": 0, "S": 1, "D": 2, "F": 3, "G": 4, "H": 5, "J": 6}
                for key_id, lbl in self.al_labels.items():
                    if key_id in degree_labels:
                        is_act = (degree_map[key_id] == self.active_chord_degree)
                        lbl.config(
                            text=f"[{key_id}] {degree_labels[key_id]}",
                            bg="#e11d48" if is_act else "#3b1d54",
                            fg="#ffffff" if is_act else "#e9d5ff",
                            relief=tk.SUNKEN if is_act else tk.RAISED,
                            highlightbackground="#13161f",
                            cursor="hand2"
                        )
                    elif key_id == "K":
                        lbl.config(
                            text=f"[K] Iv{self.active_chord_inversion}",
                            bg="#4a154b" if self.active_chord_inversion > 0 else "#2a1f3d",
                            fg="#f472b6",
                            relief=tk.SUNKEN if self.active_chord_inversion > 0 else tk.RAISED,
                            highlightbackground="#13161f",
                            cursor="hand2"
                        )
                    elif key_id == "L":
                        lbl.config(
                            text="[L] 7ª✓" if self.active_chord_seventh else "[L] 7ª",
                            bg="#4a154b" if self.active_chord_seventh else "#2a1f3d",
                            fg="#38bdf8" if self.active_chord_seventh else "#94a3b8",
                            relief=tk.SUNKEN if self.active_chord_seventh else tk.RAISED,
                            highlightbackground="#13161f",
                            cursor="hand2"
                        )
                    else:
                        lbl.config(text="", bg="#13161f", fg="#334155", relief=tk.FLAT, highlightbackground="#13161f", cursor="")
            elif mode == "accent_ss":
                self.lbl_al_title.config(text="⚡ [ACENTOS SS]:", fg="#fbbf24")
                active_n = len(self._get_active_ball_indices())
                cur_dyn = self.dynamic_mode_var.get()
                dyn_short = DYNAMIC_MODES.get(cur_dyn, {}).get('short', cur_dyn)
                if hasattr(self, 'lbl_al_hint'):
                    self.lbl_al_hint.config(
                        text=f"💥 {dyn_short} ({active_n} bolas) • [ESC/F1]=Piano",
                        fg="#fde047"
                    )
                accent_configs = {
                    "A": ("Suv", "delicado", "#1e3a5f", "#93c5fd"),
                    "S": ("For", "forte", "#991b1b", "#fecaca"),
                    "D": ("Mar", "marcato", "#7c2d12", "#fdba74"),
                    "F": ("Sín", "sincopa", "#701a75", "#f5d0fe"),
                    "G": ("Cre", "crescendo", "#065f46", "#a7f3d0"),
                    "H": ("Dec", "decrescendo", "#1e293b", "#cbd5e1"),
                    "J": ("Gho", "ghost_notes", "#312e81", "#c7d2fe"),
                    "K": ("+Sn", "", "#854d0e", "#fef08a"),
                    "L": ("-Sn", "", "#3f3f46", "#e4e4e7"),
                }
                for key_id, lbl in self.al_labels.items():
                    if key_id not in accent_configs:
                        lbl.config(text="", bg="#13161f", fg="#334155", relief=tk.FLAT, highlightbackground="#13161f", cursor="")
                        continue
                    name, mode_key, def_bg, def_fg = accent_configs[key_id]
                    is_act = bool(mode_key and cur_dyn == mode_key)
                    lbl.config(
                        text=f"[{key_id}] {name}",
                        bg="#f59e0b" if is_act else def_bg,
                        fg="#000000" if is_act else def_fg,
                        relief=tk.SUNKEN if is_act else tk.RAISED,
                        highlightbackground="#13161f",
                        cursor="hand2"
                    )
            elif mode == "strum_dd":
                is_all = (self.strum_target_mode == "all")
                self._update_strum_step_row(
                    labels_dict=self.al_labels,
                    title_lbl=self.lbl_al_title,
                    step_keys=("A", "S", "D", "F", "G", "H", "J", "K"),
                    len_keys=("L", "Ñ"),
                    side_idx=1,
                    is_all=is_all,
                    title_dir="►VTA",
                    title_arrow="►",
                    title_single_fg="#f97316",
                    on_bg="#ea580c",
                    mix_bg="#7c2d12",
                    mix_fg="#fde047",
                    off_bg="#261e26",
                    off_fg="#fdba74",
                    on_hb="#f97316",
                    single_len_bg="#292028",
                    single_len_fg="#fb923c",
                )
                if hasattr(self, 'lbl_al_hint'):
                    if is_all:
                        n_balls = len(self.system.pendulums) if hasattr(self, 'system') else 0
                        self.lbl_al_hint.config(
                            text=f"🌐 TODAS ({n_balls} bolas) • [0]=Bola • [1-9]=Elegir • [ESC]",
                            fg="#fde047"
                        )
                    else:
                        b = self.selected_ball_idx
                        cur_left, cur_right = self._get_ball_steps(b)
                        self.lbl_al_hint.config(
                            text=f"◄{format_pattern(cur_left)} │ ►{format_pattern(cur_right)} • [0]=TODAS [ESC]",
                            fg="#fdba74"
                        )
            elif mode == "accel_ff":
                self.lbl_al_title.config(text="🌪 [EVOLUCIÓN FF]:", fg="#38bdf8")
                cur_evol = getattr(self, 'strum_evolving_mode', 'off')
                cur_spd = getattr(self, 'strum_speed_factor', 1.0)
                cur_prog = self.strum_progression_var.get()
                cur_prog_short = STRUM_PROGRESSIONS.get(cur_prog, {}).get('short', cur_prog)
                if hasattr(self, 'lbl_al_hint'):
                    self.lbl_al_hint.config(
                        text=f"⚡ {cur_prog_short} • {cur_spd:g}x • {cur_evol} • [F1]",
                        fg="#7dd3fc"
                    )
                accel_al_configs = {
                    "A": ("Est", "off", "#1e293b", "#94a3b8"),
                    "S": ("Ac↗", "accel", "#065f46", "#6ee7b7"),
                    "D": ("Fr↘", "decel", "#7c2d12", "#fdba74"),
                    "F": ("Rs∿", "breathe", "#4c1d95", "#c084fc"),
                    "G": ("Al⇄", "altern", "#0284c7", "#7dd3fc"),
                    "H": ("Cao", "chaos", "#854d0e", "#fde047"),
                    "J": ("On⋀", "wave", "#1e3a8a", "#93c5fd"),
                    "K": ("Pr⇅", "pairs_alt", "#701a75", "#f472b6"),
                    "L": ("Rt↺", "retro_flip", "#831843", "#fb7185"),
                }
                for key_id, lbl in self.al_labels.items():
                    if key_id not in accel_al_configs:
                        lbl.config(text="", bg="#13161f", fg="#334155", relief=tk.FLAT, highlightbackground="#13161f", cursor="")
                        continue
                    name, mode_id, def_bg, def_fg = accel_al_configs[key_id]
                    is_act = (cur_evol == mode_id)
                    lbl.config(
                        text=f"[{key_id}] {name}",
                        bg="#0284c7" if is_act else def_bg,
                        fg="#ffffff" if is_act else def_fg,
                        relief=tk.SUNKEN if is_act else tk.RAISED,
                        highlightbackground="#13161f",
                        cursor="hand2"
                    )
            else:
                self.lbl_al_title.config(text="[A-Ñ] Blancas:", fg="#34d399")
                active_key = self.pitch_follow.key_for_midi(self.pitch_follow.active_midi)
                pending_key = self.pitch_follow.key_for_midi(self.pitch_follow.pending_midi)
                held_set = set(self.pitch_follow.held_piano_keys)
                for key_id, lbl in self.al_labels.items():
                    midi_val = self.pitch_follow.midi_for_key(key_id)
                    note_str = midi_to_note_name(midi_val) if midi_val is not None else ""
                    txt = f"[{key_id}] {note_str}".strip()
                    self._style_piano_key_label(
                        lbl,
                        txt,
                        midi_val,
                        is_black=False,
                        is_active=(key_id == active_key),
                        is_pending=(key_id == pending_key),
                        is_held=(key_id in held_set),
                        exact_red=exact_red,
                        red_pcs=red_pcs,
                        sounding_exact=sounding_exact,
                    )
                if hasattr(self, 'lbl_al_hint'):
                    s_mode = self.keyboard_sound_mode_var.get()
                    custom_inst = self.kb_timbre_var.get().strip() if hasattr(self, 'kb_timbre_var') else ""
                    oct_v = int(self.kb_octave_offset_var.get()) if hasattr(self, 'kb_octave_offset_var') else 0
                    oct_s = f" {oct_v:+d}oct" if oct_v != 0 else ""
                    is_linked = self.kb_link_accompaniment_var.get() if hasattr(self, 'kb_link_accompaniment_var') else True
                    if not is_linked:
                        inst_lbl = custom_inst or self.timbre_var.get()
                        hint_txt = f"🎹 Solista [{inst_lbl}{oct_s}]" if s_mode != "silent" else "🎹 Solista (Silencio)"
                        hint_fg = "#64748b" if s_mode == "silent" else "#38bdf8"
                    else:
                        hint_map = {
                            "hold": "🎯 Tono + Sonido (Hold)",
                            "staccato": "🎯 Tono + Clic Corto",
                            "short_only": "🎯 Tono + Clic <250ms",
                            "silent": "🎯 Solo Tono (Sin nota)",
                        }
                        hint_txt = hint_map.get(s_mode, "🎯 Tono + Sonido")
                        if (custom_inst or oct_v != 0) and s_mode != "silent":
                            inst_lbl = custom_inst or self.timbre_var.get()
                            hint_txt += f" [{inst_lbl}{oct_s}]"
                        hint_fg = "#64748b" if s_mode == "silent" else "#059669"
                    self.lbl_al_hint.config(text=hint_txt, fg=hint_fg)

        # --- Row 4 [Z-.] ---
        if hasattr(self, 'zm_labels') and hasattr(self, 'lbl_zm_title'):
            if mode == "strum_dd":
                is_all = (self.strum_target_mode == "all")
                if is_all:
                    self.lbl_zm_title.config(text="[Z-.] ALL Ritmo:", fg="#facc15")
                    zm_strum = {
                        "Z": "<<", "X": ">>", "C": "Inv", "V": "I→V",
                        "B": "⇄", "N": "Euc", "M": "Rnd", ",": "xxx", ".": "1+1",
                    }
                    zm_bg, zm_fg = "#451a03", "#fde047"
                else:
                    self.lbl_zm_title.config(text="[Z-.] Ritmo:", fg="#14b8a6")
                    zm_strum = {
                        "Z": "<<", "X": ">>", "C": "Inv", "V": "I→V",
                        "B": "⇄", "N": "Euc", "M": "Rnd", ",": "All", ".": "1+1",
                    }
                    zm_bg, zm_fg = "#132e2b", "#5eead4"
                for key_id, lbl in self.zm_labels.items():
                    lbl.config(
                        text=f"[{key_id}] {zm_strum.get(key_id, key_id)}",
                        bg=zm_bg,
                        fg=zm_fg,
                        relief=tk.RAISED,
                        cursor="hand2"
                    )
                if hasattr(self, 'btn_third_mode'):
                    self.btn_third_mode.config(state=tk.DISABLED)
                if hasattr(self, 'lbl_transpose_status'):
                    if is_all:
                        n_balls = len(self.system.pendulums) if hasattr(self, 'system') else 0
                        self.lbl_transpose_status.config(text=f"🌐 ALL ({n_balls}b)")
                    else:
                        b = self.selected_ball_idx
                        cl, cr = self._get_ball_steps(b)
                        self.lbl_transpose_status.config(text=f"B{b+1}: {len(cl)}│{len(cr)}p")
            elif mode == "accel_ff":
                self.lbl_zm_title.config(text="[Z-M] Vel. Span:", fg="#38bdf8")
                cur_spd = round(getattr(self, 'strum_speed_factor', 1.0), 1)
                zm_accel = {
                    "Z": (".3x", cur_spd == 0.3),
                    "X": (".5x", cur_spd == 0.5),
                    "C": (".8x", cur_spd == 0.8),
                    "V": ("1.0x", cur_spd == 1.0),
                    "B": ("1.6x", cur_spd == 1.6),
                    "N": ("2.5x", cur_spd == 2.5),
                    "M": ("3.5x", cur_spd == 3.5),
                }
                for key_id, lbl in self.zm_labels.items():
                    if key_id in zm_accel:
                        name, is_act = zm_accel[key_id]
                        lbl.config(
                            text=f"[{key_id}] {name}",
                            bg="#0284c7" if is_act else "#0c4a6e",
                            fg="#ffffff" if is_act else "#7dd3fc",
                            relief=tk.SUNKEN if is_act else tk.RAISED,
                            cursor="hand2"
                        )
                    else:
                        lbl.config(text="", bg="#13161f", fg="#334155", relief=tk.FLAT, cursor="")
                if hasattr(self, 'btn_third_mode'):
                    self.btn_third_mode.config(state=tk.DISABLED)
                if hasattr(self, 'lbl_transpose_status'):
                    self.lbl_transpose_status.config(text=f"Span: {cur_spd:g}x")
            else:
                self.lbl_zm_title.config(text="[Z-.] Transponer:", fg="#14b8a6")
                zm_defs = {
                    "Z": "-1st",
                    "X": "+1st",
                    "C": f"-3ª({third})",
                    "V": f"+3ª({third})",
                    "B": "-5ª",
                    "N": "+5ª",
                    "M": "-8ª",
                    ",": "+8ª",
                    ".": "Reset",
                }
                for key_id, lbl in self.zm_labels.items():
                    lbl.config(
                        text=f"[{key_id}] {zm_defs.get(key_id, key_id)}",
                        bg="#132e2b",
                        fg="#5eead4",
                        relief=tk.RAISED,
                        cursor="hand2"
                    )
                if hasattr(self, 'btn_third_mode'):
                    t_mode = self.pitch_follow.third_mode
                    t_short = THIRD_INTERVAL_MODES.get(t_mode, {}).get("short", "Auto")
                    self.btn_third_mode.config(state=tk.NORMAL, text=f"3ª: {t_short} ({third}st)")
                self._update_follow_indicator()

    def _update_keyboard_labels(self):
        self._update_num_labels()
        self._update_piano_keyboard_labels()

    def _flash_key_ui(self, key_char: str, row_type: str = "num"):
        self.pressed_keys_ui[key_char] = (time.time() + 0.16, row_type)
        if row_type == "num" and key_char in self.num_labels:
            self.num_labels[key_char].config(bg="#00f5d4", fg="#000000")
        elif row_type == "qp" and key_char in self.qp_labels:
            self.qp_labels[key_char].config(bg="#facc15", fg="#000000")
        elif row_type == "al" and key_char in self.al_labels:
            if self.keyboard_mode == "chords_aa":
                self.al_labels[key_char].config(bg="#f43f5e", fg="#ffffff")
            elif self.keyboard_mode == "accent_ss":
                self.al_labels[key_char].config(bg="#fbbf24", fg="#000000")
            elif self.keyboard_mode == "strum_dd":
                self.al_labels[key_char].config(bg="#f97316", fg="#ffffff")
            elif self.keyboard_mode == "accel_ff":
                self.al_labels[key_char].config(bg="#38bdf8", fg="#000000")
            else:
                self.al_labels[key_char].config(bg="#34d399", fg="#000000")
        elif row_type == "zm" and key_char in self.zm_labels:
            self.zm_labels[key_char].config(bg="#14b8a6", fg="#000000")
        elif row_type == "piano" and hasattr(self, 'piano_key_labels') and key_char in self.piano_key_labels:
            self.piano_key_labels[key_char].config(bg="#38bdf8", fg="#000000")

    def _choose_backing_track(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar pista de acompañamiento (WAV o MP3)",
            filetypes=[
                ("Archivos de audio", "*.wav;*.mp3;*.ogg;*.flac"),
                ("WAV Audio (*.wav)", "*.wav"),
                ("MP3 Audio (*.mp3)", "*.mp3"),
                ("Todos los archivos", "*.*")
            ]
        )
        if not filepath:
            return
        if isinstance(filepath, (list, tuple)):
            filepath = filepath[0]
        self._load_backing_track(str(filepath))

    def _create_master_volume_group(
        self,
        parent: tk.Widget,
        label_text: str,
        label_fg: str,
        init_text: str,
        val_fg: str,
        adjust_fn,
        cycle_fn,
        right_pad: int = 8,
    ) -> tk.Label:
        """Builds a compact master volume control block (Label + ◀ + % + ▶ + wheel)."""
        tk.Label(
            parent,
            text=label_text,
            font=("Segoe UI", 8, "bold"),
            fg=label_fg,
            bg="#111624"
        ).pack(side=tk.LEFT, padx=(0, 3))

        btn_dn = tk.Button(
            parent,
            text="◀",
            font=("Segoe UI", 7, "bold"),
            bg="#252b3b",
            fg="#cad3f5",
            relief=tk.FLAT,
            padx=3,
            pady=1,
            cursor="hand2",
            command=lambda fn=adjust_fn: fn(-0.1)
        )
        btn_dn.pack(side=tk.LEFT, padx=1)

        lbl_val = tk.Label(
            parent,
            text=init_text,
            font=("Segoe UI", 8, "bold"),
            fg=val_fg,
            bg="#1b2333",
            width=4,
            relief=tk.FLAT,
            cursor="hand2"
        )
        lbl_val.pack(side=tk.LEFT, padx=1)
        lbl_val.bind("<Button-1>", lambda e, fn=cycle_fn: fn())

        btn_up = tk.Button(
            parent,
            text="▶",
            font=("Segoe UI", 7, "bold"),
            bg="#252b3b",
            fg="#cad3f5",
            relief=tk.FLAT,
            padx=3,
            pady=1,
            cursor="hand2",
            command=lambda fn=adjust_fn: fn(+0.1)
        )
        btn_up.pack(side=tk.LEFT, padx=(1, right_pad))

        for w in (lbl_val, btn_dn, btn_up):
            w.bind("<MouseWheel>", lambda e, fn=adjust_fn: fn(0.1 if e.delta > 0 else -0.1))

        return lbl_val

    def _load_backing_track(self, filepath: str):
        success = self.audio_engine.backing_mgr.load(filepath)
        if success:
            self.backing_track_path = filepath
            self.backing_manually_paused = False
            self._backing_paused_by_space = False
            dur = self.audio_engine.backing_mgr.duration
            mins = int(dur // 60)
            secs = int(dur % 60)
            base_name = os.path.basename(filepath)
            display_title = (base_name[:14] + '...') if len(base_name) > 16 else base_name
            self.backing_track_name_var.set(f"🎵 {display_title} ({mins}:{secs:02d})")
            self.lbl_backing_name.config(fg="#38bdf8", font=("Segoe UI", 8, "bold"))
            self.btn_import_backing.config(text="📁 Cambiar", bg="#0369a1")
            self.btn_backing_remove.config(state=tk.NORMAL, fg="#f87171")
            if self.is_live_active and not (self.space_silence_active and self.space_stops_backing_var.get()):
                self.audio_engine.backing_mgr.play(loop=self.backing_loop_var.get())
            self._update_backing_controls()
            self.root.update_idletasks()
            self.canvas.focus_set()
        else:
            messagebox.showwarning("Error al cargar pista", f"No se pudo cargar el archivo:\n{filepath}\nAsegúrate de que sea un archivo WAV o MP3 válido.")

    def _resume_backing_track(self):
        if not hasattr(self, 'audio_engine'):
            return
        mgr = self.audio_engine.backing_mgr
        if not mgr.is_loaded or mgr.is_playing:
            return
        mgr.loop = self.backing_loop_var.get()
        if getattr(mgr, 'accumulated_pos', 0.0) > 0.0:
            mgr.unpause()
        else:
            mgr.play(loop=mgr.loop)

    def _toggle_backing_play(self):
        if not hasattr(self, 'audio_engine') or not self.audio_engine.backing_mgr.is_loaded:
            return
        mgr = self.audio_engine.backing_mgr
        if mgr.is_playing:
            mgr.pause()
            self.backing_manually_paused = True
            self._backing_paused_by_space = False
        else:
            self._resume_backing_track()
            self.backing_manually_paused = False
            self._backing_paused_by_space = False
        self._update_backing_controls()
        self.canvas.focus_set()

    def _toggle_space_stops_backing(self):
        self.space_stops_backing_var.set(not self.space_stops_backing_var.get())
        self._update_backing_controls()
        self.canvas.focus_set()

    def _update_backing_controls(self):
        if hasattr(self, 'btn_space_stops_backing'):
            stops_b = bool(self.space_stops_backing_var.get())
            self.btn_space_stops_backing.config(
                text="Esp→Pista: SÍ" if stops_b else "Esp→Pista: NO",
                bg="#9a3412" if stops_b else "#1e293b",
                fg="#fed7aa" if stops_b else "#94a3b8",
            )
        if not hasattr(self, 'audio_engine'):
            return
        mgr = self.audio_engine.backing_mgr
        if hasattr(self, 'btn_backing_play'):
            if not mgr.is_loaded:
                self.btn_backing_play.config(
                    text="▶ Pista",
                    bg="#1e293b",
                    fg="#64748b",
                    state=tk.DISABLED,
                )
            elif mgr.is_playing:
                self.btn_backing_play.config(
                    text="⏸ Pista",
                    bg="#0284c7",
                    fg="#ffffff",
                    state=tk.NORMAL,
                )
            else:
                self.btn_backing_play.config(
                    text="▶ Pista",
                    bg="#065f46",
                    fg="#6ee7b7",
                    state=tk.NORMAL,
                )
        if hasattr(self, 'lbl_backing_status'):
            if not mgr.is_loaded:
                self.lbl_backing_status.config(text="● Sin pista", fg="#64748b")
            elif mgr.is_playing:
                self.lbl_backing_status.config(text="▶ Sonando", fg="#34d399")
            else:
                self.lbl_backing_status.config(text="⏸ Pausada", fg="#f59e0b")

    def _toggle_backing_loop(self):
        new_loop = not self.backing_loop_var.get()
        self.backing_loop_var.set(new_loop)
        self.audio_engine.backing_mgr.loop = new_loop
        if new_loop:
            self.btn_backing_loop.config(text="🔁 Loop: SÍ", bg="#065f46", fg="#6ee7b7")
        else:
            self.btn_backing_loop.config(text="➡ Loop: NO", bg="#1e293b", fg="#94a3b8")
        self.canvas.focus_set()

    def _set_master_volume_ui(
        self,
        var: tk.DoubleVar,
        setter,
        label: tk.Label,
        new_vol: float,
        active_fg: str,
    ):
        """Clamps, applies, and displays a master volume level [0.0..1.0]."""
        clamped = max(0.0, min(1.0, round(float(new_vol), 2)))
        var.set(clamped)
        setter(clamped)
        pct = int(round(clamped * 100))
        label.config(text=f"{pct}%", fg="#ef4444" if pct == 0 else active_fg)
        self.canvas.focus_set()

    def _cycle_master_volume(
        self,
        var: tk.DoubleVar,
        setter,
        label: tk.Label,
        active_fg: str,
        fallback_vol: float,
    ):
        """Cycles a master volume through 20% steps from 100% down to 0%."""
        vols = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
        cur = round(var.get(), 1)
        try:
            idx = vols.index(cur)
            next_vol = vols[(idx + 1) % len(vols)]
        except ValueError:
            next_vol = fallback_vol
        self._set_master_volume_ui(var, setter, label, next_vol, active_fg)

    def _adjust_backing_volume(self, delta: float):
        self._set_master_volume_ui(
            self.backing_volume_var,
            self.audio_engine.backing_mgr.set_volume,
            self.lbl_backing_vol,
            round(self.backing_volume_var.get(), 2) + delta,
            "#00f5d4",
        )

    def _cycle_backing_volume(self):
        self._cycle_master_volume(
            self.backing_volume_var,
            self.audio_engine.backing_mgr.set_volume,
            self.lbl_backing_vol,
            "#00f5d4",
            0.8,
        )

    def _adjust_synth_volume(self, delta: float):
        self._set_master_volume_ui(
            self.synth_volume_var,
            self.audio_engine.set_master_volume,
            self.lbl_synth_vol,
            round(self.synth_volume_var.get(), 2) + delta,
            "#ffd166",
        )

    def _cycle_synth_volume(self):
        self._cycle_master_volume(
            self.synth_volume_var,
            self.audio_engine.set_master_volume,
            self.lbl_synth_vol,
            "#ffd166",
            1.0,
        )

    def _remove_backing_track(self):
        self.audio_engine.backing_mgr.unload()
        self.backing_track_path = None
        self.backing_manually_paused = False
        self._backing_paused_by_space = False
        self.backing_track_name_var.set("(Sin pista)")
        self.lbl_backing_name.config(fg="#64748b", font=("Segoe UI", 8, "italic"))
        self.btn_import_backing.config(text="📁 Importar", bg="#0284c7")
        self.btn_backing_remove.config(state=tk.DISABLED, fg="#94a3b8")
        self._update_backing_controls()
        self.root.update_idletasks()
        self.canvas.focus_set()

    def _toggle_live_recording(self):
        if not self.is_recording:
            if getattr(self, '_rec_finish_after_id', None):
                try:
                    self.root.after_cancel(self._rec_finish_after_id)
                except Exception:
                    pass
                self._rec_finish_after_id = None
            self.is_finishing_recording = False
            self._rec_stop_offset_sec = None
            self.is_recording = True
            # Iniciar reproducción si estaba en pausa para que suene la pista y el péndulo
            if self.space_silence_active:
                self._end_space_silence(early_cancel=True)
            if not self.is_live_active:
                self._toggle_pause()
            elif (
                hasattr(self, 'audio_engine')
                and self.audio_engine.backing_mgr.is_loaded
                and not self.audio_engine.backing_mgr.is_playing
                and not self.backing_manually_paused
            ):
                self._resume_backing_track()
            self._update_backing_controls()

            self.audio_engine.recorder.start(
                timbre=self.timbre_var.get(),
                bpm=float(self.bpm_var.get()),
                time_signature=self.time_sig_var.get(),
                backing_track_mgr=self.audio_engine.backing_mgr
            )
            self.rec_indicator.config(text="● REC [00:00]", fg="#ef4444")
            self.btn_live_rec.config(
                text="⏹ Stop & Save",
                bg="#ffffff",
                fg="#dc2626"
            )
        elif not getattr(self, 'is_finishing_recording', False):
            # Parada musical: pausar nuevos cruces/pista sin cortar las notas que siguen sonando hasta que acaben
            self._rec_stop_wall_time = time.time()
            self._rec_stop_offset_sec = self.audio_engine.recorder.elapsed_seconds()
            self.is_finishing_recording = True
            self._hard_pause_for_recording_stop()
            self.rec_indicator.config(text="● FIN...", fg="#f59e0b")
            self.btn_live_rec.config(
                text="⏹ Guardar ya",
                bg="#f59e0b",
                fg="#000000"
            )
            if getattr(self, '_rec_finish_after_id', None):
                try:
                    self.root.after_cancel(self._rec_finish_after_id)
                except Exception:
                    pass
            self._rec_finish_after_id = self.root.after(100, self._poll_finish_live_recording)
        else:
            self._finalize_live_recording()

    def _poll_finish_live_recording(self):
        self._rec_finish_after_id = None
        if not getattr(self, 'is_finishing_recording', False):
            return
        still_ringing = (
            bool(getattr(self, 'pending_strum_after_ids', []))
            or bool(getattr(self, 'follow_key_voices', {}))
            or self.audio_engine.has_active_notes()
        )
        timed_out = (time.time() - getattr(self, '_rec_stop_wall_time', time.time())) >= 8.0
        if still_ringing and not timed_out:
            self._rec_finish_after_id = self.root.after(100, self._poll_finish_live_recording)
            return
        self._finalize_live_recording()

    def _finalize_live_recording(self):
        if getattr(self, '_rec_finish_after_id', None):
            try:
                self.root.after_cancel(self._rec_finish_after_id)
            except Exception:
                pass
            self._rec_finish_after_id = None
        self.is_finishing_recording = False
        self.is_recording = False
        stop_offset = self._rec_stop_offset_sec
        self._rec_stop_offset_sec = None
        rec_snapshot = self.audio_engine.recorder.prepare_stop(stop_time_sec=stop_offset)
        if not rec_snapshot:
            self.rec_indicator.config(text="● OFF", fg="#64748b")
            self.btn_live_rec.config(text="🔴 Rec", bg="#ef4444", fg="#ffffff")
            return
        self.rec_indicator.config(text="● MEZCLA...", fg="#f59e0b")
        self.btn_live_rec.config(text="🔴 Rec", bg="#ef4444", fg="#ffffff")
        self.root.update()

        save_state: Dict[str, Any] = {"done": False, "results": None}

        def save_session_thread():
            try:
                save_state["results"] = self.audio_engine.recorder.stop_and_save(
                    base_folder="exports",
                    snapshot=rec_snapshot,
                )
            finally:
                save_state["done"] = True

        def poll_save_done():
            if not save_state["done"]:
                try:
                    self._rec_save_poll_after_id = self.root.after(30, poll_save_done)
                except Exception:
                    pass
                return
            self._rec_save_poll_after_id = None
            results = save_state["results"]
            self.rec_indicator.config(text="● OFF", fg="#64748b")
            if results:
                backing_line = ""
                if results.get('has_backing'):
                    backing_line = f"Pista de fondo: {results.get('backing_name')} (Mezclada en WAV)\n"
                v_min = int(round(results.get('synth_vol_min', 1.0) * 100))
                v_max = int(round(results.get('synth_vol_max', 1.0) * 100))
                vol_range_str = f"{v_min}%" if v_min == v_max else f"{v_min}%–{v_max}%"
                master_line = f"Master Sonido: {vol_range_str}\n"
                msg = (
                    f"¡Sesión en vivo grabada con éxito!\n\n"
                    f"Tonalidad: {self.root_key_var.get()}{self.octave_var.get()}\n"
                    f"Compás: {self.time_sig_var.get()}\n"
                    f"Escala: {HARMONIC_TYPES[self.harmony_type_var.get()]['name']}\n"
                    f"Duración: {results['duration']:.1f}s\n"
                    f"Notas tocadas: {results['events_count']}\n"
                    f"{backing_line}"
                    f"{master_line}"
                    f"WAV Master: {os.path.basename(results['wav'])}\n"
                    f"MIDI: {os.path.basename(results['midi'])}"
                )
                messagebox.showinfo("Grabación en Vivo Guardada", msg)

        threading.Thread(target=save_session_thread, daemon=True).start()
        self._rec_save_poll_after_id = self.root.after(30, poll_save_done)

    def _compute_crossing_playback_params(
        self, i: int, p, moving_right: bool,
        current_beat: int, numerator: int, n: int
    ):
        """Compute strum progression, span factor, sensitivity, velocity, duration, and palette."""
        cross_idx = self.ball_cross_count[i]
        global_ratio = STRUM_PROGRESSIONS.get(self.strum_progression_var.get(), {}).get('ratio', 1.0)
        base_ratio = self.ball_custom_strum_ratio.get(i, global_ratio)
        evolving_mode = getattr(self, 'strum_evolving_mode', 'off')
        speed_factor = getattr(self, 'strum_speed_factor', 1.0)

        if evolving_mode == "accel":
            step_cycle = cross_idx % 4
            span_mults = [1.0, 0.75, 0.55, 0.38]
            ratio_mults = [1.0, 0.80, 0.60, 0.45]
            eff_span = speed_factor * span_mults[step_cycle]
            ratio = max(0.20, base_ratio * ratio_mults[step_cycle])
        elif evolving_mode == "decel":
            step_cycle = cross_idx % 4
            span_mults = [0.45, 0.75, 1.25, 1.85]
            ratio_mults = [0.50, 0.85, 1.45, 2.30]
            eff_span = speed_factor * span_mults[step_cycle]
            ratio = min(3.80, base_ratio * ratio_mults[step_cycle])
        elif evolving_mode == "breathe":
            bpm_val = max(20.0, float(self.bpm_var.get()))
            ts = self.time_sig_var.get()
            num_beats = ts[0] if isinstance(ts, tuple) else 4
            bar_dur = (60.0 / bpm_val) * max(1, num_beats)
            sine_phase = (math.sin(self.anim_time * (2.0 * math.pi / bar_dur)) + 1.0) / 2.0
            eff_span = speed_factor * (0.45 + 1.25 * sine_phase)
            ratio = max(0.22, base_ratio * (0.45 + 1.10 * (1.0 - sine_phase)))
        elif evolving_mode == "altern":
            if moving_right:
                eff_span = speed_factor * 0.50
                ratio = min(base_ratio, 0.45)
            else:
                eff_span = speed_factor * 1.70
                ratio = max(base_ratio, 2.20)
        elif evolving_mode == "chaos":
            seed_val = int((i * 1000 + cross_idx) % 10000)
            pseudo_rand = (math.sin(seed_val) * 43758.5453) % 1.0
            span_jitter = 0.65 + 0.70 * pseudo_rand
            ratio_jitter = 0.70 + 0.60 * (1.0 - pseudo_rand)
            eff_span = speed_factor * span_jitter
            ratio = max(0.20, min(3.50, base_ratio * ratio_jitter))
        elif evolving_mode == "wave":
            bpm_val = max(20.0, float(self.bpm_var.get()))
            ts = self.time_sig_var.get()
            num_beats = ts[0] if isinstance(ts, tuple) else 4
            cycle_dur = (60.0 / bpm_val) * max(1, num_beats) * 8.0
            phase = (self.anim_time % cycle_dur) / max(0.1, cycle_dur)
            tri = 2.0 * phase if phase < 0.5 else 2.0 * (1.0 - phase)
            eff_span = speed_factor * (0.4 + 1.4 * tri)
            ratio = max(0.25, base_ratio * (0.5 + 1.2 * (1.0 - tri)))
        elif evolving_mode == "pairs_alt":
            if i % 2 == 0:
                eff_span = speed_factor * 0.55
                ratio = max(0.25, base_ratio * 0.55)
            else:
                eff_span = speed_factor * 1.60
                ratio = min(3.50, base_ratio * 1.80)
        elif evolving_mode == "retro_flip":
            if moving_right:
                eff_span = speed_factor
                ratio = base_ratio
            else:
                eff_span = speed_factor * 1.30
                ratio = max(0.25, min(3.50, 1.0 / max(0.01, base_ratio)))
        else:
            eff_span = speed_factor
            ratio = base_ratio

        global_sens = STRUM_ACCENT_SENSITIVITIES.get(self.strum_sensitivity_var.get(), {}).get('value', 0.50)
        sens = self.ball_custom_strum_sens.get(i, global_sens)

        voice_norm = i / max(1, n - 1) if n > 1 else 0.5
        base_vel = 88 + int(20 * (1.0 - voice_norm * 0.3))
        dyn_mode = self.ball_custom_dynamics.get(i, self.dynamic_mode_var.get())
        vel = compute_dynamic_velocity(
            dyn_mode,
            current_beat,
            numerator,
            base_velocity=base_vel
        )
        dur_mode = self.ball_custom_durations.get(i, self.duration_mode_var.get())
        dur = compute_note_duration(dur_mode, half_period=p.half_period)
        pal_mode = self.ball_custom_palettes.get(i, self.fill_palette_var.get())
        return ratio, eff_span, sens, vel, dur, pal_mode

    def _emit_chord_voice_sequence(
        self, i: int, p, side_key: str, c_notes: List[int], step_slots: List[int],
        voice_offsets: List[float], vel: int, vel_scale: float,
        apply_strum_vel: bool, sens: float, dur: float,
        base_delay: float = 0.0
    ):
        """Play immediate or scheduled chord voices at a pattern slot and register flashes."""
        n_voices = len(c_notes)
        for v_idx, (c_pt, v_off) in enumerate(zip(c_notes, voice_offsets)):
            step_slot = step_slots[v_idx]
            c_vel = max(25, min(127, int(vel * vel_scale)))
            if apply_strum_vel:
                c_vel = compute_strum_velocity(c_vel, v_idx, n_voices, sens)
            total_ms = int(round((base_delay + v_off) * 1000))
            if total_ms <= 0:
                self.audio_engine.play_note(
                    pitch=c_pt,
                    velocity=c_vel,
                    duration=dur,
                    pan=p.pan,
                    pendulum_index=i
                )
                self._register_sounding_pendulum_pitch(c_pt, dur)
                self.active_flashes[i] = 12
                self._flash_matrix_step(i, side_key, step_slot)
                if hasattr(self, 'pilot_flashes') and i in self.pilot_flashes:
                    if step_slot < len(self.pilot_flashes[i][side_key]):
                        self.pilot_flashes[i][side_key][step_slot] = 12
                    self.pilot_flashes[i]['last_dir'] = side_key
            else:
                aid_holder: List[str] = []

                def _fire_chord_voice(
                    idx=i,
                    pt=c_pt,
                    v=c_vel,
                    d=dur,
                    pn=p.pan,
                    sk=side_key,
                    si=step_slot,
                    a_hold=aid_holder,
                ):
                    aid_self = a_hold[0] if a_hold else None
                    if aid_self and aid_self in self.pending_strum_after_ids:
                        self.pending_strum_after_ids.remove(aid_self)
                    self._trigger_secondary_strike_matrix(
                        idx, pt, v, d, pn, side=sk, strike_idx=si, allow_when_paused=True
                    )

                aid = self.root.after(total_ms, _fire_chord_voice)
                aid_holder.append(aid)
                self.pending_strum_after_ids.append(aid)

    def _animate(self):
        now = time.time()
        dt = now - self.last_wall_time
        self.last_wall_time = now

        if self.is_live_active:
            self.anim_time += dt

            if self.space_silence_active:
                if self.anim_time >= self.space_silence_until:
                    self._end_space_silence(early_cancel=False)
                else:
                    self._update_pause_button()

            # Live refresh of ball silence countdowns
            self._update_num_labels()

            # Drive musical beat clock for quantized Pitch-Follow transitions
            beat_sec = 60.0 / self.system.tempo_bpm
            sig_data = TIME_SIGNATURES.get(self.time_sig_var.get(), TIME_SIGNATURES['4/4'])
            numerator = sig_data['numerator']

            curr_total_beat = int(math.floor(self.anim_time / beat_sec))
            if self.last_total_beat == -1:
                self.last_total_beat = curr_total_beat
            elif curr_total_beat > self.last_total_beat:
                for b_step in range(self.last_total_beat + 1, curr_total_beat + 1):
                    self._on_beat_advance(b_step, numerator, beat_sec)
                self.last_total_beat = curr_total_beat

        if self.is_recording and not getattr(self, 'is_finishing_recording', False):
            elapsed = int(self.audio_engine.recorder.elapsed_seconds())
            mins = elapsed // 60
            secs = elapsed % 60
            dot = "●" if (int(now * 2) % 2 == 0) else "○"
            self.rec_indicator.config(text=f"{dot} REC [{mins:02d}:{secs:02d}]", fg="#ef4444")

        # Refresh flashing keys
        expired_row_types = set()
        for k, (expiry, row_type) in list(self.pressed_keys_ui.items()):
            if now > expiry:
                expired_row_types.add(row_type)
                del self.pressed_keys_ui[k]
        expired_sounding = [
            mp for mp, exp in self.sounding_pendulum_pitches.items() if exp <= now
        ]
        for mp in expired_sounding:
            del self.sounding_pendulum_pitches[mp]
        cur_unmuted = tuple(
            i for i in range(len(self.system.pendulums))
            if not (self.anim_time < self.pendulum_mutes.get(i, 0.0))
        )
        needs_piano_red_refresh = bool(expired_sounding) or (cur_unmuted != self._last_unmuted_balls)
        self._last_unmuted_balls = cur_unmuted

        if "num" in expired_row_types:
            self._update_num_labels()
        if (
            any(rt in expired_row_types for rt in ("zm", "piano", "qp", "al"))
            or (needs_piano_red_refresh and self.keyboard_mode == "normal")
        ):
            self._update_piano_keyboard_labels()

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w > 50 and h > 50:
            self.canvas.delete("all")
            center_x = w / 2.0
            top_y = 35.0
            n = len(self.system.pendulums)
            is_uniform_view = (self.view_mode_var.get() == "uniform")

            # Metronome Beat Indicator
            sig_data = TIME_SIGNATURES.get(self.time_sig_var.get(), TIME_SIGNATURES['4/4'])
            numerator = sig_data['numerator']
            beat_sec = 60.0 / self.system.tempo_bpm
            current_beat = int((self.anim_time / beat_sec) % numerator)

            dots_spacing = 18.0
            dots_start_x = center_x - ((numerator - 1) * dots_spacing) / 2.0
            self.canvas.create_text(
                dots_start_x - 50, 16,
                text=f"COMPÁS {self.time_sig_var.get()}:",
                fill="#64748b", font=("Segoe UI", 8, "bold")
            )
            for b_idx in range(numerator):
                dot_x = dots_start_x + b_idx * dots_spacing
                is_active_beat = (b_idx == current_beat)
                is_downbeat = (b_idx == 0)
                is_last_beat = (b_idx == numerator - 1)

                if is_active_beat:
                    if is_downbeat:
                        dot_color = "#ffd166"
                        r = 4.8
                    elif is_last_beat:
                        dot_color = "#fb7185"  # Rose/coral: Cierre de compás en último beat
                        r = 4.5
                    else:
                        dot_color = "#00f5d4"  # Cyan: Beats internos del compás
                        r = 4.0
                else:
                    dot_color = "#272e3f"
                    r = 2.5

                self.canvas.create_oval(
                    dot_x - r, 16 - r, dot_x + r, 16 + r,
                    fill=dot_color, outline=""
                )

            # Live Follow-Pitch HUD on Canvas
            if hasattr(self, 'pitch_follow'):
                active_note = midi_to_note_name(self.pitch_follow.active_midi)
                pending_midi = self.pitch_follow.pending_midi
                chord_disp = ""
                if (
                    hasattr(self, 'chord_play_mode_var')
                    and self.chord_play_mode_var.get() != "off"
                    and getattr(self, 'active_chord_label', '')
                ):
                    chord_disp = f" ({self.active_chord_label})"
                if pending_midi is not None:
                    pending_note = midi_to_note_name(pending_midi)
                    main_text = f"{active_note}{chord_disp}  →  {pending_note} ⏳"
                    main_color = "#facc15"
                else:
                    main_text = f"{active_note}{chord_disp}"
                    main_color = "#00f5d4"

                hud_top = max(44.0, min(h - 125.0, (h - 80.0) * 0.40))
                card_half_w = min(max(210.0, w * 0.40), w / 2.0 - 16.0)
                has_banner = bool(self.keyboard_mode != "normal" and self.mode_banner_text)
                card_h = 126.0 if has_banner else 104.0
                self.canvas.create_rectangle(
                    center_x - card_half_w, hud_top,
                    center_x + card_half_w, hud_top + card_h,
                    fill="#111622", outline="#1e293b", width=1
                )
                self.canvas.create_text(
                    center_x, hud_top + 26.0,
                    text=main_text,
                    fill=main_color,
                    font=("Segoe UI", 24, "bold")
                )

                harm_name = HARMONIC_TYPES.get(self.harmony_type_var.get(), {}).get("name", "")
                ball_notes = [midi_to_note_name(bp.base_pitch) for bp in self.system.pendulums[:10]]
                balls_str = " • ".join(ball_notes)
                if len(self.system.pendulums) > 10:
                    balls_str += " • …"
                self.canvas.create_text(
                    center_x, hud_top + 58.0,
                    text=f"{harm_name} • Bolas: {balls_str}",
                    fill="#cbd5e1",
                    font=("Segoe UI", 9, "bold")
                )

                low_n, high_n = self.pitch_follow.get_keyboard_range_names()
                offset_str = format_semitone_offset(self.pitch_follow.transpose_semitones)
                trans_name = FOLLOW_TRANSITION_MODES.get(
                    self.pitch_follow.transition_mode, {}
                ).get("name", self.pitch_follow.transition_mode)
                self.canvas.create_text(
                    center_x, hud_top + 82.0,
                    text=f"Teclado: {low_n} → {high_n}  |  Desplaz: {offset_str}  |  Cambio: {trans_name}",
                    fill="#94a3b8",
                    font=("Segoe UI", 8)
                )
                if has_banner:
                    self.canvas.create_text(
                        center_x, hud_top + 106.0,
                        text=self.mode_banner_text,
                        fill="#fbbf24",
                        font=("Segoe UI", 8, "bold")
                    )

            # Physical / Harmonic strike triggering logic (Sound Engine)
            accomp_chord_mode = (
                self.chord_play_mode_var.get()
                if self._is_chord_enabled_for_accompaniment()
                else "off"
            )

            for i, p in enumerate(self.system.pendulums):
                impulse = self.pendulum_impulses.get(i, 0.0)
                if impulse > 0:
                    self.pendulum_impulses[i] = max(0.0, impulse - dt * 0.8)

                max_amplitude_rad = 0.42 + impulse
                angle = p.angle_at(self.anim_time, amplitude=max_amplitude_rad)

                is_positive = (angle >= 0.0)
                was_positive = self.last_cross_states.get(i, is_positive)
                is_muted = (self.anim_time < self.pendulum_mutes.get(i, 0.0))

                if self.is_live_active and (is_positive != was_positive):
                    self.last_cross_states[i] = is_positive
                    moving_right = is_positive
                    side_key = 'right' if moving_right else 'left'
                    self.ball_cross_count[i] = self.ball_cross_count.get(i, 0) + 1

                    if not is_muted:
                        cur_left, cur_right = self._get_ball_steps(i)
                        active_steps = cur_right if moving_right else cur_left
                        next_steps = cur_left if moving_right else cur_right
                        n_steps = len(active_steps)
                        n_active = count_hits(active_steps)

                        if n_active > 0:
                            if hasattr(self, 'pitch_follow'):
                                cross_midi = self.pitch_follow.on_pendulum_crossing(
                                    i, is_primary_ball=(i == 0)
                                )
                                if cross_midi is not None:
                                    self._apply_accompaniment_pitch(cross_midi)

                            ratio, eff_span, sens, vel, dur, pal_mode = (
                                self._compute_crossing_playback_params(
                                    i, p, moving_right, current_beat, numerator, n
                                )
                            )

                            skip_for_ida = False
                            if (
                                self.ball_wait_for_ida.get(i, False)
                                and is_scale_run_palette(pal_mode)
                                and accomp_chord_mode == "off"
                            ):
                                if moving_right and count_hits(cur_left) > 0:
                                    if hasattr(self, 'pilot_flashes') and i in self.pilot_flashes:
                                        self.pilot_flashes[i]['last_dir'] = side_key
                                    skip_for_ida = True
                                else:
                                    self.ball_wait_for_ida[i] = False

                            if skip_for_ida:
                                pass
                            elif (
                                accomp_chord_mode in ("block", "strum")
                                and bool(self.system.chord_pitches)
                                and self.harmony_type_var.get() != 'drum_kit'
                            ):
                                active_indices = [k for k, st in enumerate(active_steps) if is_hit(st)]
                                chord_pool = expand_chord_to_n_voices(
                                    self.system.chord_pitches, n_steps, inversion=i
                                )
                                c_notes = [chord_pool[k] for k in active_indices]
                                step_slots = list(active_indices)
                                n_v = len(c_notes)
                                vel_scale = max(0.68, 0.90 - 0.04 * max(0, n_v - 2)) if n_v >= 2 else 1.0

                                if accomp_chord_mode == "strum" and n_v >= 2:
                                    if not moving_right:
                                        c_notes.reverse()
                                        step_slots.reverse()
                                    strum_span = min(0.18, p.half_period * 0.70, max(0.035, 0.030 * (n_v - 1)))
                                    voice_offsets = compute_strum_delays(n_v, strum_span, ratio)
                                    apply_strum_vel = True
                                else:
                                    voice_offsets = [0.0] * n_v
                                    apply_strum_vel = False

                                self._emit_chord_voice_sequence(
                                    i, p, side_key, c_notes, step_slots,
                                    voice_offsets, vel, vel_scale,
                                    apply_strum_vel, sens, dur,
                                    base_delay=0.0,
                                )
                                self.ball_strike_counts[i] = self.ball_strike_counts.get(i, 0) + n_v
                            else:
                                slot_delays = compute_pattern_slot_delays(
                                    n_steps, p.half_period, ratio=ratio, speed_factor=eff_span
                                )
                                has_any_tie = has_ties(cur_left) or has_ties(cur_right)
                                dur_mode = self.ball_custom_durations.get(i, self.duration_mode_var.get())
                                next_delays = (
                                    compute_pattern_slot_delays(
                                        len(next_steps), p.half_period, ratio=ratio, speed_factor=eff_span
                                    )
                                    if has_any_tie
                                    else []
                                )
                                if is_scale_run_palette(pal_mode):
                                    base_slot_pitch = p.base_pitch
                                elif self.system.strike_mode == 'bilateral':
                                    base_slot_pitch = p.base_pitch if moving_right else min(108, p.base_pitch + (7 if i % 2 == 0 else 12))
                                elif self.system.strike_mode == 'octaveAlt':
                                    base_slot_pitch = p.base_pitch if moving_right else min(108, p.base_pitch + 12)
                                elif self.system.strike_mode == 'stepArp':
                                    pool = self.system.scale_notes
                                    base_slot_pitch = pool[(i + int(self.anim_time * 2)) % len(pool)]
                                else:
                                    base_slot_pitch = p.base_pitch

                                active_seq_idx = 0
                                for k_sub, step_val in enumerate(active_steps):
                                    if not is_hit(step_val):
                                        continue

                                    base_delay = slot_delays[k_sub]
                                    if has_any_tie:
                                        tie_count, slot_span, tied_span = compute_step_tie_span(
                                            active_steps, next_steps, k_sub, p.half_period, slot_delays, next_delays
                                        )
                                        step_dur = compute_tied_note_duration(
                                            dur_mode, dur, True, tie_count, slot_span, tied_span
                                        )
                                    else:
                                        tie_count = 0
                                        step_dur = dur
                                    step_flash_ms = min(900, max(140, int(step_dur * 500))) if tie_count > 0 else 85

                                    sub_vel = compute_strum_velocity(vel, active_seq_idx, n_active, sens)
                                    strike_idx_used = (
                                        (n_steps - 1 - k_sub)
                                        if (getattr(self, 'strum_retrograde', False) and not moving_right)
                                        else k_sub
                                    )
                                    active_seq_idx += 1

                                    sub_c_idx = self.ball_strike_counts.get(i, 0)
                                    sub_pitch = compute_strike_pitch(
                                        base_pitch=base_slot_pitch,
                                        strike_idx=strike_idx_used,
                                        palette_key=pal_mode,
                                        scale_notes=self.system.scale_notes,
                                        strike_counter=sub_c_idx,
                                        harmony_type=self.harmony_type_var.get()
                                    )
                                    self.ball_strike_counts[i] = sub_c_idx + 1

                                    if sub_pitch is not None:
                                        dt_ms = int(round(base_delay * 1000))
                                        if dt_ms <= 0:
                                            self.audio_engine.play_note(
                                                pitch=sub_pitch,
                                                velocity=sub_vel,
                                                duration=step_dur,
                                                pan=p.pan,
                                                pendulum_index=i
                                            )
                                            self._register_sounding_pendulum_pitch(sub_pitch, step_dur)
                                            self.active_flashes[i] = 12
                                            self._flash_matrix_step(i, side_key, k_sub, flash_ms=step_flash_ms)
                                            if hasattr(self, 'pilot_flashes') and i in self.pilot_flashes:
                                                if k_sub < len(self.pilot_flashes[i][side_key]):
                                                    self.pilot_flashes[i][side_key][k_sub] = 12
                                                self.pilot_flashes[i]['last_dir'] = side_key
                                        else:
                                            aid_holder: List[str] = []

                                            def _fire_step_voice(
                                                idx=i,
                                                pt=sub_pitch,
                                                v=sub_vel,
                                                d=step_dur,
                                                pn=p.pan,
                                                sk=side_key,
                                                si=k_sub,
                                                fms=step_flash_ms,
                                                a_hold=aid_holder,
                                            ):
                                                aid_self = a_hold[0] if a_hold else None
                                                if aid_self and aid_self in self.pending_step_after_ids:
                                                    self.pending_step_after_ids.remove(aid_self)
                                                self._trigger_secondary_strike_matrix(
                                                    idx, pt, v, d, pn, side=sk, strike_idx=si, flash_ms=fms
                                                )

                                            aid = self.root.after(dt_ms, _fire_step_voice)
                                            aid_holder.append(aid)
                                            self.pending_step_after_ids.append(aid)
                    else:
                        if hasattr(self, 'pilot_flashes') and i in self.pilot_flashes:
                            self.pilot_flashes[i]['last_dir'] = side_key

                # Decay flash counters
                flash_amount = self.active_flashes.get(i, 0)
                if flash_amount > 0:
                    self.active_flashes[i] -= 1

                if hasattr(self, 'pilot_flashes') and i in self.pilot_flashes:
                    for side in ('left', 'right'):
                        for s_idx in range(len(self.pilot_flashes[i][side])):
                            if self.pilot_flashes[i][side][s_idx] > 0:
                                self.pilot_flashes[i][side][s_idx] -= 1

            self.canvas_pilot_coords.clear()
            self.canvas_mute_coords.clear()
            self.canvas_bob_coords.clear()

        self.root.after(16, self._animate)

    def _ensure_exports_dir(self) -> str:
        exports_dir = os.path.abspath("exports")
        os.makedirs(exports_dir, exist_ok=True)
        return exports_dir

    def _open_exports_folder(self):
        exports_dir = self._ensure_exports_dir()
        os.startfile(exports_dir)

    def _save_studio_wav(self):
        dur = self.duration_var.get()
        exports_dir = self._ensure_exports_dir()
        harm_name = self.harmony_type_var.get()
        root_name = f"{self.root_key_var.get()}{self.octave_var.get()}"
        sig_tag = self.time_sig_var.get().replace('/', '_')
        default_name = f"pendulum_{root_name}_{harm_name}_{sig_tag}_{self.timbre_var.get()}_{dur}s.wav"
        filepath = filedialog.asksaveasfilename(
            initialdir=exports_dir,
            initialfile=default_name,
            defaultextension=".wav",
            filetypes=[("WAV Audio Files", "*.wav")]
        )
        if not filepath:
            return

        def do_export():
            events = self.system.generate_strikes(dur)
            export_wav(events, filepath, dur, timbre=self.timbre_var.get())
            self.root.after(0, lambda: messagebox.showinfo("WAV Saved", f"File saved:\n{filepath}"))

        threading.Thread(target=do_export, daemon=True).start()

    def _save_studio_midi(self):
        dur = self.duration_var.get()
        exports_dir = self._ensure_exports_dir()
        harm_name = self.harmony_type_var.get()
        root_name = f"{self.root_key_var.get()}{self.octave_var.get()}"
        sig_tag = self.time_sig_var.get().replace('/', '_')
        default_name = f"pendulum_{root_name}_{harm_name}_{sig_tag}_{dur}s.mid"
        filepath = filedialog.asksaveasfilename(
            initialdir=exports_dir,
            initialfile=default_name,
            defaultextension=".mid",
            filetypes=[("MIDI Files", "*.mid")]
        )
        if not filepath:
            return

        def do_export():
            events = self.system.generate_strikes(dur)
            prog_map = {
                'piano': 0, 'marimba': 12, 'celesta': 11,
                'guitar-nylon': 24, 'harp': 46, 'drums': 'drums',
                'chimes': 11, 'pluck': 24,
                'organ-pipe': 19, 'organ-cathedral': 19, 'organ-hammond': 16,
                'organ-harmonium': 20, 'organ-drone': 89, 'organ-glass': 94,
                'organ-paisaje-mix': 19
            }
            t_low = self.timbre_var.get().lower()
            default_prog = 19 if 'organ' in t_low else ('drums' if 'drum' in t_low else 0)
            prog = prog_map.get(t_low, default_prog)
            export_midi(
                events,
                filepath,
                tempo_bpm=float(self.bpm_var.get()),
                program=prog,
                multi_track=self.multitrack_var.get(),
                time_signature=self.time_sig_var.get()
            )
            self.root.after(0, lambda: messagebox.showinfo("MIDI Saved", f"File saved:\n{filepath}"))

        threading.Thread(target=do_export, daemon=True).start()


def launch_gui():
    root = tk.Tk()
    app = PendulumApp(root)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
