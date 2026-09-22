# Headless rendering & verification

## The render command

```
pd -nogui -batch -noaudio -r 44100 -path <dir> -open patch.pd
```

- `-batch` runs the scheduler **and advances the DSP clock** as fast as the CPU
  allows — roughly 40× realtime. Logical time is preserved, so `[metro 125]`
  still produces musically-correct spacing in the captured samples.
- `-noaudio` suppresses "error opening audio: Unanticipated host error".
- `-r 44100` pins the sample rate (Pd's default may differ).
- **The patch must self-terminate** with a `\; pd quit` message. Without it,
  `-batch` runs forever. A hung `pd` process is itself a useful signal that your
  instrumentation failed to load.

On Windows: `pd.exe` is the **GUI** app; `pd.com` is the console build with
attached stdio — use `pd.com` when you need to capture output.

## Capturing audio

Record into an in-memory array with `[tabwrite~]`, then write it **synchronously**
with `[soundfiler]`:

```
[loadbang] → [t b b b]
   right → \; pd dsp 1                 turn DSP on FIRST
   middle → bang [tabwrite~ arr]       start recording
   left  → [del <ms>] → [soundfiler] "write -wave <abs-path> arr" → [del 100] → \; pd quit
```

**Do not use `[writesf~]`** for this — its background disk-writer thread races
the batch scheduler and you get a 44-byte header and `Bad file descriptor`.

Two traps:
- **`soundfiler` resolves relative paths against the directory of the canvas
  containing it**, not the process cwd. Always pass an absolute path (forward
  slashes are fine on Windows). Avoid spaces — they tokenize.
- **`soundfiler` normalizes any array whose peak exceeds 1.0 on write**, at any
  bit depth, printing `reducing max amplitude 8.000000 to 1`. It *scales*
  (preserving waveform shape) rather than clipping, so an over-unity patch comes
  back looking like a clean full-scale signal and its true level is lost. Parse
  that console line and multiply the buffer back by the reported peak to recover
  the real signal — otherwise you'll never detect a patch that would clip on
  playback.

## Capturing from a patch you didn't write

You cannot shadow the built-in `[dac~]` with a `dac~.pd` abstraction on the
path — Pd uses the registered built-in and the render is silent. Instead:

1. Copy the patch and **rewrite the class token** of every `dac~` object box to
   a differently-named sink abstraction (`mysink~`). Match on the class field
   only: don't touch `#X text` comments, don't touch `adc~`, and preserve
   creation args. Note `\b` will **not** anchor after `dac~` (the trailing `~`
   is a non-word char) — use a lookahead like `dac~(?=\s|$)`.
2. The sink abstraction taps its `[inlet~]`s onto a global `[throw~]` bus. Since
   `throw~` sums, **any number** of `dac~` objects at any canvas depth mix onto
   one bus — mirroring how Pd sums multiple dac~ anyway.
3. A tool-authored wrapper patch `[catch~]`es the bus and does the recording.
   Author that wrapper yourself so its indices are correct by construction.

The same rewrite trick drives inputs: `[notein]` can't be shadowed either, so
rewrite it to a shim abstraction fed by a `[receive]`, and schedule note
messages to play the instrument.

## Driving instruments

Most interesting patches are instruments: silent until something sends a note,
a gate, or a parameter. Headless, nothing does. Schedule control events into the
render — `[del <t>] → [\; <receiver> <atoms>(` chains fired from `loadbang` —
to play notes, set parameters, and switch states over the take.

Design patches so every performance parameter arrives via a **named receive**.
Then the same parameter is driveable by a GUI control *and* by an automated
test, and you can measure the instrument across its whole control space.

## What to check

Gates (any failure invalidates everything else): **not silent**, **not
clipped**, **no NaN/Inf**, expected duration. Then: fundamental pitch and
note/cents error, RMS/peak level, spectral centroid/band distribution,
tonal-vs-noisy (spectral flatness), temporal motion (steady vs evolving).

Useful measurement notes:
- Compute the spectral centroid **power-weighted**, not magnitude-weighted — a
  magnitude-weighted centroid is dragged upward by the thousands of tiny bins in
  a quantization/noise floor and will report a bass-heavy patch as bright.
- Make frequency bands cover 0..Nyquist with no gaps, or DC/subsonic content and
  near-Nyquist aliasing vanish from the analysis.
- A **timbre fingerprint cannot detect note-order changes.** To prove a
  generative melody actually changed, compare pitch content (prominent
  partials), not overall spectral similarity.
- Sweep a control surface as a **grid** and tabulate level + brightness per
  cell. That turns "there's a dead spot somewhere" into a coordinate.
- For "does the loop repeat" / "did this phrase change", analyze **per beat
  window** and compare aligned windows, or read the pitch of each onset — a
  whole-render spectrum is blind to order (measured: two different tunes in the
  same scale fingerprinted at 0.993 vs 0.997 for a tune against itself).

## What batch mode cannot tell you

`-batch` runs the scheduler as fast as it can and never touches audio, MIDI or
the GUI socket, so a patch can verify perfectly in batch and fail as a real
process:

- **ELSE GUI objects (`else/keyboard`, `else/pad`, …) hang a headless
  *real-time* Pd** (`pd -nogui -noaudio`, no `-batch`): loading stalls inside
  the object's library search and the patch never starts. Batch mode masks it.
  Keep engine patches vanilla and put GUI externals in a separate face patch
  that opens the engine (`[pdcontrol]` `dir` → `; pd open <file> <dir>`).
- `writesf~` cannot be verified in batch (its disk thread races the
  scheduler); `netsend`/`netreceive` behaviour, MIDI and anything timing-
  dependent likewise want a real run.
- So keep a **real-time smoke test** next to the batch battery: spawn
  `pd -nogui -noaudio -stderr -open patch.pd` (it ticks and sends OSC at real
  time), drive it over UDP/OSC, listen for its events, check the files it
  writes, then terminate it. Launch `pd.exe` by full path on Windows —
  `pd.com` is a wrapper, and killing it can orphan the engine.

## The tools

- **pdverify** — headless render + analysis + scored expectations + reference
  matching + control injection (`github.com/DashWieland/pdverify`).
- **pdbuild** — Python metaprogramming builder that owns `#X connect` indices.

Typical loop:

```python
from pdverify import verify, expect, control
from pdverify.render import RenderSpec

card = verify("build.pd", [expect.not_silent(), expect.no_clipping(),
                           expect.note("A4", tol_cents=30)],
              spec=RenderSpec(duration=2.0,
                              controls=tuple(control.note("A4", dur=1.5))))
print(card.feedback())   # actionable: "got A3 … scale the oscillator frequency by 2.0"
```
