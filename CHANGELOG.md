# Changelog

pdharness's `main` branch is what `uv tool install` gives a participant, so
every push to it is a release. The version below must match `pyproject.toml`,
`src/pdharness/__init__.py` and `.claude-plugin/plugin.json`, and a test
checks that.

## 0.2.1 (2026-09-26) — pdbuild 0.9.0

- Pins pdbuild v0.8.0 -> v0.9.0.
- pdbuild 0.9.0: `Patch.graph()` draws a graph-on-parent array a player can watch (locked against mouse edits); a multi-expression `[expr a; b]` gets one outlet per expression; `surface.record_takes()` records numbered takes that never overwrite an earlier one.

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
