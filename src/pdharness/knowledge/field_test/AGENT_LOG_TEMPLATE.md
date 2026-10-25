# Field test (unattended agent run): <slug>

An agent ran this build on its own. The participant is the agent runtime, the
session is one task, and no person played the result. Playability is answered
from `probe_patch` and `verify_patch`, not from a person's hands, so say plainly
what that leaves unknown.

- **Date:** <date>
- **Participant (runtime):** (agent runtime and model; who set the task, as a role)
- **Session:** one task. (MCP or CLI; how commands run: persistent shell or
  cold per command; sandbox, audio device, network; anything unusual)
- **Kit:** <kit>
- **Pd:** <pd>

## The task

> (the task as given, verbatim)

What the runtime had to decide alone, with no one to ask:

## Claims

The 3 to 6 claims the description became before anything was built. Each one
is a check below.

| # | Claim | Check (`verify_patch` expectation or `probe_patch` watch) | Passed? |
|---|---|---|---|
| 1 | | | |

## Build narrative

For each render iteration:

| # | What changed | pdverify verdict (summary line + integrity) | Kept? |
|---|---|---|---|
| 1 | initial build | | |

- **Wall clock:** task → first non-silent render: ___ ; → done: ___
- **Silent/broken renders:** ___ of ___ iterations (cause of each)
- **Commands or tool calls that failed or surprised:** (what, the error, the
  workaround)
- **Objects / files in final instrument:**

## Result

- **Final artifacts:** `instruments/<slug>/`: build script, `.pd`, demo `.wav`
- **pdverify's final description:**

## Playability, from the probe (no human hands)

One row per control a person would touch. Drive its `_ui` receive the way a
hand would (`controls`), watch what it should reach (`watch`), and say what
the tap printed and what the audio did.

| Control | Driven (receive, value, at) | Watched receive(s) | What the tap printed | Audible effect (`verify_patch`) | Verdict |
|---|---|---|---|---|---|
| | | | | | |

- **Initialised at load:** with no controls played in, which receives print a
  value? Anything downstream of a control that prints nothing is silent until
  someone touches it.
- **Sweeps:** each continuous control at several values across its range. Does
  the one thing it moves move, without the level jumping?
- **What the probe cannot tell:** feel, whether a range is musical rather than
  merely working, the canvas layout, anything only a hand finds. List what a
  person should try first when they open the `.pd`.

## Intent gap analysis

Where meaning was lost, if anywhere. Classify each gap:

- **Vocabulary** (the task's words → synthesis choices):
- **Perception** (pdverify couldn't hear the quality that mattered):
- **Construction** (knew *what* to change, not *how*):

## Friction with the kit

Where the kit assumed something about the agent that did not hold here: shell
state, paths, where skills live, a person at the machine. What the runtime did
instead.

## Lessons

What should change in the harness because of this run. For each lesson, name
the tool it belongs in (pdverify, pdbuild, pdharness, the skill, the bank) and
the API shape you would want:
