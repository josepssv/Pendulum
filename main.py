"""
Pendulum Polyphony - Main Entry Point
Run without arguments to launch the GUI, or use CLI flags for instant batch exports.
"""

import sys
import os
import argparse

# Ensure standard output supports UTF-8 on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from engine import PendulumSystem, SCALES
from midi_export import export_midi
from audio_synth import export_wav

def cli_main():
    parser = argparse.ArgumentParser(
        description="Pendulum Polyphony: Physical pendulum wave polyphony synthesizer & WAV/MIDI recorder."
    )
    parser.add_argument("--gui", action="store_true", help="Launch visual interactive GUI")
    parser.add_argument("--scale", type=str, default="romanza", choices=list(SCALES.keys()), help="Scale preset")
    parser.add_argument("--balls", type=int, default=10, help="Number of pendulums (1 to 20)")
    parser.add_argument("--duration", type=float, default=30.0, help="Recording duration in seconds")
    parser.add_argument("--timbre", type=str, default="chimes", help="Audio timbre or sample bank folder name")
    parser.add_argument("--mode", type=str, default="bilateral", choices=["bilateral", "unison", "stepArp", "octaveAlt"], help="Strike mode")
    parser.add_argument("--bpm", type=float, default=96.0, help="Tempo BPM for MIDI")
    parser.add_argument("--sig", type=str, default="4/4", choices=["4/4", "3/4", "2/4", "6/8", "5/4"], help="Time signature (compas)")
    parser.add_argument("--articulation", type=str, default="auto", choices=["auto", "staccato", "short", "normal", "tenuto", "legato", "drone", "paisaje"], help="Note duration & articulation")
    parser.add_argument("--multitrack", action="store_true", help="Separate each pendulum into its own MIDI track")
    parser.add_argument("--wav", type=str, default=None, help="Output WAV path (optional)")
    parser.add_argument("--midi", type=str, default=None, help="Output MIDI path (optional)")
    parser.add_argument("--quick-both", action="store_true", help="Quickly export both WAV and MIDI to exports/ folder")

    args = parser.parse_args()

    # If no export flags are passed and not explicitly CLI, launch GUI
    if len(sys.argv) == 1 or args.gui:
        from gui import launch_gui
        launch_gui()
        return

    # CLI mode
    os.makedirs("exports", exist_ok=True)
    system = PendulumSystem(
        scale_key=args.scale,
        n_pendulums=args.balls,
        strike_mode=args.mode,
        tempo_bpm=args.bpm,
        time_signature=args.sig,
        note_duration_mode=args.articulation
    )

    print(f"🎵 Simulating {args.balls} pendulums with scale '{args.scale}' ({SCALES[args.scale]['name']})...")
    events = system.generate_strikes(args.duration)
    print(f"✨ Calculated {len(events)} musical strike events over {args.duration:.1f} seconds.")

    wav_out = args.wav
    midi_out = args.midi

    if args.quick_both and not (wav_out or midi_out):
        base_name = f"pendulum_{args.scale}_{args.timbre}_{int(args.duration)}s"
        wav_out = os.path.join("exports", f"{base_name}.wav")
        midi_out = os.path.join("exports", f"{base_name}.mid")

    if wav_out:
        print(f"🔊 Synthesizing WAV ({args.timbre} timbre)... -> {wav_out}")
        export_wav(events, wav_out, args.duration, timbre=args.timbre)
        print(f"✅ WAV file saved: {wav_out}")

    if midi_out:
        prog_map = {
            'piano': 0, 'marimba': 12, 'celesta': 11,
            'guitar-nylon': 24, 'harp': 46, 'drums': 'drums',
            'chimes': 14, 'pluck': 24,
            'organ-pipe': 19, 'organ-cathedral': 19, 'organ-hammond': 16,
            'organ-harmonium': 20, 'organ-drone': 89, 'organ-glass': 94,
            'organ-paisaje-mix': 19
        }
        t_low = args.timbre.lower()
        default_prog = 19 if 'organ' in t_low else ('drums' if 'drum' in t_low else 11)
        prog = prog_map.get(t_low, default_prog)
        print(f"🎹 Exporting MIDI track{' (Multi-track DAW)' if args.multitrack else ''}... -> {midi_out}")
        export_midi(events, midi_out, tempo_bpm=args.bpm, program=prog, multi_track=args.multitrack, time_signature=args.sig)
        print(f"✅ MIDI file saved: {midi_out}")

if __name__ == "__main__":
    cli_main()
