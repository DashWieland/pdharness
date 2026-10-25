"""The MCP server: `pdharness serve` (stdio).

Tools are the harness's ears and hands; resources are the knowledge bank; the
one prompt is the build procedure.  Any MCP client can drive it; Claude Code is
the first.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import knowledge, tools

INSTRUCTIONS = """pdharness builds Pure Data instruments you can hear.

The iron rule: you cannot hear a patch by reading it. Never report a patch as
working until `analyze_patch` has rendered it and the report matches the intent.
The loop is build -> render -> analyze -> iterate.

Start cold? Read the resource knowledge://00_START_HERE.md, then
knowledge://skill/SKILL.md and knowledge://lessons/LESSONS.md. Compose from the
verified modules (knowledge://modules/CATALOGUE.md) before writing raw Pd.
`new_instrument` gives you a build script that already builds, verifies and
renders; edit from there. When the instrument is done, fill in the field log
the scaffold created: it is how the harness learns. Running unattended, with
no person to play the result? Pass participant="agent" to `new_instrument`
or `field_log_stub` and answer playability from `probe_patch`.
"""

# keyword arguments only: mcp 2 put title and description before instructions
mcp = MCPServer("pdharness", instructions=INSTRUCTIONS)


# ----------------------------------------------------------------- tools

@mcp.tool()
def doctor(remember: bool = True) -> dict:
    """Check that this machine can build and hear a patch: Pd found, a test render produces
    an A4 sine, pdverify/pdbuild importable, whether ELSE externals are present.  Reports the
    Pd binary it settled on (`pd`), how it was found (`pd_found_by`), and `pd_persist`: the
    PDVERIFY_PD lines (POSIX, PowerShell, Windows setx) that make a fresh shell find the same
    Pd.  Every render this server makes, and every script `run_script` starts, uses that Pd.
    A Pd that passes is remembered (`pd_remembered`), so a cold shell finds it with no
    environment variable; pass remember=false to leave no trace."""
    return tools.doctor(remember)


@mcp.tool()
def analyze_patch(patch: str, duration: float = 6.0, controls: list[dict] | None = None,
                  save_wav: str | None = None, strict: bool = True) -> dict:
    """Render a .pd headless (or read a .wav) and report what it sounds like: a plain-language
    description, integrity (silent / clipped / NaN), pitch, level, spectral character, onsets and
    rhythm, plus any Pd console errors.  `controls` plays values into receives during the
    render: [{"receive": "tempo_ui", "value": 150, "at": 0.5}, {"bang": "nextpattern", "at": 1},
    {"note": 60, "at": 0, "dur": 0.5}].  This is the ears; call it after every change."""
    return tools.analyze_patch(patch, duration, controls, save_wav, strict)


@mcp.tool()
def verify_patch(patch: str, expectations: list[dict], duration: float = 6.0,
                 controls: list[dict] | None = None) -> dict:
    """Render and score against named expectations, worst first (or score a .wav as it is,
    no render: QA a delivered file).  Each expectation is
    {"name": <pdverify.expect function>, "args": [...], "kwargs": {...}, "within": [t0, t1]?}.
    Names: not_silent, no_clipping, finite, pitch, note, f0, level, tonal, noisy, centroid,
    has_partial, harmonic, harmonic_series, loudest_partial, brighter_than, darker_than, band,
    percussive, sustained, onsets, stereo, dynamic, steady, ioi, ioi_cv, period, repeats,
    matches_reference, duration, seamless (loops without a click, jump or crossfade dip),
    band_level (level in one band: {"args": [250], "kwargs": {"min_db": -12, "relative": true}}
    survives a phone speaker), change (a measure moves between two windows:
    {"args": ["level", [0, -4], [-4, null]], "kwargs": {"min": 2}} lifts in the last 4 s).
    Negative times count from the end, in `within`, in `change` windows and in control `at`.
    Use it to turn every claim about the instrument into a check."""
    return tools.verify_patch(patch, expectations, duration, controls)


@mcp.tool()
def render_patch(patch: str, out: str, duration: float = 6.0, controls: list[dict] | None = None,
                 sr: int = 44100, bits: int = 16, loop: float | None = None, crossfade: float = 2.0,
                 preroll: float = 4.0, rms_dbfs: float | None = None, peak_dbfs: float | None = None,
                 expectations: list[dict] | None = None) -> dict:
    """Render a patch to a .wav file to use somewhere (a video, a game, a set): `duration`
    seconds, or with `loop` a seamless loop of exactly `loop` seconds (renders `preroll` +
    loop + `crossfade`, crossfades the overrun onto the head; the result reports the seam).
    `rms_dbfs` / `peak_dbfs` set the level with one gain, never a limiter (the ceiling wins and
    `master.peak_bound` says so).  `sr` and `bits` (16 or 24) set the format.  `controls` as in
    analyze_patch; a negative `at` is seconds before the end, so one score fits every length.
    `expectations` (as in verify_patch) are scored on the file as written.  A family of files
    (several control sets x several lengths) is several calls, or a loop in a build script."""
    return tools.render_patch(patch, out, duration, controls, sr, bits, loop, crossfade, preroll,
                              rms_dbfs, peak_dbfs, expectations)


@mcp.tool()
def compare_patches(candidate: str, reference: str, duration: float = 6.0,
                    controls: list[dict] | None = None) -> dict:
    """Similarity (0..1) between two renders (.pd or .wav) and the moves that would close the
    gap.  1.000 means a rewrite did not change the sound; use it to gate any transform."""
    return tools.compare_patches(candidate, reference, duration, controls)


@mcp.tool()
def probe_patch(patch: str, watch: list[str], controls: list[dict] | None = None,
                duration: float = 3.0) -> dict:
    """The runtime probe for interaction, which audio cannot see.  Adds `[r name] -> [print]`
    taps for each name in `watch` to a copy of the patch, plays `controls` in, and returns what
    each tap printed.  Proves a slider reaches its target, a read-out updates, a pad landed on
    the bar, a latch learned a direct set."""
    return tools.probe_patch(patch, watch, controls, duration)


@mcp.tool()
def run_script(script: str, args: list[str] | None = None, cwd: str | None = None,
               timeout: float = 900.0) -> dict:
    """Run a Python build script with the interpreter that has pdbuild and pdverify installed,
    with PDVERIFY_PD set to the Pd `doctor` reports.  Returns the output tail and the files it
    created or changed.  The CLI equivalent is `pdharness run <script> [args]`."""
    return tools.run_script(script, args, cwd, timeout)


@mcp.tool()
def new_instrument(slug: str, description: str, directory: str | None = None,
                   participant: str = "human", dry_run: bool = False, exact_dir: bool = False) -> dict:
    """Scaffold <project>/instruments/<slug>/ with a build script that already builds a minimal
    playable patch (two sliders with `_ui` receives, initialised), verifies it, and renders a
    demo; plus a README and the field-log stub in <project>/field_tests/.  Edit from something
    that passes.  `directory` (default: cwd) is the project root; given an instruments/ folder,
    or an instrument folder inside one, the folder above instruments/ is used (`note` says so;
    `exact_dir=true` turns that off).  The result lists `project_root` and `layout`.
    `dry_run=true` returns the layout and writes nothing.  `participant="agent"` writes the
    unattended-run field log (the runtime is the participant; playability from probe_patch)."""
    return tools.new_instrument(slug, description, directory, participant, dry_run, exact_dir)


@mcp.tool()
def list_modules() -> str:
    """The catalogue of verified pdbuild modules (voices, drums, filters, effects, envelopes,
    clocks, step tables, melody loop, scales) and surface helpers (controls with `_ui` receives,
    pad rows, CC maps), with signatures.  Compose from these before writing raw Pd."""
    return tools.list_modules()


@mcp.tool()
def knowledge_index() -> str:
    """The knowledge bank's table of contents, for clients that cannot list MCP resources."""
    return knowledge.index()


@mcp.tool()
def knowledge_read(path: str) -> str:
    """Read one knowledge-bank document by its path from `knowledge_index` (e.g.
    `lessons/LESSONS.md`)."""
    return knowledge.read(path)


@mcp.tool()
def field_log_stub(slug: str, directory: str | None = None, participant: str = "human",
                   exact_dir: bool = False) -> dict:
    """Create <project>/field_tests/<date>_<slug>.md from the template if it does not exist.
    `participant="human"` (default): a study session with a person.  `participant="agent"`: an
    unattended run; the runtime is the participant, the session is one task, and the
    playability section is answered from `probe_patch` results, not a person's hands.  Fill it
    in when the build is done: the request verbatim, every render iteration and its verdict,
    the intent gaps, and the lessons.  The logs are how the harness gets better."""
    return tools.field_log_stub(slug, directory, participant, exact_dir)


# ----------------------------------------------------------------- resources

@mcp.resource("knowledge://index", name="knowledge index", mime_type="text/markdown")
def _index() -> str:
    return knowledge.index()


# {+path} (RFC 6570 reserved expansion) matches across '/', so knowledge://skill/SKILL.md
# resolves; a plain {path} stops at the first slash.
@mcp.resource("knowledge://{+path}", name="knowledge document", mime_type="text/markdown")
def _doc(path: str) -> str:
    return knowledge.read(path)


# ----------------------------------------------------------------- prompt

@mcp.prompt(name="build_instrument")
def build_instrument(description: str, slug: str = "") -> str:
    """The build procedure for an instrument described in plain language."""
    slug_line = f"Slug: `{slug}`." if slug else "Choose a short snake_case slug."
    return f"""Build a playable Pure Data instrument from this description:

> {description}

{slug_line}

Procedure (the harness's loop; do not skip steps):
1. Read knowledge://00_START_HERE.md, then knowledge://lessons/LESSONS.md. If Pd objects are
   involved you have not used, read knowledge://skill/SKILL.md and its references.
2. Run `doctor` once. If it is not ok, stop and say what is missing.
3. Translate the description into 3 to 6 claims you could check by ear (pitch, rhythm, timbre,
   what each control does). Write them down before building.
4. `new_instrument` for the scaffold; `list_modules` and compose from verified modules first;
   write raw Pd only for what does not exist.
5. Edit the build script. Every control the person will touch: a `_ui` receive, initialised at
   load. Audio on at load. Then `run_script`.
6. `analyze_patch` after every change. Silent, clipped or NaN is a bug, never a style.
   `verify_patch` turns each claim from step 3 into a check; `probe_patch` proves interaction.
7. Iterate until every claim passes and the description matches what you hear. Render a demo
   .wav and hand it over with the .pd.
8. Fill in the field log (`field_log_stub`; `participant="agent"` when no person will play
   it): the request verbatim, each iteration and its verdict, the intent gaps, the lessons.
   Flag anything the harness lacked.
"""


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
