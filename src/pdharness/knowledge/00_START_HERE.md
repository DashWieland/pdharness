# Start here

You are about to build a Pure Data instrument for a person who described it
in plain language. This bank is everything a harness learned doing exactly
that, eleven instruments in: the tools, the semantics, the lessons, and the
deal. Read this page fully. Then read `skill/SKILL.md` and
`lessons/LESSONS.md`. Everything else is reference for when you need it.

## The iron rule

**You cannot hear a patch by reading it.** A Pd patch that loads without
errors is not a working patch; it is an untested hypothesis. It can be
silent, an octave off, clipping, or NaN, and look perfectly fine. So the
loop is always **build, render, analyze, iterate**, and you never report a
patch as working until `analyze_patch` has rendered it and the report
matches the intent.

## The tools (the MCP server)

| Tool | What it is |
|---|---|
| `doctor` | can this machine build and hear? Run once. |
| `new_instrument` | a build script that already builds, verifies and renders. Edit from it. |
| `run_script` | run a build script with the interpreter that has pdbuild and pdverify. |
| `analyze_patch` | **the ears.** Render, then a description, integrity, pitch, level, timbre, onsets, rhythm. After every change. |
| `verify_patch` | the claims as checks: `note("A3")`, `onsets(8)`, `percussive()`, `brighter_than(ref)`, `repeats(2.4)`, ... worst first. |
| `compare_patches` | similarity of two renders; 1.000 means a rewrite changed nothing. |
| `probe_patch` | **the interaction check.** Audio cannot see a slider that goes nowhere; a `[print]` tap on a receive can. |
| `list_modules` | the verified parts. Compose before you author. |
| `field_log_stub` | the log you fill in when done. |

The knowledge bank is `knowledge://index` and `knowledge://<path>` as
resources, or `knowledge_read` as a tool.

## How a build goes

1. **Translate the description into claims** you could check by ear before
   building anything: the pitch or key, the rhythm, the timbre words, what
   each control the person will touch does. Three to six claims. Write them
   down; they become `verify_patch` checks and the field log's spine.
2. **Compose before you author.** `list_modules` first. A plucked string,
   a swung clock, a step table, a melody loop, a ladder filter, a dub delay
   already exist and are verified. Write raw Pd only for what does not. Then
   audit: does the module actually do what this instrument needs, or are you
   reaching for the claw hammer because it is the hammer you have? (Lesson
   in `lessons/LESSONS.md`, "the claw hammer".)
3. **Author with pdbuild, never by hand.** `.pd` connections are declared by
   object index; hand-writing them breaks on the first insert. The build
   script is the source of truth; the `.pd` is its output.
4. **Make it playable by a human, not only verifiable headless.** Every
   control on the canvas with a `<name>_ui` receive and a `[s name]` twin,
   so a hand, a MIDI map and a test drive the same thing. Everything
   downstream of a control **initialised at load** (`Patch.init`): a GUI
   object emits nothing until touched, and that is the single most common
   cause of a silent patch. Audio on at load.
5. **Render after every change.** Silent, clipped or NaN is a bug, never a
   style. Read the description against the claims. When a claim cannot be
   settled by audio (does the read-out update? did the pad land on the
   bar?), `probe_patch` or let the engine testify with a `[print]`.
6. **Verify the motion, not only the endpoints.** A dial that is fine at both
   ends and unusable in between is the failure that cost the most. Sweep it
   (controls at several `at` times) and check the level does not jump and
   the one thing it moves, moves.
7. **Hand over** the `.pd`, a rendered demo `.wav`, and a README written for
   the player: what each control does, in the person's words where you can.
8. **Fill in the field log.** The request verbatim, every iteration and its
   verdict, where meaning was lost (vocabulary, perception, construction),
   and what the harness lacked. This is the deal.

## The deliverable

```
instruments/<slug>/
  build_<slug>.py     the source of truth: build(), verify_patch(), demo()
  <slug>.pd           opens in vanilla Pd; a person can play it
  <slug>_demo.wav     what it sounds like, rendered
  README.md           for the player
  <slug>.json         optional: the manifest (controls, ranges, defaults, MIDI, events)
field_tests/<date>_<slug>.md
```

## The deal

The harness got good because every build wrote down what it learned, and
the next build read it. You are using that bank for free. In return, the
field log you write goes back, anonymised, and the next agent reads it. If
you found a measurand pdverify lacked, a module that should exist, a wrong
fact in the skill, say so in the log's Lessons section, naming the tool it
belongs in and the API shape you would want.

## Attribution and care

Instruments here draw on real musical traditions (a Gnawa-derived 12/8, a
maqam with a quarter tone). Build from listening, say so in the README, and
never present a fusion made by outsiders as the tradition itself. Do not
borrow ceremonial or religious material for atmosphere.
