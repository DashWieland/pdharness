---
name: pure-data
description: Building, editing, and verifying Pure Data (Pd) patches. Use for anything involving Pd/PureData, .pd files, audio patching, DSP objects (osc~, bob~, vline~, delwrite~), synths/instruments/sequencers in Pd, or the pdverify/pdbuild tools. Covers the .pd file format, execution-order semantics, headless rendering, and the silent-failure gotchas that make patches look fine and produce nothing.
---

# Pure Data

## The frame

**You cannot hear the patch.** Everything else follows from that. A Pd patch
that loads without console errors is not a working patch — it is an untested
hypothesis. It can be silent, detuned an octave, DC-offset, clipping, or
NaN-diverged, and look perfectly fine.

So the loop is always: **build → render → analyze → iterate.** Never report a
patch as working on the basis that it loaded.

## Workflow

1. **Build with metaprogramming, not by hand.** Hand-writing `.pd` breaks on
   `#X connect` index bookkeeping; issuing hundreds of live MCP tool-calls is
   slow and fragile. Use a builder that owns the indices (`pdbuild`).
2. **Verify by rendering** — `pdverify` renders headless (~40× realtime) and
   reports pitch, level, integrity gates, spectral bands, and a plain-language
   description. Drive instruments with control injection.
3. **Diagnose from the report**, not from reading the patch: silent / clipped /
   NaN / wrong pitch each point at different causes (see the checklist below).

## The five things that will bite you

**1. GUI controls emit nothing at load.** A `tgl`, `hradio`, `hsl`, or `nbx`
sits there holding a value and sends *nothing* until a human touches it.
Anything downstream (a gain `line~`, a `spigot` gate) stays at 0 → **silence**,
with no error. Always initialize: `[loadbang] → [0( → the control`. This is the
single most common cause of a mysteriously dead patch.

**2. Comments take a connection index, and commas break them.** Every `#X`
element — objects, messages, **comments**, atoms, GUIs — increments the index
used by `#X connect`. Forget that comments count and every later connection is
wrong. Also: an unescaped `,` or `;` inside a comment or message box is parsed
as a message separator (`error: canvas: no method for 'play'`). Escape as `\,`
and `\;`.

**3. Order of execution is right-to-left and partly undefined.** Outlets fire
right-to-left (highest index first). Fan-out from *one* outlet to several
inlets is **undefined order** — use `[t]`/`[trigger]` when order matters. This
governs design: to set a value *before* a trigger fires, put it on a **higher**
outlet index. (E.g. a step-sequencer message packed as `gate accent pitch slide`
so `[unpack]` emits slide → pitch → accent → gate, setting glide and pitch
before the gate triggers the envelope.)

**4. You cannot shadow a built-in class.** Putting a `dac~.pd` abstraction on
the search path does *not* intercept `[dac~]` — Pd resolves the registered
built-in and never looks at the path, and your render comes out silent. To tap
or replace a built-in, **rewrite the class token** in a copy of the patch to a
differently-named abstraction (`dac~` → `mysink~`).

**5. Silent is not the same as broken.** Distinguish "rendered silence" from
"failed to render." A missing external, an unreachable sink, or a nonzero exit
must raise loudly — never be scored as a legitimately quiet patch.

## Execution model, briefly

- Two domains: **control messages** (event-driven) and **signals** (`~` objects,
  processed in 64-sample blocks). Thick cords are signals.
- **Leftmost inlet is hot** (triggers output); others are cold (store only). Set
  cold inlets *before* the hot one fires — e.g. `[pack f f]`.
- Message cascades run **depth-first to completion** between DSP ticks; logical
  time is sample-accurate (`[del]` in `-batch` advances correctly).
- Signal graph must be acyclic; feedback needs `[send~]/[receive~]`,
  `[throw~]/[catch~]`, or `[delwrite~]/[delread~]` (one block of delay).

## Essential objects

Control: `metro` `del` `f` `+` `mod` `sel`/`select` `spigot` `route` `pack`
`unpack` `t`/`trigger` `moses` `random` `mtof` `ftom` `s`/`r` `loadbang` `line`

Signal: `osc~` `phasor~` `noise~` `*~` `+~` `-~` `clip~` `lop~` `hip~` `bp~`
`vcf~` **`bob~`** (Moog **resonant** ladder — signal cutoff *and* resonance
inlets; >4 self-oscillates) `vline~` (sample-accurate envelopes) `line~`
`sig~` `snapshot~` `delwrite~`/`delread~`/`vd~` `rev1~`/`rev2~`/`rev3~`
`tabwrite~`/`tabread4~` `expr~` `dac~`

Two that carry a lot of weight:
- **`vline~` envelopes**: `[1 5, 0 180 5(` = ramp to 1 over 5 ms, then (after a
  5 ms delay) ramp to 0 over 180 ms. Attack–decay in one message. The comma is
  the mechanism — escape it as `\,` when writing files.
- **`line~` + `[pack f f]`**: portamento/glide and smooth control→signal. Send
  `"target time"`. This is how you avoid zipper noise on any parameter.

Full detail: [references/objects.md](references/objects.md).

## File format

```
#N canvas 20 20 900 700 12;          <- window
#X obj 40 40 osc~ 440;               <- object      (index 0)
#X msg 40 90 1 5 \, 0 180 5;         <- message     (index 1)
#X text 200 40 a comment;            <- comment     (index 2 — it counts!)
#X floatatom 40 140 8 0 0 0 - - - 0; <- number box  (index 3)
#X connect 0 0 1 0;                  <- src outlet dst inlet
```

`$1`–`$9` in an object box are creation args (expanded at load); `$0` is a
per-instance unique id — use `$0-name` for instance-local send/receive/array
names. `$v1`/`$f1` inside `expr~`/`expr` are *not* expanded (no digit after `$`)
and pass through safely.

**`$0` in a message box is `0`, not the instance id** (verified 0.56.2:
`[$0(` outputs 0 and `[$0-name(` outputs `0-name`, where `[f $0]` gives
1004). So `[; $0-freq 440(` silently sends to a global `0-freq`. To get the
id into a message, carry it in an object: `[f $0]` → `[; $1-freq 440(`
reaches `[r $0-freq]` (verified). Or send through an object box that has
the name: `[s $0-freq]`.

Full detail incl. arrays, subpatches, GUI parameter lists:
[references/file-format.md](references/file-format.md).

## Abstractions

An abstraction is just a `.pd` file on the search path, instantiated as
`[name]`. `[inlet]`/`[outlet]`/`[inlet~]`/`[outlet~]` define its ports, **ordered
by x-position**. Pd finds abstractions in the patch's own directory (plus
`-path`). Use `$0-` prefixes inside so multiple instances don't collide, and
`[clone]` for polyphony.

This is how you make an instrument *playable*: put the engine in abstractions
and leave only the control surface on the parent canvas. Route surface controls
through **named sends/receives** rather than direct wires — then they're
driveable by message, which makes the rig both scriptable and headless-testable.

## Headless rendering

```
pd -nogui -batch -noaudio -r 44100 -open patch.pd
```

`-batch` advances the DSP clock faster than realtime; `-noaudio` avoids device
errors. **The patch must self-terminate** (`; pd quit`) or the process hangs
forever. Capture with `[tabwrite~]` into an array + a synchronous `[soundfiler]`
write — **not** `[writesf~]`, whose background disk thread races the batch
scheduler and yields an empty file.

Full recipe, incl. the `soundfiler` over-unity normalization trap and the
`dac~`-rewrite capture technique: [references/headless-verify.md](references/headless-verify.md).

## Debug checklist

| Symptom | Look at |
|---|---|
| Silent, no errors | GUI control never initialized (#1); DSP off; envelope never triggered; a gain/`spigot` sitting at 0 |
| Batch render hangs | no `; pd quit` in the patch |
| `couldn't create` | missing external, or library folder not on Pd's **path** (`-lib` alone is often not enough) |
| `canvas: no method for '<word>'` | unescaped `,`/`;` in a comment or message |
| Connections land on wrong objects | forgot comments/atoms take indices |
| NaN / Inf in output | resonant filter diverging — lower resonance, raise `oversample`, or clip the feedback |
| Output loud but analysis says clean | `soundfiler` normalized an over-unity signal on write |
| Instrument makes no sound headless | it's waiting for input — inject notes/messages |

## References

| File | Load when |
|---|---|
| [references/file-format.md](references/file-format.md) | Writing or parsing `.pd` text: records, escaping, arrays, subpatches, GUI params |
| [references/objects.md](references/objects.md) | Choosing objects / wiring them: I/O details, envelopes, filters, effects, ELSE |
| [references/headless-verify.md](references/headless-verify.md) | Rendering, capturing audio, verifying, driving instruments |
