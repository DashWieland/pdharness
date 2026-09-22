"""The tool implementations behind the MCP server, importable and testable on
their own.  Every tool returns plain dicts (JSON-safe) so any MCP client can
use them.

Thin by design: pdverify is the ears, pdbuild is the hands; this module only
turns their Python APIs into something an agent can call with JSON.
"""

from __future__ import annotations

import datetime as _dt
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------- controls

def parse_controls(controls: list[dict] | None) -> tuple:
    """JSON control events -> pdverify Control events.

    Each item is one of
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


def _spec(patch: str | Path, duration: float, controls: list[dict] | None, strict: bool = True):
    from pdverify.render import RenderSpec

    p = Path(patch)
    return RenderSpec(duration=float(duration), controls=parse_controls(controls),
                      search_paths=(str(p.parent.resolve()),), strict=strict)


def _console_errors(console: str) -> list[str]:
    out = []
    for line in (console or "").splitlines():
        low = line.lower()
        if "error" in low or "couldn't create" in low or "multiply defined" in low or "no such object" in low:
            out.append(line.strip())
    return out


# ----------------------------------------------------------------- doctor

def doctor() -> dict:
    """Is this machine able to build and hear a patch?"""
    info: dict[str, Any] = {"python": sys.version.split()[0], "platform": platform.platform()}
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
        from pdverify.pd_locate import discover
        pd = discover(None)
        info["pd"] = str(pd)
    except Exception as e:
        info["pd"] = f"NOT FOUND ({e})"
        info["ok"] = False
        info["fix"] = "Install Pure Data (puredata.info) and put `pd` on PATH, or set PDVERIFY_PD to the executable."
        return info
    # a real render: the only proof the capture pipeline works
    try:
        from pdverify import analyze
        from pdverify.render import RenderSpec, render
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "probe.pd"
            t.write_text("#N canvas 0 0 300 200 10;\n#X obj 20 20 osc~ 440;\n#X obj 20 50 *~ 0.2;\n"
                         "#X obj 20 80 dac~;\n#X connect 0 0 1 0;\n#X connect 1 0 2 0;\n#X connect 1 0 2 1;\n",
                         encoding="utf-8")
            r = render(str(t), RenderSpec(duration=0.5))
            rep = analyze(r.audio)
            info["pd_version"] = r.pd_version
            info["render_ms"] = round(r.wall_ms, 1)
            info["probe"] = rep.summary()
            info["ok"] = (not rep.is_silent) and rep.note is not None and rep.note.startswith("A")
    except Exception as e:
        info["ok"] = False
        info["probe_error"] = str(e)
    # ELSE is optional; say whether it is there
    try:
        from pdverify.render import RenderSpec, render
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "else.pd"
            t.write_text("#N canvas 0 0 300 200 10;\n#X obj 20 20 else/lop2~ 1000;\n#X obj 20 60 dac~;\n"
                         "#X connect 0 0 1 0;\n", encoding="utf-8")
            r = render(str(t), RenderSpec(duration=0.2, strict=False))
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
    Names are the functions in pdverify.expect (not_silent, no_clipping, pitch, note, level, tonal,
    noisy, centroid, has_partial, harmonic, brighter_than, darker_than, band, percussive, sustained,
    onsets, stereo, dynamic, steady, ioi, ioi_cv, period, repeats, matches_reference, ...).
    """
    from pdverify import expect, verify

    exps = []
    for e in expectations:
        fn = getattr(expect, e["name"], None)
        if fn is None or e["name"].startswith("_"):
            raise ValueError(f"unknown expectation {e['name']!r}; see pdverify.expect")
        exp = fn(*e.get("args", []), **e.get("kwargs", {}))
        if "within" in e:
            t0, t1 = e["within"]
            exp = expect.within(float(t0), float(t1), exp)
        exps.append(exp)
    p = Path(patch)
    card = verify(str(p), exps, spec=_spec(p, duration, controls))
    d = card.to_dict()
    d["description"] = card.report.summary()
    return d


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
                          search_paths=(str(p.parent.resolve()),), strict=False)
        r = render(str(t), spec)
    lines = (r.pd_console or "").splitlines()
    got = {name: [l.split(":", 1)[1].strip() for l in lines if l.startswith(f"{name}:")] for name in watch}
    return {"watched": got, "console_errors": _console_errors(r.pd_console),
            "missing_externals": list(r.missing_externals), "console_tail": lines[-20:]}


# ----------------------------------------------------------------- hands

def run_script(script: str, args: list[str] | None = None, cwd: str | None = None,
               timeout: float = 900.0) -> dict:
    """Run a Python build script with this environment's interpreter (the one that has pdbuild
    and pdverify).  Returns the tail of its output and the files it produced or touched."""
    s = Path(script).resolve()
    if not s.exists():
        raise FileNotFoundError(script)
    workdir = Path(cwd).resolve() if cwd else s.parent
    before = {f: f.stat().st_mtime for f in workdir.rglob("*") if f.is_file()}
    proc = subprocess.run([sys.executable, str(s), *(args or [])], cwd=str(workdir),
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)
    after = {f: f.stat().st_mtime for f in workdir.rglob("*") if f.is_file()}
    changed = sorted(str(f.relative_to(workdir)) for f, m in after.items()
                     if f not in before or before[f] != m)
    out = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip().splitlines()
    return {"returncode": proc.returncode, "output_tail": out[-60:], "files_changed": changed[:50],
            "cwd": str(workdir)}


def list_modules() -> str:
    from . import knowledge
    return knowledge.read("modules/CATALOGUE.md")


def new_instrument(slug: str, description: str, directory: str | None = None) -> dict:
    """Scaffold instruments/<slug>/ with a build script that already builds, verifies and
    renders a minimal playable patch, plus a README and a field-log stub."""
    from .scaffold import scaffold
    return scaffold(slug, description, Path(directory) if directory else Path.cwd())


def field_log_stub(slug: str, directory: str | None = None) -> dict:
    from . import knowledge
    base = Path(directory) if directory else Path.cwd()
    logs = base / "field_tests"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"{_dt.date.today().isoformat()}_{slug}.md"
    if not path.exists():
        path.write_text(knowledge.read("field_test/LOG_TEMPLATE.md").replace("<slug>", slug), encoding="utf-8")
    return {"path": str(path)}
