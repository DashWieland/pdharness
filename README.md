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
- **Python 3.13 or later** and [uv](https://docs.astral.sh/uv/) (or pip).
- **An agent that speaks MCP.** Claude Code is the tested client.

## Install

```bash
uv tool install git+https://github.com/DashWieland/pdharness
pdharness doctor
```

`doctor` renders a one-second sine through your Pd and reports whether it
heard an A4. If it did, everything works. The three harness packages
(pdverify, pdbuild and a patched py2pd) are pulled from git by the install;
none is on PyPI yet.

Register the server with your agent:

```bash
claude mcp add --transport stdio --scope user pdharness -- pdharness serve
pdharness install-skill      # optional: the pure-data skill into ~/.claude/skills
```

Any other MCP client: `pdharness mcp-config` prints the JSON.

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

Without an agent, the parts are still useful:

```bash
pdharness knowledge                     # the bank's index
pdharness knowledge lessons/LESSONS.md  # one document
pdharness new rain_roof "rain on a tin roof I can speed up"   # a build script that already passes
python instruments/rain_roof/build_rain_roof.py
```

## The tools

| Tool | What it is |
|---|---|
| `doctor` | can this machine build and hear? |
| `new_instrument` | a build script that already builds, verifies and renders |
| `run_script` | run a build script with the right interpreter |
| `analyze_patch` | the ears: description, integrity, pitch, level, timbre, onsets, rhythm |
| `verify_patch` | claims as checks: pitch, note, level, onsets, percussive, brighter_than, repeats, ... |
| `compare_patches` | similarity between two renders |
| `probe_patch` | the interaction check: `[print]` taps on receives while controls are played in |
| `list_modules` | the verified parts |
| `knowledge_index` / `knowledge_read` | the bank, for clients without resources |
| `field_log_stub` | the log every build writes |

Resources: `knowledge://index` and `knowledge://<path>`.

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

## Credits

Pure Data by Miller Puckette. [pdverify](https://github.com/DashWieland/pdverify)
and [pdbuild](https://github.com/DashWieland/pdbuild) by Dash Wieland;
[py2pd](https://github.com/shakfu/py2pd) by shakfu. MIT.
