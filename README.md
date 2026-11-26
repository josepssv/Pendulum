# Pendulum v1.3 — Pendulum Polyphony

Simulador polirrítmico musical basado en ondas de péndulos en Python, con síntesis en tiempo real, banco de samples acústicos y exportación a WAV y MIDI multipista.

## Requisitos

- Python 3.10+ (probado con Python 3.12)
- Dependencias en `requirements.txt`

## Instalación

```bash
pip install -r requirements.txt
```

## Uso rápido

### Interfaz gráfica (GUI)
- En Windows: doble clic en `iniciar.bat` (o `iniciar_consola.bat` para ver salida de consola).
- Desde terminal:
```bash
python main.py
```

### Modo CLI (exportación directa WAV / MIDI)
```bash
python main.py --scale romanza --balls 10 --duration 30 --timbre chimes --quick-both --multitrack
```

## Estructura básica

- `main.py` — Punto de entrada (GUI y CLI).
- `gui.py` — Interfaz visual interactiva (Tkinter + Pygame).
- `engine.py` — Motor físico de péndulos y eventos musicales.
- `harmony.py`, `rhythm_patterns.py`, `pitch_follow.py` — Escalas, progresiones, patrones rítmicos y seguimiento de tono.
- `live_audio.py`, `sample_engine.py`, `audio_synth.py` — Reproducción en vivo y síntesis/renderizado de audio.
- `midi_export.py` — Exportación MIDI Type 0 / Type 1.
- `assets/samples/` — Bancos de muestras de instrumentos.
- `download_samples.py`, `generate_organ_soundscapes.py` — Utilidades opcionales para regenerar o descargar samples base.
