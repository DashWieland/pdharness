# pdharness

Bring your own agent to Pure Data instrument building.

An MCP server that gives any agent **ears** (render a patch headless and
say what it sounds like), **hands** (a verified library of Pd parts and a
build-script scaffold), and **the knowledge** that took a harness eleven
instruments to accumulate: the semantics, the gotchas, and the lessons.

The premise: someone describes an instrument in plain language, an agent
builds it, they play it. A blind agent with good tools got 8 of 12 simple
tasks right. The same tools plus this bank built a 3000-line two-family
trance rig in an afternoon. The bank is the difference, and it is what this
package ships.

## What you need

- **Pure Data** (vanilla, 0.54 or later) on your PATH, from
  [puredata.info](https://puredata.info). The ELSE library is optional;
  `doctor` says whether it is found.
- **Python 3.13 or later** (3.14 is what the tests run on) and
  [uv](https://docs.astral.sh/uv/) (or pip).
- **An agent.** One that speaks MCP gets the server; Claude Code is the
  tested client. One that only has a shell gets the same loop from the CLI.

## Install

```bash
uv tool install --python 3.14 git+https://github.com/DashWieland/pdharness
pdharness doctor
```

If the shell says `pdharness` is not found, uv's tool directory is not on
your PATH yet: run `uv tool update-shell`, open a new terminal, try again.

`doctor` renders a one-second sine through your Pd and reports whether it
heard an A4. If it did, everything works. The three harness packages
(pdverify, pdbuild and a patched py2pd) are pulled from git by the install,
pinned to tagged releases; none is on PyPI yet.

**Which Python.** The dependencies are pinned, but the interpreter is not.
Without `--python`, uv picks the newest Python it has or can download, which
may be newer than anything the tests have run on. `--python 3.14` asks for
the version the tests run on, so every participant runs the same kit.
`requires-python` is `>=3.13` (py2pd needs 3.13) with no upper bound,
because nothing yet shows a newer Python breaking it. `doctor` prints the
version you got, and the field log records it.

**Which Pd.** `doctor` prints the Pd binary it settled on, how it found it
(`PDVERIFY_PD`, PATH, a default install location), and the lines that make
every shell find the same one:

```
pd                 /usr/local/bin/pd
pd_found_by        `pd` on PATH
  POSIX sh/bash/zsh:           export PDVERIFY_PD=/usr/local/bin/pd
  PowerShell, this session:    $env:PDVERIFY_PD = '/usr/local/bin/pd'
  Windows, every new shell:    setx PDVERIFY_PD "/usr/local/bin/pd"
```

The MCP server renders with that Pd, and `run_script` and `pdharness run`
pass it to the scripts they start. A build script run any other way does
its own lookup, so if your shell starts cold for every command, set
`PDVERIFY_PD` or use `pdharness run`. `pdharness doctor --json` gives the
same report as JSON.

Register the server with your agent:

```bash
claude mcp add --transport stdio --scope user pdharness -- pdharness serve
pdharness install-skill      # optional: the pure-data skill into ~/.claude/skills
```

Any other MCP client: `pdharness mcp-config` prints the JSON.

If your agent keeps its skills somewhere else, `pdharness install-skill
--target <skills folder>` installs the skill as `<skills folder>/pure-data`.
`pdharness install-skill --print` writes every file of the skill to stdout,
between `===== FILE: <path> =====` markers, for the agent to file itself.

Or, as a Claude Code plugin (skill and server together):

```bash
/plugin marketplace add DashWieland/pdharness
/plugin install pdharness@pdharness
```

## Use

In a directory you want the instrument in, ask your agent for one:

> Build me an instrument that sounds like rain on a tin roof that I can
> speed up and slow down.

The server's instructions tell the agent to read the bank, scaffold a build
script, compose from verified modules, render after every change, verify
each claim, probe the interaction, and hand back a `.pd` you can open in
Pd, a demo `.wav`, and a README. The MCP prompt `build_instrument` is the
same procedure, if your client supports prompts.

From a shell, with or without an agent, the parts are the same:

```bash
pdharness knowledge                     # the bank's index
pdharness knowledge lessons/LESSONS.md  # one document
pdharness new rain_roof "rain on a tin roof I can speed up"   # a build script that already passes
pdharness run instruments/rain_roof/build_rain_roof.py        # build -> verify -> demo .wav
pdharness run -m pdverify analyze instruments/rain_roof/rain_roof.pd --dur 6   # the ears
```

`pdharness run` uses the kit's own Python, the one that has pdbuild and
pdverify. After a `uv tool install`, a plain `python` usually has neither.

`pdharness new` works in a **project root**. It prints the layout before
it writes anything (`--dry-run` stops there):

```
<project>/instruments/rain_roof/build_rain_roof.py
<project>/instruments/rain_roof/README.md
<project>/field_tests/<date>_rain_roof.md
```

Run it from a folder named `instruments/`, or from an instrument folder
inside one, and it uses the folder above as the project root, so the
instrument and its field log stay in one tree. `--exact-dir` turns that
off.

**Unattended runs.** When an agent builds on its own and no person will
play the result, `pdharness new ... --participant agent` (MCP:
`participant="agent"`) writes a field log in which the agent runtime is the
participant and the session is one task. It fills in the date, the kit and
the Pd itself, and asks for playability from `probe_patch` results instead
of a person's hands.

## The tools

The MCP server and the CLI share one implementation, but not every tool has
both shapes. **both** means the same tool under two names.

| MCP tool | CLI | Surface | What it is |
|---|---|---|---|
| `doctor` | `pdharness doctor [--json]` | both | can this machine build and hear? Which Pd, found how, and its `PDVERIFY_PD` line |
| `new_instrument` | `pdharness new <slug> "<description>"` | both | a build script that already builds, verifies and renders, and its field log |
| `run_script` | `pdharness run <script> [args]` | both | run a build script with the kit's interpreter and its Pd |
| `analyze_patch` | `pdharness run -m pdverify analyze <patch> --dur 6` | MCP; CLI through pdverify | the ears: description, integrity, pitch, level, timbre, onsets, rhythm |
| `verify_patch` | | MCP | claims as checks: pitch, note, level, onsets, percussive, brighter_than, repeats, ... From a shell, the build script's `verify_patch()` is the same check. |
| `compare_patches` | | MCP | similarity between two renders |
| `probe_patch` | | MCP | the interaction check: `[print]` taps on receives while controls are played in |
| `list_modules` | `pdharness knowledge modules/CATALOGUE.md` | both | the verified parts |
| `knowledge_index`, `knowledge_read` | `pdharness knowledge [path]` | both | the bank, for clients without resources |
| `field_log_stub` | `pdharness field-log <slug> [--participant agent]` | both | the log every build writes |
| | `pdharness install-skill [--target DIR or --print]` | CLI | the pure-data skill, into a skills folder or to stdout |
| | `pdharness serve`, `pdharness mcp-config` | CLI | run the server; print how to register it |

MCP resources: `knowledge://index` and `knowledge://<path>`. MCP prompt:
`build_instrument`.

## The deal

The bank got good because every build wrote down what it learned and the
next build read it. Use it for free; send the field log back, anonymised,
so the next agent starts where yours finished. See
[STUDY.md](STUDY.md) for the study this package exists to run.

## Development

```bash
git clone https://github.com/DashWieland/pdharness && cd pdharness
uv venv && uv pip install -e ".[dev]"
python -m pytest tests -q
```

The knowledge bank lives in `src/pdharness/knowledge/`. `skills/pure-data/`
is a copy of `knowledge/skill/` for the Claude Code plugin; a test keeps
them identical.

`main` is what `uv tool install` gives a participant, so every push to it is a
release. Dependencies are pinned so that an install changes only when
`pyproject.toml` does: pdverify and pdbuild to release tags, the py2pd fork
to a commit, and everything else with an upper bound.

To release:

1. Tag the library change in its own repo, once its tests (and pdverify's
   CI) are green.
2. Bump the pin here.
3. Bump the version in `pyproject.toml`, `src/pdharness/__init__.py`,
   `.claude-plugin/plugin.json` and `CHANGELOG.md`.
4. Run the tests in a fresh environment.
5. Push, between participants, so that each field log names one kit.

The tests fail if the four version strings disagree, if a dependency has no
upper bound, or if a git dependency follows a branch.

## Credits

Pure Data by Miller Puckette. [pdverify](https://github.com/DashWieland/pdverify)
and [pdbuild](https://github.com/DashWieland/pdbuild) by Dash Wieland;
[py2pd](https://github.com/shakfu/py2pd) by shakfu. MIT.
