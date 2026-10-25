"""Delivering a file: render_patch (takes, seamless loops, one-gain level, bit depth),
claims scored on a delivered .wav, end-relative times, and a doctor that remembers its Pd.
Needs Pd; skipped without it."""

from __future__ import annotations

import os
import shutil
import wave
from pathlib import Path

import pytest

from pdharness import tools

HAS_PD = shutil.which("pd") is not None or shutil.which("pd.com") is not None or os.environ.get("PDVERIFY_PD")
if not HAS_PD:
    try:
        from pdverify.pd_locate import discover
        discover()
        HAS_PD = True
    except Exception:
        pass
pytestmark = pytest.mark.skipif(not HAS_PD, reason="no Pure Data binary found")

# whole cycles per 5 s (110 Hz -> 550), a little hiss, and a gain that follows [r lift]
BED = (
    "#N canvas 0 0 400 300 12;\n"
    "#X obj 30 30 osc~ 110;\n"          # 0
    "#X obj 30 60 *~ 0.1;\n"            # 1
    "#X obj 150 30 noise~;\n"           # 2
    "#X obj 150 60 *~ 0.01;\n"          # 3
    "#X obj 30 120 *~;\n"               # 4
    "#X obj 30 170 dac~;\n"             # 5
    "#X obj 250 30 loadbang;\n"         # 6
    "#X msg 250 60 1;\n"                # 7
    "#X obj 250 120 line~;\n"           # 8
    "#X obj 330 30 r lift;\n"           # 9
    "#X msg 330 60 \\$1 200;\n"         # 10
    "#X connect 0 0 1 0;\n#X connect 1 0 4 0;\n#X connect 2 0 3 0;\n#X connect 3 0 4 0;\n"
    "#X connect 8 0 4 1;\n#X connect 4 0 5 0;\n#X connect 4 0 5 1;\n"
    "#X connect 6 0 7 0;\n#X connect 7 0 8 0;\n#X connect 9 0 10 0;\n#X connect 10 0 8 0;\n"
)


@pytest.fixture(autouse=True)
def fresh_pd():
    tools._PD = None
    yield
    tools._PD = None


@pytest.fixture
def bed(tmp_path) -> Path:
    p = tmp_path / "bed.pd"
    p.write_text(BED, encoding="utf-8")
    return p


def test_render_patch_writes_a_seamless_loop_at_a_level_and_format(bed, tmp_path):
    out = tools.render_patch(str(bed), str(tmp_path / "out" / "bed_5s.wav"), loop=5.0, crossfade=1.0,
                             preroll=1.0, sr=48000, bits=24, rms_dbfs=-18.0, peak_dbfs=-1.0,
                             expectations=[{"name": "seamless"}, {"name": "no_clipping"}])
    assert out["duration"] == pytest.approx(5.0) and out["sr"] == 48000 and out["bits"] == 24
    with wave.open(out["wav"], "rb") as w:
        assert (w.getframerate(), w.getsampwidth(), w.getnframes()) == (48000, 3, 5 * 48000)
    assert out["master"]["rms_dbfs"] == pytest.approx(-18.0, abs=0.05) and not out["master"]["peak_bound"]
    assert out["seam"]["click_ratio"] < 1.5 and out["seam"]["head_excursion_db"] < 2.0
    assert out["verdict"]["passed"], out["verdict"]


def test_one_end_relative_score_fits_every_length(bed, tmp_path):
    lift = [{"receive": "lift", "value": 3, "at": -1.5}]
    claim = [{"name": "change", "args": ["level", [0.5, -2], [-1, None]], "kwargs": {"min": 6}}]
    for dur in (4.0, 9.0):
        out = tools.render_patch(str(bed), str(tmp_path / f"cue_{dur:g}s.wav"), duration=dur,
                                 controls=lift, expectations=claim)
        assert out["verdict"]["passed"], out["verdict"]
    flat = tools.render_patch(str(bed), str(tmp_path / "flat.wav"), duration=4.0, expectations=claim)
    assert not flat["verdict"]["passed"]


def test_verify_patch_scores_a_delivered_wav_as_it_is(bed, tmp_path):
    good = tools.render_patch(str(bed), str(tmp_path / "loop.wav"), loop=5.0, crossfade=1.0, preroll=1.0)
    # whole cycles and no fade: a plain 5-s take of this bed already loops; one that lifts at the end does not
    plain = tools.render_patch(str(bed), str(tmp_path / "plain.wav"), duration=5.0)
    raw = tools.render_patch(str(bed), str(tmp_path / "raw.wav"), duration=5.0,
                             controls=[{"receive": "lift", "value": 3, "at": -1.5}])
    claims = [{"name": "seamless"},
              {"name": "band_level", "args": [250], "kwargs": {"min_db": -30, "relative": True}},
              {"name": "level", "args": [-25], "kwargs": {"tol_db": 6}, "within": [-2, None]}]
    v = tools.verify_patch(good["wav"], claims)
    assert v["passed"], v
    assert tools.verify_patch(plain["wav"], [{"name": "seamless"}])["passed"]
    assert not tools.verify_patch(raw["wav"], [{"name": "seamless"}])["passed"]


def test_doctor_remembers_a_pd_that_passes(tmp_path, monkeypatch):
    from pdverify import pd_locate

    monkeypatch.setenv("PDVERIFY_CONFIG_DIR", str(tmp_path / "cfg"))
    info = tools.doctor()
    assert info["ok"], info
    assert Path(info["pd_remembered"]).exists()
    assert pd_locate.remembered() == str(Path(info["pd"]).resolve())
    tools._PD = None
    pd_locate.forget()
    info = tools.doctor(remember=False)
    assert "pd_remembered" not in info and pd_locate.remembered() is None


def test_the_bank_drift_example_builds_and_its_default_state_holds(tmp_path):
    """The worked example builds from a copy, and its first claim holds (the full 5 checks
    and the delivered family run in its own build script, about a minute)."""
    import subprocess
    import sys

    from pdverify import expect, verify
    from pdverify.render import RenderSpec

    src = Path(tools.__file__).parent / "knowledge" / "examples" / "drift" / "build_drift.py"
    shutil.copy(src, tmp_path / "build_drift.py")
    r = subprocess.run([sys.executable, str(tmp_path / "build_drift.py"), "--build-only"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    card = verify(str(tmp_path / "drift.pd"),
                  [expect.not_silent(), expect.no_clipping(0.9),
                   expect.band_level(250, min_db=-12, relative=True)],
                  spec=RenderSpec(duration=8.0))
    assert card.passed, card.feedback()
