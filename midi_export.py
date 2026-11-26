"""
MIDI Exporter for Pendulum System
Converts simulation strike events to standard MIDI files (.mid)
Supports single-track and multi-track (DAW separated) modes.
"""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from typing import List
from engine import StrikeEvent, midi_to_note_name

def _timbre_to_midi_program(timbre_name: str, fallback_program=11):
    """Maps a Pendulum instrument/timbre name to a General MIDI program number or 'drums'."""
    t_low = (timbre_name or "").strip().lower()
    if not t_low:
        return fallback_program
    prog_map = {
        'piano': 0,
        'marimba': 12,
        'celesta': 11,
        'chimes': 14,
        'guitar-nylon': 24,
        'pluck': 24,
        'harp': 46,
        'organ-pipe': 19,
        'organ-cathedral': 19,
        'organ-hammond': 16,
        'organ-harmonium': 20,
        'organ-drone': 89,
        'organ-glass': 94,
        'organ-paisaje-mix': 19,
        'drums': 'drums',
        'percussion': 'drums',
    }
    if t_low in prog_map:
        return prog_map[t_low]
    if 'organ' in t_low:
        return 19
    if 'drum' in t_low or 'perc' in t_low:
        return 'drums'
    return fallback_program


def export_midi(
    events: List[StrikeEvent],
    output_path: str,
    tempo_bpm: float = 96.0,
    program: int = 11,
    ticks_per_beat: int = 480,
    multi_track: bool = False,
    time_signature: str = '4/4'
) -> str:
    """
    Exports a list of StrikeEvent objects to a standard MIDI file (.mid).
    If multi_track is True, creates a distinct track per pendulum voice.
    Writes exact tempo and time signature metadata.
    """
    mid = MidiFile(type=1 if multi_track else 0, ticks_per_beat=ticks_per_beat)
    tempo_us = mido.bpm2tempo(tempo_bpm)
    ticks_per_sec = (tempo_bpm / 60.0) * ticks_per_beat

    # Parse time signature
    try:
        parts = time_signature.split('/')
        num = int(parts[0])
        den = int(parts[1])
    except Exception:
        num, den = 4, 4

    # Check if drums
    is_drum = (program == 'drums' or program == 'percussion')
    midi_prog = 0 if is_drum else (int(program) if isinstance(program, int) else 11)
    base_channel = 9 if is_drum else 0

    if not multi_track:
        # Single track with all voices combined
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(MetaMessage('track_name', name='Pendulum Percussion' if is_drum else 'Pendulum Polyphony', time=0))
        track.append(MetaMessage('set_tempo', tempo=tempo_us, time=0))
        track.append(MetaMessage('time_signature', numerator=num, denominator=den, time=0))
        track.append(Message('program_change', program=midi_prog, time=0, channel=base_channel))

        actions = []
        for ev in events:
            actions.append((ev.time, 'note_on', ev.pitch, ev.velocity, base_channel))
            actions.append((ev.time + ev.duration, 'note_off', ev.pitch, 0, base_channel))

        actions.sort(key=lambda a: (a[0], 0 if a[1] == 'note_off' else 1))

        prev_tick = 0
        for t_sec, action_type, pitch, vel, ch in actions:
            current_tick = int(round(t_sec * ticks_per_sec))
            delta_ticks = max(0, current_tick - prev_tick)
            prev_tick = current_tick

            if action_type == 'note_on':
                track.append(Message('note_on', note=pitch, velocity=vel, time=delta_ticks, channel=ch))
            else:
                track.append(Message('note_off', note=pitch, velocity=0, time=delta_ticks, channel=ch))

        track.append(MetaMessage('end_of_track', time=ticks_per_beat))

    else:
        # Group events by pendulum index
        pendulum_groups = {}
        for ev in events:
            pendulum_groups.setdefault(ev.pendulum_index, []).append(ev)

        # Global conductor tempo track (Type 1 MIDI standard)
        conductor = MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(MetaMessage('track_name', name='Conductor / Tempo', time=0))
        conductor.append(MetaMessage('set_tempo', tempo=tempo_us, time=0))
        conductor.append(MetaMessage('time_signature', numerator=num, denominator=den, time=0))
        conductor.append(MetaMessage('end_of_track', time=ticks_per_beat))

        for p_idx in sorted(pendulum_groups.keys()):
            p_events = pendulum_groups[p_idx]
            first_pitch = p_events[0].pitch if p_events else 60
            ev_timbre = getattr(p_events[0], 'timbre', None) if p_events else None
            track_prog = _timbre_to_midi_program(ev_timbre, program) if ev_timbre else program
            track_is_drum = (track_prog == 'drums' or track_prog == 'percussion')
            track_midi_prog = (
                0
                if track_is_drum
                else (int(track_prog) if isinstance(track_prog, int) else 11)
            )
            if p_idx == 15:
                track_name = f"Teclado ({ev_timbre or 'piano'} - {midi_to_note_name(first_pitch)})"
            else:
                track_name = f"Pendulum {p_idx + 1} ({midi_to_note_name(first_pitch)})"
            ch = 9 if track_is_drum else (p_idx % 16 if (p_idx % 16) != 9 else 10)

            track = MidiTrack()
            mid.tracks.append(track)
            track.append(MetaMessage('track_name', name=track_name, time=0))
            track.append(Message('program_change', program=track_midi_prog, time=0, channel=ch))

            actions = []
            for ev in p_events:
                actions.append((ev.time, 'note_on', ev.pitch, ev.velocity))
                actions.append((ev.time + ev.duration, 'note_off', ev.pitch, 0))

            actions.sort(key=lambda a: (a[0], 0 if a[1] == 'note_off' else 1))

            prev_tick = 0
            for t_sec, action_type, pitch, vel in actions:
                current_tick = int(round(t_sec * ticks_per_sec))
                delta_ticks = max(0, current_tick - prev_tick)
                prev_tick = current_tick

                if action_type == 'note_on':
                    track.append(Message('note_on', note=pitch, velocity=vel, time=delta_ticks, channel=ch))
                else:
                    track.append(Message('note_off', note=pitch, velocity=0, time=delta_ticks, channel=ch))

            track.append(MetaMessage('end_of_track', time=ticks_per_beat))

    mid.save(output_path)
    return output_path
