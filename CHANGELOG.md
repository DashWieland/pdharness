# Changelog

pdharness's `main` branch is what `uv tool install` gives a participant, so
every push to it is a release. The version below must match `pyproject.toml`,
`src/pdharness/__init__.py` and `.claude-plugin/plugin.json`, and a test
checks that.

## 0.3.0 (2026-10-25) — agents on their own, and files to deliver

What the first run from an agent runtime other than Claude Code tripped on:
cold shells, no person to play the result, a skills folder elsewhere. And
what its first real job needed, which the kit could not do: files to deliver
(seamless loops, a lift near the end, a level, audible on a phone).

- **One Pd per process, and the line to persist it.** `doctor` (CLI and MCP)
  reports the Pd binary it settled on (`pd`), how pdverify's discovery found
  it (`pd_source`, `pd_found_by`: `PDVERIFY_PD`, PATH, a default install
  location, a portable copy under `tools/`), a warning when `PDVERIFY_PD`
  names a missing file, and `pd_persist`, ready-to-paste `PDVERIFY_PD` lines
  for POSIX shells, PowerShell and Windows `setx`. The Pd comes from
  pdverify's own `discover()`. Every render the server makes uses that same
  binary, and every script `run_script` starts gets it as `PDVERIFY_PD`, so
  doctor and a render cannot disagree within one server process. `doctor` also
  prints the kit's Python executable, and `pdharness doctor --json` prints the
  report as JSON.
- **`pdharness run <script> [args]`**, the CLI's `run_script`: runs a build
  script with the kit's interpreter and `PDVERIFY_PD` set, and streams its
  output. `pdharness run -m pdverify analyze <patch> --dur 6` runs a module, so
  a shell-only agent has the ears too. **`pdharness field-log <slug>`** is the
  CLI's `field_log_stub`.
- **The README's tool table says which surface each tool is on**: MCP, CLI
  or both, with the CLI name beside the MCP name.
- **`new` no longer nests `instruments/instruments/`.** `new` (CLI) and
  `new_instrument` (MCP) take their directory as the project root, report
  `project_root` and the `layout` before writing (`--dry-run` / `dry_run`
  writes nothing), and keep the instrument and its field log in the same root.
  Given a folder named `instruments/`, or an instrument folder inside one,
  they use the folder above and say so in `note`. `--exact-dir` / `exact_dir`
  turns that off. `field_log_stub` finds the root the same way.
- **The interpreter policy is written down.** The README installs with
  `uv tool install --python 3.14`, the version the tests run on. It explains
  that without `--python` uv floats to the newest Python. `requires-python`
  stays `>=3.13`, with no upper bound.
- **`install-skill --target DIR`** installs the skill into any skills folder
  (as `DIR/pure-data`). **`install-skill --print`** writes every file of the
  skill to stdout between `===== FILE: <path> =====` markers, for a runtime
  to file itself.
- **A field log for unattended agent runs.** `field_log_stub`,
  `new_instrument`, `pdharness new` and `pdharness field-log` take
  `participant="agent"` (CLI: `--participant agent`). The log starts from the
  new `field_test/AGENT_LOG_TEMPLATE.md`. The participant is the runtime and
  the session is one task. The date, the kit's versions, the Python version
  and the Pd are filled in (a path under the home folder shows as `~`), and the playability section is a table of `probe_patch`
  results, with a section on friction between the kit and the runtime. The
  human template, which is synced from the harness, is unchanged.
- The scaffold's build script says to run it with `pdharness run`, since a
  plain `python` may not have pdbuild.
- **`render_patch`** (MCP) writes a file to use somewhere: a take of
  `duration`, or with `loop` a seamless loop of exactly that length (pdverify
  0.5.0's `make_loop`; the result reports the seam). `rms_dbfs`/`peak_dbfs`
  set the level with one gain, never a limiter, and `sr` and `bits` (16/24)
  set the format. `expectations` are scored on the file as written. A family
  of files is a loop in a build script; the kit adds no batch format.
- **`verify_patch` scores a `.wav` as it is** (QA a delivered file), and
  knows pdverify 0.5.0's `seamless`, `band_level` and `change`. `within`
  takes `[t0, null]`, and negative times count from the end, as control `at`
  times now do too: one score fits every length.
- **doctor remembers the Pd that passes** (pdverify 0.5.0's `remember`), so a
  cold shell, a build script or another client finds the same binary with no
  environment variable. `pd_remembered` names the file; `remember=false` /
  `--no-remember` leaves no trace. Tests keep it in a temp dir.
- **Bank: a second worked example, `examples/drift/`**, a small self-playing
  ambient bed composed from pdbuild 0.10.0's ambient modules (scale_walk,
  pluck, drone, noise_bed, reverb). Six dials, five claims (DENSITY counted
  by a probe, BRIGHT with the air isolated, LIFT from one end-relative score
  at 19 and 30 s), and a `deliver()` that renders a family of loops and cuts
  at 48 kHz/24-bit and scores each file. `modules/CATALOGUE.md` lists the
  ambient tier.
- **Bank:** a new `guides/SETUP.md` (the agent's needs and the person's, installing Pd
  where it stays, a project under git, the loop between them), linked from the
  start page and the README; a new `guides/DELIVERING.md` (loops, arcs, level, small speakers,
  a family of takes), `render_patch` on the start page, and lessons 47-52
  ("Delivering a file").

## 0.2.2 (2026-09-26) — pdbuild v0.9.1, py2pd 11baaf2

- Pins pdbuild v0.9.0 -> v0.9.1.
- Pins py2pd c04d778 -> 11baaf2.
- pdbuild 0.9.1: `Patch.load` reads graph-on-parent arrays back (one made in Pd's GUI keeps its saved contents); extract sees control-rate table uses; `[del]`, `[table]` and every `[list]`/`[array]` verb have checked inlet and outlet counts (`[list split]` has 3 outlets).
- py2pd fork 11baaf2: graphs and `#A` data parse and re-save exactly; `#X coords` is written the way Pd writes it, so a graph-on-parent subpatch asked to hide its name now does.
- The bank's copy of pdbuild's README is the v0.9.1 one, which says graphs load back.

## 0.2.1 (2026-09-26) — pdbuild 0.9.0

- Pins pdbuild v0.8.0 -> v0.9.0.
- pdbuild 0.9.0: `Patch.graph()` draws a graph-on-parent array a player can watch (locked against mouse edits); a multi-expression `[expr a; b]` gets one outlet per expression; `surface.record_takes()` records numbered takes that never overwrite an earlier one.
- The bank follows pdbuild 0.9.0. The cookbook and the pdbuild README are
  the v0.9.0 versions, and the module catalogue now lists `record_takes` and
  `patch.graph`.
- The skill corrects two facts, both verified in Pd 0.56.2:
  - `$0` in a message box is `0`, not the instance id, so
    `[; $0-freq 440(` goes to a global `0-freq`. `[f $0]` → `[; $1-freq 440(`
    reaches `[r $0-freq]`.
  - `[rev3~]` has 6 inlets, not 2.

## 0.2.0 (2026-09-26) — mcp 2

- The server runs on mcp 2: `MCPServer`, the renamed `FastMCP`. The dependency
  is now `mcp>=2.2,<3`, which lifts 0.1.1's `<2` cap.
- Knowledge documents in subfolders now resolve as resources, because the
  template is `knowledge://{+path}`. Until now `knowledge://skill/SKILL.md` and
  `knowledge://lessons/LESSONS.md`, the documents the server's instructions
  send agents to first, failed with "Unknown resource". Only top-level
  documents and the `knowledge_read` tool worked.
- `verify_patch` now lists `f0` and `harmonic_series` (pdverify 0.4.0) among
  its expectation names.
- Every dependency now has an upper bound. The tests fail when a dependency
  lacks one, when a git dependency names a branch, or when the four version
  strings disagree.
- The bank's copy of the skill has caught up with the live skill. Its
  `references/objects.md` now covers:
  - Chebyshev waveshaping, for exact harmonics from a sine;
  - why a tempo-synced delay must not slide its taps;
  - `[array random]` as a weighted choice;
  - `[expr]` reading tables and `[value]` cells, and giving one outlet per
    expression;
  - `[file isfile]` banging its right outlet for a missing path.

## 0.1.1 (2026-09-26) — pinned

- pdverify, pdbuild and the py2pd fork are pinned to release tags (`v0.4.0`,
  `v0.8.0`) and to a commit, where they used to follow `@main` or a branch. An
  install now changes only when a pin does. This release ships pdverify 0.4.0
  (harmonicity, sweep_steps).
- `mcp<2`. A fresh install of 0.1.0 resolved mcp 2.2.0, which renamed
  `FastMCP`, so `pdharness serve` did not start. `doctor` still passed.

## 0.1.0 (2026-09-22) — the bring-your-own-agent kit

- The MCP server, with the tools `doctor`, `analyze_patch`, `verify_patch`,
  `compare_patches`, `probe_patch`, `run_script`, `new_instrument`,
  `list_modules`, the knowledge tools and `field_log_stub`.
- The knowledge bank, the Claude Code plugin and STUDY.md.
