"""The tool implementations behind the MCP server, importable and testable on
their own.  Every tool returns plain dicts (JSON-safe) so any MCP client can
use them.

Thin by design: pdverify is the ears, pdbuild is the hands; this module only
turns their Python APIs into something an agent can call with JSON.
"""

from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------- controls

def parse_controls(controls: list[dict] | None) -> tuple:
    """JSON control events -> pdverify Control events.

    Each item is one of (``at`` in seconds; negative = before the end of the render)
      {"receive": "tempo", "value": 150, "at": 0.0}        a float/list/symbol to a receive
      {"receive": "tempo", "values": [1, 2, 3], "at": 0.0}  a list
      {"bang": "nextpattern", "at": 1.0}                    a bang
      {"note": 60, "at": 0.0, "dur": 0.5, "velocity": 100}  a MIDI note into [notein]
    """
    from pdverify import control

    events: list = []
    for c in controls or []:
        at = float(c.get("at", 0.0))
        if "bang" in c:
            events += control.bang(str(c["bang"]), at=at)
        elif "note" in c:
            events += control.note(c["note"], at=at, dur=float(c.get("dur", 0.5)),
                                   velocity=int(c.get("velocity", 100)))
        elif "receive" in c:
            if "values" in c:
                events += control.send(str(c["receive"]), *c["values"], at=at)
            else:
                events += control.send(str(c["receive"]), c.get("value", 0), at=at)
        else:
            raise ValueError(f"control event needs 'receive', 'bang' or 'note': {c!r}")
    return tuple(events)


def _spec(patch: str | Path, duration: float, controls: list[dict] | None, strict: bool = True,
          sr: int = 44100):
    from pdverify.render import RenderSpec

    p = Path(patch)
    return RenderSpec(duration=float(duration), sr=int(sr), controls=parse_controls(controls),
                      search_paths=(str(p.parent.resolve()),), strict=strict,
                      pd_binary=locate_pd()["path"])


# ----------------------------------------------------------------- Pd

# One Pd per process.  `doctor` settles on a binary with pdverify's own discovery
# (pdverify.pd_locate.discover) and caches it here; every render this process makes
# passes that path explicitly, and every script `run_script` starts gets it as
# PDVERIFY_PD.  So the Pd doctor reports is the Pd that renders, in the server, and in
# a build script started from a cold shell.
_PD: dict | None = None

# How discover() found the binary, in its vocabulary (pdverify >= 0.5.0 records it as
# PdBinary.source; for older pdverify, _classify_source reconstructs it).
PD_SOURCES = {
    "explicit": "a path passed explicitly",
    "env": "the PDVERIFY_PD environment variable",
    "remembered": "the Pd path pdverify remembered (its per-user config)",
    "path": "`pd` on PATH",
    "default": "a default install location for this OS",
    "dev": "a portable Pd unzipped under tools/ near the working directory",
}


def _same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _classify_source(path: str) -> str:
    """Which of discover()'s rules produced ``path`` (pdverify < 0.5.0 does not say)."""
    env = os.environ.get("PDVERIFY_PD")
    if env and _same_file(env, path):
        return "env"
    names = ["pd.com", "pd.exe"] if os.name == "nt" else ["pd", "puredata"]
    for name in names:
        found = shutil.which(name)
        if found and _same_file(found, path):
            return "path"
    parts = [x.lower() for x in Path(path).parts]
    if any(a == "tools" and b.startswith("pd-") for a, b in zip(parts, parts[1:])):
        return "dev"
    return "default"


def _env_warning() -> str | None:
    """PDVERIFY_PD set to something that is not there: discover() skips it silently."""
    env = os.environ.get("PDVERIFY_PD")
    if env and not Path(env).exists():
        return f"PDVERIFY_PD is set to {env!r}, which does not exist, so it was ignored"
    return None


def persist_lines(path: str) -> dict:
    """Ready-to-paste lines that make every shell find this Pd."""
    ps = path.replace("'", "''")
    return {
        "posix": f"export PDVERIFY_PD={shlex.quote(path)}",
        "powershell": f"$env:PDVERIFY_PD = '{ps}'",
        "windows_setx": f'setx PDVERIFY_PD "{path}"',
        "note": ("posix: put the export in your shell profile, or prefix a single command with "
                 "PDVERIFY_PD=...; a shell that starts cold for every command needs one of the two. "
                 "`pdharness run <script>` (MCP: run_script) sets it for the script it starts."),
    }


def locate_pd(refresh: bool = False) -> dict:
    """The Pd this process renders with: path, version, and how it was found.

    The first call (or ``refresh=True``, which doctor uses) runs pdverify's discovery;
    later calls return the same answer, so the server cannot render with a different
    Pd from the one doctor reported.  Raises pdverify's PdNotFound if there is none.
    """
    global _PD
    if _PD is not None and not refresh:
        return dict(_PD)
    from pdverify.pd_locate import discover

    pd = discover(None)
    path = os.path.abspath(pd.path)
    source = getattr(pd, "source", None) or _classify_source(pd.path)
    _PD = {"path": path, "version": pd.version, "source": source,
           "found_by": PD_SOURCES.get(source, source), "persist": persist_lines(path)}
    warning = _env_warning()
    if warning:
        _PD["warning"] = warning
    return dict(_PD)


def script_env() -> dict:
    """The environment a build script runs in: this process's, with PDVERIFY_PD set to the
    Pd this process settled on (when there is one), so the script's own pdverify finds it."""
    env = dict(os.environ)
    try:
        env["PDVERIFY_PD"] = locate_pd()["path"]
    except Exception:
        pass  # no Pd: the script's own discovery will say so
    return env


def _console_errors(console: str) -> list[str]:
    out = []
    for line in (console or "").splitlines():
        low = line.lower()
        if "error" in low or "couldn't create" in low or "multiply defined" in low or "no such object" in low:
            out.append(line.strip())
    return out


# ----------------------------------------------------------------- doctor

def doctor(remember: bool = True) -> dict:
    """Is this machine able to build and hear a patch?  Also: which Pd, found how, and
    the line that makes a fresh shell find the same one.  When the probe render passes and
    ``remember`` is set, the Pd is remembered (pdverify's per-user config), so every later
    discovery -- a cold shell, a build script, another client -- finds the same binary."""
    from . import __version__
    info: dict[str, Any] = {"pdharness": __version__, "python": sys.version.split()[0],
                            "python_executable": sys.executable, "platform": platform.platform()}
    try:
        import pdverify
        info["pdverify"] = pdverify.__version__
    except Exception as e:  # pragma: no cover
        info["pdverify"] = f"MISSING ({e})"
    try:
        import pdbuild
        info["pdbuild"] = getattr(pdbuild, "__version__", "installed")
        from pdbuild import Patch  # noqa: F401
        from py2pd import Patcher
        import inspect
        params = inspect.signature(Patcher.__init__).parameters
        info["py2pd_fork"] = "width" in params  # the fork's geometry kwargs; upstream 0.2.x says canvas_width
        if not info["py2pd_fork"]:
            info["warning"] = "py2pd is the upstream release, not the fork pdbuild needs; pdbuild.Patch() will fail. See README."
    except Exception as e:
        info["pdbuild"] = f"MISSING ({e})"
    try:
        pd = locate_pd(refresh=True)
    except Exception as e:
        info["pd"] = f"NOT FOUND ({e})"
        warning = _env_warning()
        if warning:
            info["pd_warning"] = warning
        info["ok"] = False
        info["fix"] = "Install Pure Data (puredata.info) and put `pd` on PATH, or set PDVERIFY_PD to the executable."
        return info
    info["pd"] = pd["path"]
    info["pd_source"] = pd["source"]
    info["pd_found_by"] = pd["found_by"]
    if pd.get("warning"):
        info["pd_warning"] = pd["warning"]
    info["pd_persist"] = pd["persist"]
    pd_path = pd["path"]
    # a real render: the only proof the capture pipeline works
    try:
        from pdverify import analyze
        from pdverify.render import RenderSpec, render
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "probe.pd"
            t.write_text("#N canvas 0 0 300 200 10;\n#X obj 20 20 osc~ 440;\n#X obj 20 50 *~ 0.2;\n"
                         "#X obj 20 80 dac~;\n#X connect 0 0 1 0;\n#X connect 1 0 2 0;\n#X connect 1 0 2 1;\n",
                         encoding="utf-8")
            r = render(str(t), RenderSpec(duration=0.5, pd_binary=pd_path))
            rep = analyze(r.audio)
            info["pd_version"] = r.pd_version
            info["render_ms"] = round(r.wall_ms, 1)
            info["probe"] = rep.summary()
            info["ok"] = (not rep.is_silent) and rep.note is not None and rep.note.startswith("A")
    except Exception as e:
        info["ok"] = False
        info["probe_error"] = str(e)
    # a Pd that renders is remembered, so a cold shell's discover() finds this same one
    # with no environment variable (pdverify >= 0.5.0)
    if info.get("ok") and remember:
        try:
            from pdverify import pd_locate
            if hasattr(pd_locate, "remember"):
                info["pd_remembered"] = str(pd_locate.remember(pd_path))
        except Exception as e:  # pragma: no cover - a read-only home, say
            info["pd_remember_error"] = str(e)
    # ELSE is optional; say whether it is there
    try:
        from pdverify.render import RenderSpec, render
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "else.pd"
            t.write_text("#N canvas 0 0 300 200 10;\n#X obj 20 20 else/lop2~ 1000;\n#X obj 20 60 dac~;\n"
                         "#X connect 0 0 1 0;\n", encoding="utf-8")
            r = render(str(t), RenderSpec(duration=0.2, strict=False, pd_binary=pd_path))
            info["else_externals"] = not r.missing_externals
    except Exception:
        info["else_externals"] = False
    return info


# ----------------------------------------------------------------- hear

def analyze_patch(patch: str, duration: float = 6.0, controls: list[dict] | None = None,
                  save_wav: str | None = None, strict: bool = True) -> dict:
    """Render a patch (or read a .wav) and report what it sounds like."""
    from pdverify import analyze, read_wav, write_wav
    from pdverify.render import render

    p = Path(patch)
    if not p.exists():
        raise FileNotFoundError(patch)
    out: dict[str, Any] = {"patch": str(p)}
    if p.suffix.lower() == ".wav":
        audio = read_wav(p)
    else:
        r = render(str(p), _spec(p, duration, controls, strict))
        audio = r.audio
        out.update(pd_version=r.pd_version, render_ms=round(r.wall_ms, 1),
                   missing_externals=list(r.missing_externals),
                   console_errors=_console_errors(r.pd_console),
                   console_tail=(r.pd_console or "").strip().splitlines()[-12:])
        if save_wav:
            out["wav"] = str(write_wav(save_wav, audio))
    rep = analyze(audio)
    out["description"] = rep.summary()
    out["report"] = rep.to_dict()
    out["integrity"] = {"silent": rep.is_silent, "clipped": rep.is_clipped, "nan_inf": rep.has_nan_inf,
                        "peak_dbfs": rep.peak_dbfs}
    return out


def verify_patch(patch: str, expectations: list[dict], duration: float = 6.0,
                 controls: list[dict] | None = None) -> dict:
    """Render and score against pdverify's expectation vocabulary.

    expectations: [{"name": "note", "args": ["A4"], "kwargs": {"tol_cents": 30}, "within": [0.5, 2.0]}, ...]
    Names are the functions in pdverify.expect (not_silent, no_clipping, pitch, note, f0, level, tonal,
    noisy, centroid, has_partial, harmonic, harmonic_series, brighter_than, darker_than, band,
    percussive, sustained, onsets, stereo, dynamic, steady, ioi, ioi_cv, period, repeats,
    matches_reference, ...).
    """
    from pdverify import expect, verify

    exps = build_expectations(expectations)
    p = Path(patch)
    if p.suffix.lower() == ".wav":
        # a delivered file: score what is on disk, no render
        from pdverify import analyze, read_wav, score
        audio = read_wav(p)
        card = score(analyze(audio), exps, audio=audio, meta={"source": str(p)})
    else:
        card = verify(str(p), exps, spec=_spec(p, duration, controls))
    d = card.to_dict()
    d["description"] = card.report.summary()
    return d


def build_expectations(expectations: list[dict]) -> list:
    """JSON expectations -> pdverify Expectations.  ``within`` is [t0, t1] seconds; negative
    times count from the end and a null t1 is the end ([-4, null] = the last four seconds).
    Lists in args/kwargs stay lists (``change``'s windows take them as [t0, t1])."""
    from pdverify import expect

    exps = []
    for e in expectations:
        fn = getattr(expect, e["name"], None)
        if fn is None or e["name"].startswith("_") or not callable(fn):
            raise ValueError(f"unknown expectation {e['name']!r}; see pdverify.expect")
        exp = fn(*e.get("args", []), **e.get("kwargs", {}))
        if "within" in e:
            t0, t1 = e["within"]
            exp = expect.within(float(t0), None if t1 is None else float(t1), exp)
        exps.append(exp)
    return exps


def render_patch(patch: str, out: str, duration: float = 6.0, controls: list[dict] | None = None,
                 sr: int = 44100, bits: int = 16, loop: float | None = None, crossfade: float = 2.0,
                 preroll: float = 4.0, rms_dbfs: float | None = None, peak_dbfs: float | None = None,
                 expectations: list[dict] | None = None) -> dict:
    """Render a patch to a .wav file meant to be used somewhere: a take of ``duration``, or
    with ``loop`` a seamless loop of exactly that many seconds (renders preroll + loop +
    crossfade and crossfades the overrun onto the head).  ``rms_dbfs``/``peak_dbfs`` apply one
    gain (never a limiter; the ceiling wins).  ``expectations`` are scored on the file as
    written (e.g. seamless, band_level, change).  Control ``at`` times may be negative: seconds
    before the end of the render."""
    from pdverify import analyze, score, write_wav
    from pdverify.render import render

    p = Path(patch)
    if not p.exists():
        raise FileNotFoundError(patch)
    result: dict[str, Any] = {"patch": str(p)}
    if loop is not None:
        from pdverify.loops import loop_render_seconds, make_loop, seam
        n = loop_render_seconds(loop, crossfade, preroll)
        r = render(str(p), _spec(p, n, controls, sr=sr))
        audio = make_loop(r.audio, loop, crossfade=crossfade, start=preroll)
        s = seam(audio, head_s=max(crossfade, 0.5))
        result["seam"] = {"click_ratio": round(s.click_ratio, 3), "click_dbfs": round(s.click_dbfs, 1),
                          "level_step_db": round(s.level_step_db, 2),
                          "head_excursion_db": round(s.head_excursion_db, 2)}
    else:
        r = render(str(p), _spec(p, duration, controls, sr=sr))
        audio = r.audio
    result.update(pd_version=r.pd_version, render_ms=round(r.wall_ms, 1),
                  console_errors=_console_errors(r.pd_console))
    if rms_dbfs is not None or peak_dbfs is not None:
        from pdverify import master
        m = master(audio, rms_dbfs=rms_dbfs, peak_dbfs=-1.0 if peak_dbfs is None else peak_dbfs)
        audio = m.audio
        result["master"] = {"gain_db": round(m.gain_db, 2), "rms_dbfs": round(m.rms_dbfs, 2),
                            "peak_dbfs": round(m.peak_dbfs, 2), "peak_bound": m.peak_bound}
    dest = Path(out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    result["wav"] = str(write_wav(dest, audio, bits=int(bits)))
    result.update(duration=round(audio.duration, 4), sr=audio.sr, channels=audio.channels, bits=int(bits))
    rep = analyze(audio)
    result["description"] = rep.summary()
    result["level"] = {"rms_dbfs": round(rep.rms_dbfs, 2), "peak_dbfs": round(rep.peak_dbfs, 2)}
    if expectations:
        exps = build_expectations(expectations)
        card = score(rep, exps, audio=audio)
        result["verdict"] = card.to_dict()
    return result


def compare_patches(candidate: str, reference: str, duration: float = 6.0,
                    controls: list[dict] | None = None) -> dict:
    """How close does the candidate sound to the reference (.pd or .wav)?  Similarity 0..1 plus
    the moves that would close the gap."""
    from pdverify import analyze, compare, read_wav
    from pdverify.render import render

    def rep(path: str):
        p = Path(path)
        if p.suffix.lower() == ".wav":
            return analyze(read_wav(p))
        return analyze(render(str(p), _spec(p, duration, controls)).audio)

    c = compare(rep(candidate), rep(reference))
    return {"similarity": c.similarity, "diffs": list(c.diffs), "feedback": c.feedback()}


# ----------------------------------------------------------------- probe

_BOX = re.compile(r"^#X (obj|msg|text|floatatom|symbolatom|listbox) ")


def _top_level_box_count(patch_text: str) -> int:
    """Number of boxes on the top-level canvas, the index the next box would get.
    Subpatch contents do not count; the subpatch's `#X restore` does."""
    depth = 0
    n = 0
    seen_canvas = False
    for line in patch_text.splitlines():
        if line.startswith("#N canvas"):
            if seen_canvas:
                depth += 1
            seen_canvas = True
        elif line.startswith("#X restore"):
            depth -= 1
            if depth == 0:
                n += 1
        elif depth == 0 and _BOX.match(line):
            n += 1
    return n


def probe_patch(patch: str, watch: list[str], controls: list[dict] | None = None,
                duration: float = 3.0) -> dict:
    """The runtime probe: drive receives, and read back what named receives carry.

    A headless render cannot see interaction; this can.  For every name in ``watch`` a
    `[r name] -> [print name]` tap is added to a COPY of the patch, the controls are played
    in, and the console lines for each tap are returned.  Use it to prove a control reaches
    what it should (`watch=["tempo"]`, send `tempo_ui`), that a read-out updates (give the
    read-out box a send name, watch it), or that a latch landed on the bar.
    """
    from pdverify.render import RenderSpec, render

    p = Path(patch)
    text = p.read_text(encoding="utf-8")
    n = _top_level_box_count(text)
    extra = []
    for i, name in enumerate(watch):
        r_idx, p_idx = n + 2 * i, n + 2 * i + 1
        extra += [f"#X obj 10 {10 + 40 * i} r {name};", f"#X obj 10 {30 + 40 * i} print {name};",
                  f"#X connect {r_idx} 0 {p_idx} 0;"]
    probe_text = text.rstrip("\n") + "\n" + "\n".join(extra) + "\n"
    with tempfile.TemporaryDirectory() as d:
        t = Path(d) / p.name
        t.write_text(probe_text, encoding="utf-8")
        spec = RenderSpec(duration=float(duration), controls=parse_controls(controls),
                          search_paths=(str(p.parent.resolve()),), strict=False,
                          pd_binary=locate_pd()["path"])
        r = render(str(t), spec)
    lines = (r.pd_console or "").splitlines()
    got = {name: [l.split(":", 1)[1].strip() for l in lines if l.startswith(f"{name}:")] for name in watch}
    return {"watched": got, "console_errors": _console_errors(r.pd_console),
            "missing_externals": list(r.missing_externals), "console_tail": lines[-20:]}


# ----------------------------------------------------------------- hands

def script_command(script: str | None = None, args: list[str] | None = None, module: str | None = None,
                   cwd: str | None = None) -> tuple[list[str], Path]:
    """The command line and working directory for running a build script (or ``-m module``)
    with this environment's interpreter.  A script runs in its own folder unless ``cwd``
    says otherwise; a module runs in the current directory."""
    if module:
        cmd = [sys.executable, "-m", module, *([script] if script else []), *(args or [])]
        return cmd, (Path(cwd).resolve() if cwd else Path.cwd())
    if not script:
        raise ValueError("give a script to run (or a module)")
    s = Path(script).resolve()
    if not s.exists():
        raise FileNotFoundError(script)
    return [sys.executable, str(s), *(args or [])], (Path(cwd).resolve() if cwd else s.parent)


def run_script(script: str, args: list[str] | None = None, cwd: str | None = None,
               timeout: float = 900.0) -> dict:
    """Run a Python build script with this environment's interpreter (the one that has pdbuild
    and pdverify), with PDVERIFY_PD set to the Pd this process renders with.  Returns the tail
    of its output and the files it produced or touched."""
    cmd, workdir = script_command(script, args, cwd=cwd)
    env = script_env()
    before = {f: f.stat().st_mtime for f in workdir.rglob("*") if f.is_file()}
    proc = subprocess.run(cmd, cwd=str(workdir), env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)
    after = {f: f.stat().st_mtime for f in workdir.rglob("*") if f.is_file()}
    changed = sorted(str(f.relative_to(workdir)) for f, m in after.items()
                     if f not in before or before[f] != m)
    out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip().splitlines()
    return {"returncode": proc.returncode, "output_tail": out[-60:], "files_changed": changed[:50],
            "cwd": str(workdir), "python": sys.executable, "pd": env.get("PDVERIFY_PD")}


def list_modules() -> str:
    from . import knowledge
    return knowledge.read("modules/CATALOGUE.md")


def new_instrument(slug: str, description: str, directory: str | None = None,
                   participant: str = "human", dry_run: bool = False, exact_dir: bool = False) -> dict:
    """Scaffold <project>/instruments/<slug>/ with a build script that already builds, verifies
    and renders a minimal playable patch, plus a README and a field-log stub in
    <project>/field_tests/.  ``directory`` (default: cwd) is the project root; if it is itself
    an instruments/ folder, or an instrument folder inside one, its project root is used
    instead (``exact_dir=True`` turns that off).  ``dry_run`` reports the layout and writes
    nothing.  ``participant="agent"`` writes the unattended-agent field log."""
    from .scaffold import scaffold
    return scaffold(slug, description, Path(directory) if directory else Path.cwd(),
                    participant=participant, dry_run=dry_run, exact_dir=exact_dir)


def field_log_stub(slug: str, directory: str | None = None, participant: str = "human",
                   exact_dir: bool = False) -> dict:
    """Create <project>/field_tests/<date>_<slug>.md from the template if it does not exist.
    ``participant="human"``: a study session with a person.  ``participant="agent"``: an
    unattended run, where the participant is the agent runtime, the session is one task, and
    playability is answered from probe_patch results.  The project root is found the way
    ``new_instrument`` finds it, so the log lands beside instruments/, not inside it."""
    from .scaffold import project_root, write_field_log
    root, note = project_root(Path(directory) if directory else Path.cwd(), exact=exact_dir)
    path = write_field_log(root, slug, participant)
    out = {"path": str(path), "participant": participant, "project_root": str(root)}
    if note:
        out["note"] = note
    return out
