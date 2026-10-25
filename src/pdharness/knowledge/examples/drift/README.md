# drift

A small self-playing ambient bed. Soft plucks walk D dorian (a seeded walk,
so every render is the same) over a breathing drone and a band of air,
through a reverb. pdverify describes a delivered loop as "an evolving, warm
chord, pitched near D2". It is the bank's worked example of an ambient
patch built from `pdbuild.modules.ambient`, and of delivering it as files.

| Dial | Does | Verified |
|---|---|---|
| DENSITY | how many notes the walk plays | 0.1 → 0.9: 3 → 28 notes in 12 s (counted by a probe on `[s drift_note]`) |
| BRIGHT | a two-pole lowpass on notes and drone | 0 → 1: centroid 233 → 436 Hz (air bed off) |
| AIR | the noise bed's level | |
| SPACE | dry … all reverb | |
| LIFT | everything rises 6 dB over 3 s; send it near the end of a cut | +5.9 dB in the last 2.5 s of a 19-s cut, +9.4 dB in a 30-s one, from one end-relative score |
| LEVEL | output | default ≈ −22 dBFS RMS |

Default state: it sounds, does not clip (under 0.9), is stereo, and keeps
its level above 250 Hz within 12 dB of the whole, so a phone can play it.

## What it shows

- **Steady layers are whole cycles per loop.** The drone is 73.4 Hz (1468
  cycles in 20 s), and the drone's and the noise bed's LFOs use
  `loop_s=20`. So every steady part closes at 20, 40 and 60 s, and the
  crossfade does not beat. The plucks and the reverb are generative and
  need nothing.
- **Count notes, don't hear them.** An onset detector undercounts a wash of
  overlapping plucks (it read 7 → 2 for a density change that played
  3 → 28 notes). The patch sends each note on `[s drift_note]`, and the
  check counts them with `probe_patch`.
- **Isolate what a dial moves.** BRIGHT filters the notes and the drone,
  but not the air. With the air on, darkening the notes raised the air's
  share and the centroid went *up*. The check turns the air off.
- **A lift has to beat the music's own swing.** At +3.5 dB the lift
  measured +1.0 dB in a sparse variant, because the plucks move the level
  that much on their own. At +6 dB it reads +5.9 dB.
- **`deliver()`** writes a family at 48 kHz / 24-bit, −20 dBFS RMS with a −1
  dBFS ceiling: two variants (`dusk`, `noon`) × a 20-s loop, a 40-s loop and
  a 19-s cut that lifts. Each file is scored as written (`seamless`,
  `no_clipping`, `band_level`, and `change` for the cut). Loop seams read
  0.31–0.54 (click), 0.0 dB head excursion.

```bash
pdharness run build_drift.py               # build -> 5 checks -> the family in takes/
pdharness run build_drift.py --no-deliver
```
