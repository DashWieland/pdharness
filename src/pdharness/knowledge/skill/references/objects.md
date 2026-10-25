# Object reference (the ones worth knowing)

Vanilla unless marked. Check I/O with the object's help patch
(`<Pd>/extra/<name>-help.pd`, or right-click → Help) rather than guessing —
inlet order and signal-vs-float acceptance vary and matter.

## Envelopes & smoothing

**`vline~`** — sample-accurate envelope generator. Message is a sequence of
`target time delay` triples separated by commas:

```
1 5, 0 180 5      attack to 1 over 5ms, then (after 5ms) decay to 0 over 180ms
1                 jump to 1 instantly
0 200             ramp to 0 over 200ms starting now
```

This is the workhorse for note envelopes: fast attack, decay, retriggerable.
Written in a file the commas must be `\,`. If you want to avoid commas
entirely, split into two messages with a `[del]` between them.

**`line~`** — ramps to a target over a time: send `"target time"`. Pair with
`[pack f f]` to build the message (set the time in the cold inlet first, then
the target into the hot inlet). Two constant uses:
- **Portamento/glide:** target frequency + glide time → `line~` → `osc~`/`phasor~`
  frequency inlet. Glide time 2 ms ≈ instant, 60 ms ≈ a 303 slide.
- **Smoothed control→signal:** any parameter you'd otherwise send as a raw float
  into a signal inlet. Prevents zipper noise. `[r param] → [* range] → [+ lo] →
  [pack f 25] → [line~]`.

`sig~` converts a float to a constant signal (no smoothing — clicks).

## Filters

**`bob~`** — Moog ladder **resonant** lowpass (Runge-Kutta model). The one to
reach for when you want *character* (acid, squelch, self-oscillation).
- inlet 0: signal in · inlet 1: cutoff Hz (**float or signal**) · inlet 2:
  resonance (**float or signal**, >4 oscillates) · outlet: signal
- messages: `oversample <n>` (default 2 — raise for stability at high
  cutoff/resonance), `saturation <n>` (default 3), `clear` (reset if it blows up)
- Because cutoff takes a *signal*, you can modulate it with an envelope
  directly — that's the classic filter-envelope squelch.

`lop~` / `hip~` — one-pole low/high pass, cutoff is **control-rate only** (a
float to the right inlet). To sweep them with an LFO you must sample the LFO:
`[osc~ 0.2] → [snapshot~]` banged by a `[metro 25]` → scale → cutoff.

`bp~ <freq> <Q>` — bandpass (noise → snare/hat). `vcf~` — signal-controlled
resonant bandpass. `clip~ lo hi` — hard clip / safety limiter.

## Oscillators & noise

`osc~` (cosine), `phasor~` (0→1 ramp; `-~ 0.5` to centre it into a sawtooth,
then scale), `noise~` (white). Frequency inlets accept **signals**, so drive
them from `line~` for glides or from another oscillator for FM.

Neither `osc~` nor `phasor~` is band-limited — high harmonics alias. A lowpass
after them (or a modest cutoff) hides it.

**`phasor~` drifts; `osc~` does not, measurably.** A free-running `phasor~`
loses about 3–6e-6 of a cycle per cycle: about 15 ms an hour at a 4-s loop,
or 1e-4 of a cycle in a minute at 3/7 Hz. `osc~` stayed under 3e-7 of a
cycle over 42 s. To lock an LFO to a loop or to a `metro` clock, restart a
`vline~` ramp from the clock each cycle (pdbuild's `loop_lfo`, 2e-6 after a
minute) rather than trusting `phasor~` to stay in step. For a seamless loop,
a steady tone also needs whole cycles per loop (frequency × loop length an
integer), or it beats against itself in the crossfade.

## Saturation / drive

`[*~ drive] → [expr~ tanh($v1)]` — smooth, warm soft-clipping. Sounds far better
than `clip~` for "meat". Drive pre-gain of 1–6 is a useful range; add makeup
gain after. `clip~` remains the right tool as a final safety limiter.

**Exact harmonics from a sine: Chebyshev waveshaping.** For a unit-amplitude
cosine c = `[osc~]`, `T_k(c) = cos(kx)` exactly: T2 = 2c²−1, T3 = 4c³−3c,
T4 = 8c⁴−8c²+1, T5 = 16c⁵−20c³+5c, T6 = 32c⁶−48c⁴+18c²−1. So
`[expr~ $f2*(2*$v1*$v1-1) + $f3*(4*pow($v1,3)-3*$v1) + …]` adds harmonic k at
amplitude `$f(k)`, a brightness control that keeps a pitched voice exactly
harmonic, has no DC, and follows a gliding pitch. Shape the unit cosine
*before* the amplitude envelope (the identity needs amplitude 1), and hold
the level with 1/sqrt(1 + Σa_k²). A 1:1 FM pair used for the same job put a
sideband through 0 Hz and made a pitch-dropping drum double-strike
(overtone, 2026-09).

## Delay, chorus, reverb

`delwrite~ <name> <maxms>` writes a delay line; `delread~ <name> <ms>` reads at
a **fixed** delay; `vd~ <name>` reads at a **signal-controlled** delay (this is
what makes chorus/flange possible — modulate the delay time with a slow LFO).

Feedback delay: read → `*~ feedback` → clip → sum back into the `delwrite~`
input. Keep feedback < ~0.7 and clip it, or it runs away. Cross-feeding L→R and
R→L gives ping-pong. **The exception is a delay network** (a reverb): several
lines mixed back through an orthogonal matrix (Hadamard), each with a gain
under 1 and a damping `lop~`, are stable with no clip in the loop. 20 s of
noise at full size and no damping stayed finite and level (pdbuild's
`reverb`, verified).

**A delay feedback loop is at least one block long** (64 samples, 1.45 ms at
44.1 kHz): `delwrite~`/`delread~` round-trip no faster. So a Karplus-Strong
string built on the canvas cannot play above about 689 Hz. Sum decaying
harmonics instead (pdbuild's `pluck`), or run the loop in a subpatch with
`[block~ 1]`.

`rev1~`/`rev2~`/`rev3~` are abstractions in Pd's `extra/` folder, not
built-ins. They load headless where `extra/` ships, and are missing where it
does not; `rev3~` has 6 inlets.

**A tempo-synced delay must not slide its taps.** A `vd~` whose time follows
the pulse (`[r pulsems] → [* 3] → [line~] → vd~`) bends the pitch of every
echo while the tempo glides: the read point moves, which is a Doppler shift.
A 60 → 165 BPM glide bent a 6-pulse tap up about six semitones, and a
player heard it as "inharmonic until it resettles". Use two fixed tap pairs.
When the pulse has held still for ~150 ms, jump the silent pair to the new
times and cross-fade to it over ~80 ms. During a glide the echoes keep their
old spacing, in tune.

`rev3~ <level_dB> <liveness> <crossover_Hz> <damping%>` — **6-in** / **4-out**
reverberator (use outs 0,1 as stereo). Inlets: audio L, audio R, then level,
liveness, crossover and damping, one per inlet, so each can be changed live
(verified 0.56.2: a connection into inlet 5 is accepted; pdbuild's
`OBJECT_IO` checks it against Pd). Liveness ~70 short, ~85 long, 100 =
infinite. Higher damping = darker tail. `rev1~`/`rev2~` are cheaper.
**A bare `[rev2~]` or `[rev3~]` is silent** (level defaults to 0 dB in Pd's
scale, i.e. −240 dBFS, measured): always give creation args
(`rev3~ 100 88 3000 20`) or send the level inlet.

`[tabosc4~ t]` needs its table at **2ⁿ+3 points before DSP starts**: create it
as `[table t 2051]`, not `[table t]` resized later by `sinesum` — a shared
loadbang's `; pd dsp 1` can fire first (`error: number of points (100) not a
power of 2 plus three`). An IEM `[hsl]` outputs exactly the float32 it receives
(0.44 in, 0.439999997616 out — the same as a message box).

## Sequencing idioms

Counter: `[metro] → [f ] → [+ 1] → back into [f]'s right inlet`, and `[f] →
[mod N]` for the step index.

Step lookup without arrays: `[sel 0 1 2 … N-1]` → one message box per step →
all into a single `[unpack f f f f]`. Pack several per-step parameters into one
message and remember the **right-to-left** emission order when choosing the
field order.

Gating: `[sel 1]` turns a 0/1 gate into a bang. `[spigot]` passes/blocks a
stream based on a control value — handy for switching between patterns
(`[r pattern] → [== 0] → spigot right inlet`). **A `spigot` defaults to closed**,
so initialize the selector at load.

`mtof` / `ftom` convert MIDI note ↔ Hz. `[random N]` for generative material —
or a deterministic hash of the step index if you want a phrase that *repeats*
and can be re-rolled (vary the multiplier, not just an offset, or you only get
rotations of the same sequence).

**`[random]` must be banged, never handed a float.** A float into its left
inlet *sets the range and fires* (verified: `30 → [random 2]` outputs 22).
The classic trap is a `[moses]` or `[sel]`-branch that forwards its value into
`[random 2]` meaning "pick ±1": you get `random(0..value)` instead, no error,
and a melody that silently drifts to its ceiling. Put `[t b]` between any
value-carrying outlet and a `[random]`.

**`[random]` and `[noise~]` seeds are deterministic by creation order.** Two
renders of the same patch are bit-identical (useful: render twice with one
control changed and diff the audio), but adding *any* `[random]`/`[noise~]`
earlier in the file re-seeds every later one — so a check on "the loudest
partial" or "which note rang longest" can flip between builds for no musical
reason. Measure fundamentals (`f0`) and band shares, not loudest peaks.
**A `seed <n>` message makes a stream independent of creation order**:
`[random]` takes it, and so does `[noise~]` (verified on 0.56.2; seeds are per
object). Send the seed before the first draw: on the first clock tick, or
through a `[t b b]` that orders it first. A seed and a draw fanned out from
one loadbang outlet fire in an order you do not control.

**`[array get name]` / `[array set name]` inlets:** left = bang / float
onset (fires), **middle = number of points** (float, −1 = to the end), right =
the array **name** (symbol). A count sent to the right inlet gives `inlet:
expected 'symbol' but got 'float'` — the error names the inlet's type, which
is the fastest way to learn a multi-inlet object's layout headless.

**Weighted random choice is one object: `[array random name]`.** Bang it and
it outputs an index with probability proportional to that array's values
(verified: weights `0 1 0 3` → 1009 : 2991 over 4000 draws). Fill a small
array with weights, bang, done — a Markov step or a tempered choice needs no
cumulative-sum loop. `[array quantile name]` is the same with your own 0..1
input. Seeds are per object and deterministic by creation order, like
`[random]`; a `seed <n>` message resets one.

**`[expr]` reads tables and `[value]` cells by name**, which keeps state
machines small: `[expr tune[(ot_i+23)%24] - 6]` reads array `tune` at an
index computed from the `[v ot_i]` cell, with `%`, `if()`, `pow()`, `max()`
all available (verified 0.56.2). Share engine state through `[v name]` cells
and let each `[expr]` read what it needs instead of wiring every value in.
**A multi-expression `[expr a; b; c]` has one outlet per expression and
fires them right to left**, so its outlets can feed a `[pack f f f]` directly
(the hot left inlet arrives last). In a file the separators are `\;`.

**`[file isfile]` does not output 0 for a missing path — it bangs its right
(error) outlet.** Outlet 0 gives `1` for an existing file; a path that does
not exist produces only a bang on outlet 1, so `[file isfile] → [sel 0]`
never fires (verified 0.56.2). Resolve a name next to the patch with
`[file patchpath]` (symbol in → absolute path out). Together: find the next
free `take_NNN.wav` so RECORD never overwrites an earlier take.

## Control routing

`[s name]` / `[r name]` — wireless connections. Prefer these for anything a
control surface touches: it decouples layout from signal flow and makes the
parameter driveable by message (scriptable, and testable headlessly).

A message box `\; name value` sends to `[r name]` without a cord at all.

## ELSE library (external, worth installing)

Porres's ELSE ships ~330 objects. Install: put the `else` folder somewhere and
add it to Pd's **search path** — `-lib else` alone loads the binary but leaves
the individual object files unfindable. On Windows the binaries are `.m_amd64`
(m = Microsoft), path preference lives in `HKCU\Software\Pure-Data\path1`.

**`else/pad`** — an X-Y control surface, the thing vanilla can't do. Creation
args set the coordinate dimension; `width`/`height` messages set pixel size.
Its outlet emits `list <x> <y>` and `click <0|1>` — split with
`[route list click]`, then normalize and clamp the coordinates.

**Lua objects (`.pd_lua`).** ELSE bundles a streamlined pdlua (0.12.23, PUC
Lua 5.4, not LuaJIT). A `name.pd_lua` file beside the patch becomes the object
`[name]`, and it runs in `-batch` and through `pdverify.render(Path)` (verified
2026-09-27, ELSE 1.0-0 rc-14, Pd 0.56.2; the CANTUS brain is a 2,500-line
example). Reach for it when the logic is real code (rule systems, search,
state machines) that would otherwise be a tangle of `[expr]`, `[until]` and
`[text]`:

```lua
local c = pd.Class:new():register("cn_name")   -- file: cn_name.pd_lua; UTF-8, NO BOM
function c:initialize(sel, atoms) self.inlets, self.outlets = 1, 1; return true end
function c:in_1_float(f) self:outlet(1, "float", { f * 2 }) end
```

Facts that bite (all measured):
- **Loading ELSE needs the `#X declare -lib else;` record** right after
  `#N canvas`, *plus* the `[declare -lib else]` box (Pd rebuilds the record
  from the box on save). A box alone does **not** load ELSE, so the class
  "couldn't create". An `[else]` object box works only if it comes before the
  Lua object. pdbuild emits only the box: insert the record into the text.
- **Lua runtime errors do not fail a strict render**: Pd prints
  `error: lua: dispatcher: <file>: <line>: <msg>` and exits 0. Grep the
  console. Syntax errors and `initialize` failures do fail ("couldn't create").
  An error inside a clock callback before it reschedules kills that clock chain;
  reschedule first, and wrap the body in `pcall`.
- **Class names and module names are global to the Pd process**; the first
  file loaded wins, silently. A `.pd_lua` named like a vanilla object is
  ignored. Prefix everything.
- **All pdlua objects share one Lua state**: `math.random` is one shared stream
  (seeded randomly per launch), and **`pairs()` order changes between Pd
  launches** (string hashes are seeded per process). For reproducible output
  use a per-object PRNG and arrays, never `pairs()` on anything that reaches an
  outlet or a log.
- `require` finds a sibling `.lua` module only at the **top level** of the
  `.pd_lua` (`package.loaded[m] = nil` first, so `; pdluax reload` re-reads it).
- Every number from Pd arrives as a Lua **float**: `"D" .. (62.0 // 12 - 1)` is
  `"D4.0"`; convert with `math.tointeger` once at the boundary.
  Numbers crossing an outlet become float32. Format log lines in Lua
  (`pd.post(string.format(...))`); Lua `print()` goes to stdout, not the Pd
  window.
- `pd.Clock` runs in logical time, exactly (`delay`, `set(abs)`, `unset`).
  **Same-time ordering depends on the driver**: pdverify's controls (`[del]`s
  set at load) fire before a clock the object set later for the same ms, but a
  `[qlist]` fires *after* a clock set during its own dispatch. To make a trace
  driver-independent, let each callback re-arm itself once with `delay(0)` and
  act on the second firing, and let input events cancel pending second stages.
- `pd.Receive:new():register(self, "name", "method")` and
  `pd.send(name, sel, atoms)` work inside the object; a loadbang init reaches a
  receive registered in `initialize`.

Unverified: pd4web support, and signal (`dsp`/`perform`) methods.
