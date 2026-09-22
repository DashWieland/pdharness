# Lessons

Every lesson from every field test, 2026-07 to 2026-09, by theme. Each one
cost at least an iteration; several cost a day. The instruments they came
from: an emotion wheel of one-shot voices, a morph pad, a choral break
slicer, a Gnawa/maqam trance rig (lila_rig), its two-family successor
(ember), the six-dial meditation instrument (tend), and a mic-driven
harmoniser (halo).

## A. Perception: measuring what you cannot hear

1. **Measure the thing that can move.** Whole-render fields (`dominant_hz`,
   `top_partials`, a spectral fingerprint) answer "what is this sound," not
   "did my change do anything." When a check keeps failing, ask what
   measurand would move if the feature worked, and measure that: a windowed
   RMS, a band share, an onset in a window, a pitch sequence.
2. **Spectra are blind to note order.** A timbre fingerprint of a melody
   played forwards and backwards is the same. Proving a tune changed means
   comparing pitch content per onset (`pitch_sequence`, `top_partials` per
   window), never similarity.
3. **`pitch_hz` (f0) for "rooted on", never `dominant_hz`.** In a riff the
   loudest partial is whichever note rang longest. Worse, Pd's `random` and
   `noise~` seeds are fixed by creation order, so adding an object earlier in
   the file re-seeds everything after it and a "loudest partial" check flips
   between builds for no musical reason.
4. **The onset detector has a global floor.** `onset_count` uses a fraction
   of the render's peak envelope, so a quiet answering voice, a shaker
   between drum hits, or a note after a long gap is invisible however
   clearly it sounds. Use a level rise in a short window after a known time
   (`rise_events`), or solo the voice.
5. **Solo every voice by injection.** "The whole patch makes sound" hid a
   silent oud inside a sounding rig. Mute the other buses with controls and
   check each voice on its own bed.
6. **Differential measurement for effects.** Two renders with identical
   notes differ only by the effect (seeds are deterministic). A per-window
   1/3-octave difference showed a phaser's notches walking 400 Hz to 8 kHz
   where fingerprint similarity barely moved (0.917).
7. **A quiet partial needs a band share.** `top_partials` is a top-10 list;
   a partial at 0.28 of a drone's saws never makes it. Power within 3 % of
   the frequency as a share of the window did (−55 dB absent, −17 dB
   present).
8. **The startup window lies.** Loadbang defaults sound until injected
   values land (about 0.1 s), so a peak-based silence check fails spuriously.
   Skip the first 0.5 s, or analyse a window.
9. **A recall restores everything, so measure something invariant to the
   rest.** A scene check that compared level broke because the scene also
   reopened other buses; centroid survived. When a control is a scene, the
   bed changes under it.
10. **Let the engine testify.** When audio cannot settle a claim (did the
    pad land on the bar? did the tune re-seed?), a `[print]` of internal
    state is cheap, harmless in use, and exact. pdverify captures the
    console; read it.
11. **Measure the bus, not the voice.** Two vanilla ladder filters at
    nominal 20 kHz shaved everything above 8 kHz off a shaker nobody could
    hear. A system effect no single-voice reasoning predicted; one render of
    the bus found it.
12. **Verify sweeps, not endpoints.** The first tend verified 49 static
    corners and played badly: every failure was in motion. A dial scanned
    end to end must not step more than 10 dB in a second and must move its
    one measurand. This contract is what found a filter whose entire action
    sat in a tenth of its travel.

## B. Construction: Pd facts that cost time

13. **GUI controls emit nothing at load.** A toggle, slider, radio or number
    box holds a value and sends nothing until touched, so gains sit at 0 and
    gates stay shut, with no error. Initialise every one something depends
    on (`Patch.init`). Three separate builds rendered silent for this.
14. **Floatatom slots: 8 is receive, 9 is send.** Verified against the
    runtime, not a document. `send` makes typing in the box do something;
    `receive` makes it display. Crossed, the box looks wired and is inert,
    and no render can tell. A gatom with a receive set has **no inlet**: set
    the receive field or wire `[r name]` into it, never both.
15. **A reference you never tested is not evidence.** A "bug" in py2pd's
    symbol atom was chased for two hours because the skill's field table was
    backwards. For any field-order or binding question, probe the runtime
    with a five-line patch, then fix the reference.
16. **Dollar signs in files are `\$`.** Unescaped ones evaluate at load to 0
    with `argument number out of range`. Commas in `expr if(a, b, c)` need
    `\,` like message boxes. pdbuild escapes both, idempotently.
17. **`[array get]` inlets: left bang/onset, middle count, right array
    name.** A count on the symbol inlet is a load-time error that reads
    "inlet: expected 'symbol'," which is exactly the diagnosis.
18. **`[change]` has one inlet**; set it with `set $1`. py2pd's arity check
    catches this at build time, before any render, which is the earliest a
    construction error has ever been caught here.
19. **A `[f]` fed only on its cold inlet never speaks.** Store through the
    hot inlet on the trigger outlet that fires after the comparison.
20. **Attack and release are `[slop~]`, not `[line~]` on hop-rate targets.**
    Release exponential; a squared follower halves the release constant.
21. **An init is not a move.** A dial whose value glides (`[pack f 2000]`
    into `[line]`) must not glide on its own loadbang: the `[line]` re-sends
    every grain for the whole ramp and overrides every direct set of the
    destination for two seconds. Put `[change <default>]` before the glide,
    or init the target directly.
22. **A latch must learn direct sets.** A pad that stores a pending value
    and emits it on the bar reverts anything set directly (a scene, a test)
    on the next bar unless the direct receive also feeds the pending store.
23. **Start a sweep at the floor.** A scan that opens by jumping from the
    default to the low end fails its own continuity test on the first event.
24. **A test bed pins only the internals its question needs.** Two controls
    sent at the same instant to the same receive give whichever was sent
    last; a bed that pinned `vary 0` for timing checks silently switched the
    drift control off in the drift check. A macro under test never shares a
    bed with a pin on one of its own bindings.
25. **Bind the expert path to the pulse, not the surface.** Keep internal
    receives even when a macro owns them, so the engine and the macro layer
    stay separately testable.
26. **Comments take a connection index.** Every `#X` element counts; forget
    a comment and every later connection is wrong. (pdbuild owns this.)
27. **Run the layout check in the build.** A pad row placed at a fixed offset
    under a column collided with the column after it grew;
    `preview.overlaps()` found five collisions, but only because someone
    called it by hand.

## C. Design: what "playable" turned out to mean

28. **Legibility beats breadth.** Five bundled macros, each moving several
    unlike things, made a surface where "the only right way to play it is
    not to touch it." The rework that fixed it kept six dials that each do
    one audible, monotonic thing with both ends musical, and moved every
    discrete change to pads that land on the bar. Fewer controls is not the
    goal; legible controls are.
29. **A dial earns its place** only if one turn is one thing you can hear at
    once, the effect is immediate and monotonic, and both ends are still
    music. Discrete moves are pads, and they wait for the bar so the change
    is a musical event, not a hiccup.
30. **No scale morphs on the surface.** In-between scales are detuned
    versions of both neighbours; nobody untrained can hear a mode switch as
    anything but wrongness, and testers were "nervous to touch it." Fix the
    mode; make it good.
31. **Quantise touches, or drop them.** A free note inserted off the grid in
    a 12/8 groove reads as a plank. Land it on the pulse or the bar.
32. **The axis people love is "how much of the melody is playing."** From
    none (the drums pound quietly) to all, strong beats first. Bury it
    inside a macro and the instrument loses its expressiveness.
33. **Tempo edges are music too.** A range so wide that both ends are
    frantic or dead keeps the player in the bottom quarter. Pick a range
    where the extremes are still something you would leave on.
34. **Note events as one list** (`degree velocity voice startdeg glide`),
    with the voice chosen once per note, is what makes ornaments and
    tremolo re-strike the same string and read as one player, not a chord.
35. **Research the production technique before building an aesthetic.** A
    full build was burned on "granular equals chops"; a ten-minute search
    would have said slicer.
36. **Interaction bugs are invisible to headless audio.** A slider whose
    send and receive are crossed renders exactly like a working one. Read
    the emitted records, and probe the runtime.

## D. Process: how the harness got better

37. **Verification has to be built into the tool, not improvised per patch.**
    Every throwaway analysis script was a signal that pdverify lacked a
    feature.
38. **A helper that prevents a bug must itself be tested,** or the bug just
    moved. Tests that only assert defaults leave the real hole: seventy
    tests and an external review still found dead threshold parameters
    because no test varied a threshold.
39. **Measured claims beat confident ones.** Prove a port with a similarity
    render, prove a dependency swap with an A/B, prove a namespacing fix with
    the positive control that the un-fixed case really does print `multiply
    defined`.
40. **The claw hammer.** A library module promoted from an early instrument
    carried that instrument's bug into the next one, because the next
    builder trusted it. Audit every module against this instrument's needs
    before adopting it, and write which were adopted, which rejected, and
    why, in the field log.
41. **Write the threshold's reason next to it.** A "never bad" window of
    −50 dBFS at the far dim corner is a design decision; the comment saying
    why is what makes the contract meaningful.
42. **An instrument that listens needs a real input round** before its
    participant section means anything: a phone recording of someone
    humming, saved next to the patch, is the corpus's one real file.
43. **The field log is the compounding asset.** The same lesson ("measure
    the thing that can move," "spectra are blind to note order") recurred
    across instruments and only stopped costing time once it was written
    down and read by the next session. Every instrument should make the
    harness stronger: flag the lesson, fix the knowledge, hand the library
    work to another agent, keep building.

## E. The browser

44. **The manifest earns its keep.** A face generated from the control
    manifest, end words and pad kinds included, needed no hand edits.
45. **Parity is a render, not a diff.** A web patch differing from the
    original in three lines and one abstraction is trusted because both
    render to similarity 1.000, not because the diff looks small. Gate every
    transform the same way.
46. **pd4web facts:** register callbacks only after `openPatch`; bang
    callbacks take one argument; float creation arguments to `[clone]` are
    mistaken for abstraction names (pass integers); the runtime needs
    cross-origin isolation headers; `netsend`/`netreceive` fail harmlessly.
