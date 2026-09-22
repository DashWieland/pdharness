# tend — design note (the rework, 2026-09-13)

The pared-down instrument that came out of lila_rig and ember. It plays
itself; you steer. Built for long, unhurried sitting, and for giving someone
authorship of music without musical vocabulary.

The first tend (five macros, a continuous scale morph, note insertion)
verified 49/49 and played badly: "the only right way to play it is to not
touch it at all." Each macro moved several unlike things at once, so no
gesture had one audible meaning; the in-between scales were detuned versions
of both neighbours; the axis Dash loved, how much of the melody plays, was
buried; inserted notes landed off the grid. This note is the rework.

## The rule

**The dials are the instrument.** A dial earns its place only if one turn is
one thing you can hear at once, the effect is monotonic and immediate, and
both ends are still music. Discrete moves are not dials: they are pads, and
they land on the next bar (or the loop's end) so the change is a musical
event, not a hiccup. Nothing on the surface asks you to know which scale is
nice: the mode is one, chosen and fixed. Fewer controls is not the goal;
legible controls are.

## The surface — the whole manifest

| Dial | One thing | Inside |
|---|---|---|
| TEMPO | slow → fast | 110–190 BPM; the dial is a destination and the band glides there over 2 s (`[line]` into `tempo_now`), so a quick turn reads as the music speeding up |
| DENSITY | none of the melody → all of it | the loop's priority mask: strong beats first, thinned steps become holds; 0 is no melody at all |
| MUTATE | the tune holds → keeps rewriting itself | the loop's per-pass rewrite probability, scale-aware with gravity |
| FILTER | dark → open | a ladder lowpass dive over the whole dial: 200 Hz and resonant at 0, open at 1. Ember split this dial into a dive and a highpass build; the sweep contract showed the dive's whole action then sat in a tenth of the travel, and the thin end was the least musical edge, so the build went and the dive got the full dial |
| STORM | dry → the dub storm | ember's tempo-synced dub loop: feedback, wet, send, a slight duck at the top; the reverb opens with it |
| DISTANCE | at the fire → over the dune | as in ember: lowpass 20 k→500 Hz, −18 dB, mono, reverb wetter and later, drum buses softened first |

| Pad | Move | Lands |
|---|---|---|
| STUTTER | hold: freeze the last pulse | now |
| KILL LOW | hold: drums and bass out | now |
| PATTERN+ | next groove variant (core, hemiola, roll, skeleton) | the bar's last pulse, so the reset makes the next tick the downbeat |
| INTENSITY+ | sparse / groove / full | the bar's last pulse |
| PHRASE+ | re-seed the tune from the bank | the loop's end |
| DRONE | on / off | now, ramped |
| RECORD | a take | now |

Scenes over OSC: SNAPSHOT / RECALL `<slot>` hold the six dials and DRONE.
Keys on channel 1 remain the expert path (exact degrees, C4 = tonic); the
testers so far never used them.

MiniLab 3: knobs 1–6 = the dials (CC 74 71 76 77 93 18); pads 1–7 = the pad
row (36–42), pad 8 free.

Fixed inside the engine, by measurement: Bayati (D E½♭ F G A B♭ C, the
neutral second at the quarter tone), swing 0.12, ornaments 0.3, the oud / ney
balance (the ney takes the strong notes), the bus levels, reverb 0.35, echo
0.25, the drone's breathing at 0.5. Every one of them is still a receive.

## What the rework removed

FIRE, COLOUR, AIR, DRIFT (the macro layer); the continuous scale morph; the
drone's third; the lead brightness tilt; TOUCH, its chooser and the
answering voice; the groove's self-variation. All of it is in git history
(`c90a679`) and none of it in the engine.

## The four contracts

- **Every corner is safe.** All 64 corners of the six dials plus the centre:
  unclipped, no runaway. Silence is allowed here: FILTER's thin end over
  DISTANCE's far end stacks to nothing, and both dials said "take it away".
  Whether a position is *music* is the next contract's job.
- **Every edge is music.** Each dial at either end with the others at their
  defaults: inside a fixed level window (−50..−8 dBFS; −47 is the band over
  the dune, a whisper by design). Onsets are not required: a full dub storm
  smears every transient and is music. This contract is what removed
  FILTER's highpass end (−48 dBFS, the thinnest edge on the surface).
- **Every dial scanned end to end is a musical move.** The dial sits at its
  floor, rises to its ceiling over six seconds, holds, comes back: no
  1-second level step over 10 dB (silence to sound excepted), and the dial's
  one measurand moves (the pulse shortens, melody onsets appear, the
  centroid opens, the wash rises, the level recedes).
- **Unattended.** Ten minutes with no input: level-bounded, still a loop,
  and the tune rewritten (read from the engine's own melody print).

These are the checks the first tend lacked: it tested static corners, and
the failure was in motion.

## Build notes

Same build route as before: pdbuild's `Patch` with `surface` and the modules
`swing_clock`, `step_tables` + `gated_value`, `scale_degree`; `melody_loop`
still rejected (see the field log); DSP copied from ember. The pads' cycle
logic and the on-the-bar latches are small hand-built graphs; when the
library agent generalises them, `surface.pad_row` should grow a `land_on`
option.
