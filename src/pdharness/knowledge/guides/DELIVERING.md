# Delivering a file: loops, arcs, level, small speakers

Some instruments end up played live. Others end up as files that go
somewhere: under a video, into a game, in an installation, on a playlist.
A delivered file has claims of its own, and you check them the same way
as the others.

| Claim | Check |
|---|---|
| it loops without a seam | `seamless()` |
| it lifts (or fades, or opens up) near the end | `change("level", before=(0, -4), after=(-4, None), min=2)` |
| it sits at a level, with gentle peaks | `render_patch(..., rms_dbfs=-18, peak_dbfs=-1)`, then `level(-18)` and `no_clipping(0.9)` |
| it is audible where it is heard | `band_level(250, min_db=-12, relative=True)` (a phone speaker) |
| it is the format asked for | `render_patch(..., sr=48000, bits=24)` (48 kHz is the video standard) |

`verify_patch` takes a `.wav` as well as a `.pd`. Point it at the file you
are about to hand over and it scores exactly what is on disk.

## Loops

`render_patch(patch, out, loop=20, crossfade=2, preroll=6)` writes exactly
20 seconds that loop. To do that it renders 6 + 20 + 2 seconds, skips the
first 6, and crossfades the 2 that followed the cut onto the head. At the
wrap, the end of the file is followed by the audio that really followed
it, reverb tails included. The result reports the seam.

- **Preroll past the start-up.** A patch rendered from silence has an
  empty reverb and envelopes that haven't opened yet, so its first seconds
  are quieter than the rest. A loop that starts there jumps at the join.
- **The crossfade follows the material.** The default curve measures how
  correlated the head and the overrun are. It is linear for a drone that
  is the same signal one loop later, and equal power for unrelated
  textures.
- **A steady tone needs whole cycles per loop.** If its frequency times the
  loop length is near a half-integer, the tone is in anti-phase with
  itself one loop later. It then cancels mid-crossfade whatever the curve.
  `seamless` reports the dip ("head strays ... dB"). Tune drone partials so
  that `freq * loop_s` is an integer, or modulate them with an LFO that
  completes whole cycles per loop. Generative layers (plucks, noise,
  reverb) need nothing special.
- **Why `seamless`, not `|x[0] - x[-1]|`?** A sine cut at half a cycle
  returns to zero, so its sample step is nothing, but its slope flips and
  you hear a click. `seamless` high-passes the take circularly, the way
  playback wraps it, and compares the join with the rest of the take.

## Arcs: a change that lands near the end

A short cut often wants its moment at the end: something opens, lifts or
resolves just as the picture pays off. Make that a control score, not an
edit. **Negative times count from the end**, so one score fits every
length:

```json
"controls": [{"receive": "density", "value": 0.3, "at": 0},
             {"receive": "lift", "value": 1, "at": -4}]
```

This lands 4 s before the end of a 19-s cut, and 4 s before the end of a
47-s one. Claim it the same way: `{"name": "change", "args": ["level",
[0, -4], [-4, null]], "kwargs": {"min": 2}}`. The `within` windows of
`verify_patch` take negative times too, so `"within": [-4, null]` means
the last four seconds.

## A family of files is a loop in your build script

There is no batch format to learn. One patch, a few control sets and a
few lengths give a family of related files that share a sound:

```python
from pdharness import tools

VARIANTS = {"dusk": [{"receive": "bright", "value": 0.2}],
            "noon": [{"receive": "bright", "value": 0.8}, {"receive": "density", "value": 0.6}]}
for name, controls in VARIANTS.items():
    for seconds in (20, 60):
        out = tools.render_patch("bed.pd", f"out/{name}_{seconds}s.wav", loop=seconds, controls=controls,
                                 crossfade=2, preroll=6, sr=48000, bits=24, rms_dbfs=-18, peak_dbfs=-1,
                                 expectations=[{"name": "seamless"},
                                               {"name": "band_level", "args": [250],
                                                "kwargs": {"min_db": -12, "relative": True}}])
        print(name, seconds, out["verdict"]["passed"], out["master"], out["seam"])
```

From a shell, `pdharness run -m pdverify render bed.pd -o out.wav --loop 20
--send bright=0.2 --rms -18 --peak -1 --bits 24 --sr 48000` does the same
for one file.

## Level, honestly

`rms_dbfs` / `peak_dbfs` apply **one gain**. It is never a limiter or a
compressor, so the dynamics stay the patch's own. If the ceiling would be
passed, the ceiling wins and `master.peak_bound` is true. The file is then
quieter than the target, and the fix (fewer, softer peaks) belongs in the
patch. The level is RMS, not LUFS. For steady beds the two track closely,
but say which you measured. Leave about 1 dB of peak headroom if the file
will be encoded to a lossy format.

**Check the level where it will be heard.** Phone and laptop speakers give
little below about 250 Hz. A bed can measure −21 dBFS RMS and still be
nearly silent on a phone if that level comes from a 55 Hz drone. One
sketch measured −57 dBFS above 250 Hz. Put something above 250 Hz that
carries the mood (partials, a pluck an octave up, a noise bed), then claim
it with `band_level`.
