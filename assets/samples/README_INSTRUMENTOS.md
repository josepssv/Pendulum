# Guía: Cómo Añadir Vuestros Propios Instrumentos

Este sistema cuenta con una arquitectura abierta que auto-detecta cualquier nuevo instrumento que pongáis en esta carpeta.

---

## 1. Pasos Básicos

1. Crea una nueva carpeta dentro de `assets/samples/` con el nombre de tu instrumento.  
   *Por ejemplo:*  
   - `assets/samples/MiGuitarra/`
   - `assets/samples/CuencoTibetano/`
   - `assets/samples/SinteAnalogico/`
   - `assets/samples/PercusionFlamenca/`

2. Introduce tus archivos de audio grabados dentro de esa carpeta.  
   *Formatos admitidos:* `.wav`, `.mp3`, `.ogg`, `.flac`.

3. ¡Listo! Al arrancar la aplicación o pulsar `[Q]` para cambiar de instrumento, vuestro nuevo instrumento aparecerá en la lista.

---

## 2. Nomenclatura de Archivos

### A. Para Instrumentos Melódicos (Guitarras, Pianos, Flautas, Sintes...)
Nombra los archivos con el nombre de la nota y su octava, o con su número MIDI:
- `C3.wav`, `E3.wav`, `G3.wav`, `C4.wav`, `E4.wav`, `G4.wav`...
- Con sostenidos o bemoles: `F#3.wav` o `Fs3.wav`, `Bb3.wav`, `C#4.wav`...
- O por número de nota MIDI: `60.wav` (Do central / C4), `64.wav` (Mi / E4), etc.

> **¡No necesitas grabar todas las notas!**  
> Si solo tienes 2, 3 o 4 notas grabadas (o incluso un único archivo como `C4.wav`), el motor interpola y ajusta el tono automáticamente para cubrir todas las notas que toquen los péndulos.

### B. Para Baterías y Percusiones
Si el nombre de la carpeta contiene la palabra `drum` o `bateria` o `perc`:
- Nombra los archivos según el golpe:
  - `kick.wav` (Bombo)
  - `snare.wav` (Caja)
  - `hihat.wav` (Charles cerrado)
  - `openhat.wav` (Charles abierto)
  - `tom.wav` (Tom)
  - `clap.wav` (Palmas / Aplauso)
  - `ride.wav` / `crash.wav` (Plato)

---

## 3. Control de Resonancia y Sequedad (Decay)

En la interfaz de la aplicación encontraréis el control **Decay**:
- **0.4x - 0.6x (Muy seco / Staccato):** Corta las colas rápidamente. Ideal para sesiones rápidas o con muchos péndulos oscilando a la vez sin que se acumule reverberancia.
- **1.0x (Natural):** Duración y decaimiento acústico estándar del instrumento.
- **1.5x - 2.0x (Sustain largo):** Para pasajes lentos o ambientes flotantes.
