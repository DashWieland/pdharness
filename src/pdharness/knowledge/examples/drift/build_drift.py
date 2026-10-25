"""drift: a small self-playing ambient bed, and how to deliver it as files.

A seeded walk of soft plucks in D dorian over a breathing drone and a band of
air, through a reverb. Six dials on the canvas: DENSITY (how many notes),
BRIGHT (the tone), AIR (the noise bed), SPACE (dry ... all reverb), LIFT (the
gentle rise you send near the end of a cut), LEVEL.

It is the bank's worked example of two things:

- an ambient patch composed from pdbuild's ambient modules (scale_walk,
  pluck, drone, noise_bed, reverb), every layer that holds a steady pitch
  made whole cycles per loop so it crossfades cleanly;
- delivering files: seamless loops of exact length, a cut that lifts in its
  last seconds (one end-relative control score for every length), a level
  and a format, and the claims scored on the files themselves.

    pdharness run build_drift.py               # build -> verify -> deliver the demo family
    pdharness run build_drift.py --build-only
"""

from __future__ import annotations

import sys
from pathlib import Path

from pdbuild import Patch, surface
from pdbuild.modules.ambient import drone, noise_bed, pluck, reverb, scale_walk
from pdverify import analyze, expect, verify
from pdverify.render import RenderSpec, render
from pdverify import control

HERE = Path(__file__).resolve().parent
PATCH = HERE / "drift.pd"

LOOP_S = 20.0          # every steady layer is whole cycles per 20 s, so 20/40/60-s loops all close
DORIAN = (0, 2, 3, 5, 7, 9, 10)
DRONE_HZ = 73.4        # D2, a hair flat: 73.4 x 20 = 1468 whole cycles per loop

# name -> (default, label)
DIALS = {
    "density": (0.35, "DENSITY  (a few notes ... many)"),
    "bright": (0.5, "BRIGHT  (dark ... clear)"),
    "air": (0.5, "AIR  (no bed ... a band of air)"),
    "space": (0.45, "SPACE  (dry ... all reverb)"),
    "lift": (0.0, "LIFT  (send near the end of a cut)"),
    "level": (0.6, "LEVEL"),
}


def _ramp(p, name, ms):
    """[r name] -> [pack f ms] -> [line~]: a de-zippered signal of a control."""
    r = p.obj(f"r {name}"); pk = p.obj(f"pack f {ms}"); ln = p.obj("line~")
    p.chain(r, pk, ln)
    return ln


def build() -> Path:
    p = Patch(820, 560)
    y = 40
    for name, (default, label) in DIALS.items():
        surface.control(p, name, "hsl", x=30, y=y, lo=0, hi=1, default=default, label=label)
        y += 62
    p.comment("drift: plucks in D dorian over a drone and air. LIFT near the end of a cut.", 30, 8)

    p.cursor(420, 40)
    # the notes: a clock, a seeded walk whose density follows DENSITY, soft plucks
    clock = p.obj("metro 420")
    p.init(clock, 1)
    walk = scale_walk(p, clock, scale=DORIAN, tonic=62, seed=5, density=DIALS["density"][0],
                      density_recv="density", lo=-4, hi=10)
    hz = p.obj("mtof")
    p.link(walk.midi, 0, hz, 0)
    note_out = p.obj("s drift_note")        # every note played, for a probe, a visual, OSC
    p.link(walk.midi, 0, note_out, 0)
    notes = pluck(p, None, hz, decay=3.2, brightness=0.45, gain=0.22)

    # the steady layers: whole cycles per loop
    body = drone(p, DRONE_HZ, partials=((1, 1.0), (2, 0.6), (3, 0.45), (4, 0.3), (6, 0.2)),
                 gain=0.10, loop_s=LOOP_S)
    air = noise_bed(p, lo=700, hi=5200, swell_rate=0.1, seed=3, gain=0.05, loop_s=LOOP_S)
    air_amt = _ramp(p, "air", 80)
    air_g = p.obj("*~"); p.link(air, 0, air_g, 0); p.link(air_amt, 0, air_g, 1)

    # BRIGHT sets a two-pole lowpass on the notes and the drone (300 Hz .. 9.6 kHz)
    mix = p.obj("+~"); p.link(notes, 0, mix, 0); p.link(body, 0, mix, 1)
    rb = p.obj("r bright"); cut = p.obj("expr 300*pow(32, $f1)")
    p.link(rb, 0, cut, 0)
    tone1 = p.obj("lop~ 2000"); tone = p.obj("lop~ 2000")
    p.link(mix, 0, tone1, 0); p.link(tone1, 0, tone, 0)
    p.link(cut, 0, tone1, 1); p.link(cut, 0, tone, 1)
    pre = p.obj("+~"); p.link(tone, 0, pre, 0); p.link(air_g, 0, pre, 1)

    # LIFT: over 3 s, everything rises 6 dB (a smaller lift drowns in the plucks' own swing)
    lift = _ramp(p, "lift", 3000)
    lift_g = p.obj("expr~ 1 + $v1"); p.link(lift, 0, lift_g, 0)
    lifted = p.obj("*~"); p.link(pre, 0, lifted, 0); p.link(lift_g, 0, lifted, 1)

    # SPACE: dry ... wet
    wet = reverb(p, lifted, size=0.72, damping=0.5, mix=1.0)
    space = _ramp(p, "space", 80)
    dry_amt = p.obj("expr~ 1 - $v1"); p.link(space, 0, dry_amt, 0)
    level = _ramp(p, "level", 50)
    dac = p.obj("dac~")
    for ch, w in enumerate((wet.left, wet.right)):
        wg = p.obj("*~"); p.link(w, 0, wg, 0); p.link(space, 0, wg, 1)
        dg = p.obj("*~"); p.link(lifted, 0, dg, 0); p.link(dry_amt, 0, dg, 1)
        s = p.obj("+~"); p.link(wg, 0, s, 0); p.link(dg, 0, s, 1)
        out = p.obj("*~"); p.link(s, 0, out, 0); p.link(level, 0, out, 1)
        hot = p.obj("*~ 4"); p.link(out, 0, hot, 0)          # +12 dB: about -22 dBFS RMS at LEVEL 0.6
        p.link(hot, 0, dac, ch)

    p.save(PATCH)
    return PATCH


def verify_patch(path: Path) -> bool:
    """The claims, each a check."""
    checks = []

    def check(label, ok, detail=""):
        checks.append(ok)
        print(("  ok   " if ok else "  FAIL ") + label + (f"  ({detail})" if detail else ""))

    # 1. the default state: sounds, clean, and audible on a phone speaker
    card = verify(str(path), [expect.not_silent(), expect.no_clipping(0.9), expect.finite(),
                              expect.band_level(250, min_db=-12, relative=True), expect.stereo()],
                  spec=RenderSpec(duration=12.0))
    check("default: sounds, clean, wide, audible above 250 Hz", card.passed, card.feedback().splitlines()[0])

    # 2. DENSITY reaches the walk: count the notes it plays (a probe on [s drift_note]; an
    #    onset detector undercounts a wash of overlapping plucks, so do not count by ear)
    from pdharness import tools

    def notes(d):
        got = tools.probe_patch(str(path), watch=["drift_note"], duration=12.0,
                                controls=[{"receive": "density_ui", "value": d, "at": 0.0}])
        return len(got["watched"]["drift_note"])
    lo, hi = notes(0.1), notes(0.9)
    check("DENSITY 0.1 -> 0.9 plays more notes", hi > 3 * max(lo, 1), f"{lo} -> {hi} notes in 12 s")

    # 3. BRIGHT moves the tone
    def centroid(b):       # with the air bed out: it is not filtered, and would mask the change
        r = render(str(path), RenderSpec(duration=8.0, controls=tuple(
            control.send("bright_ui", b, at=0.0) + control.send("air_ui", 0, at=0.0))))
        return analyze(r.audio, window=(3.0, 8.0)).centroid_hz
    dark, clear = centroid(0.0), centroid(1.0)
    check("BRIGHT 0 -> 1 is brighter", clear > dark * 1.3, f"centroid {dark:.0f} -> {clear:.0f} Hz")

    # 4. LIFT lands near the end of a cut of any length: one end-relative score
    for dur in (19.0, 30.0):
        card = verify(str(path), [expect.change("level", before=(4.0, -6.0), after=(-2.5, None), min=3.0)],
                      spec=RenderSpec(duration=dur, controls=tuple(control.send("lift_ui", 1, at=-5.0))))
        check(f"LIFT sent 5 s before the end of a {dur:g}-s cut rises", card.passed,
              card.scores[0].detail)

    ok = all(checks)
    print(f"{sum(checks)}/{len(checks)} checks", "-- VERIFIED" if ok else "-- NOT VERIFIED")
    return ok


# A family: one patch, a few control sets, a few lengths. The library adds no
# batch format; this loop is the whole of it.
VARIANTS = {
    "dusk": [{"receive": "bright_ui", "value": 0.3}, {"receive": "density_ui", "value": 0.25},
             {"receive": "air_ui", "value": 0.35}],
    "noon": [{"receive": "bright_ui", "value": 0.75}, {"receive": "density_ui", "value": 0.55},
             {"receive": "air_ui", "value": 0.6}],
}
FILE_CLAIMS = [{"name": "seamless"}, {"name": "no_clipping", "args": [0.9]},
               {"name": "band_level", "args": [250], "kwargs": {"min_db": -12, "relative": True}}]


def deliver(path: Path, out_dir: Path | None = None) -> bool:
    from pdharness import tools

    out_dir = out_dir or HERE / "takes"
    ok = True
    for name, controls in VARIANTS.items():
        for seconds in (20, 40):                             # loops: every steady layer closes at 20 s
            r = tools.render_patch(str(path), str(out_dir / f"drift_{name}_{seconds}s.wav"), loop=seconds,
                                   crossfade=2.0, preroll=6.0, controls=controls, sr=48000, bits=24,
                                   rms_dbfs=-20.0, peak_dbfs=-1.0, expectations=FILE_CLAIMS)
            ok &= r["verdict"]["passed"]
            print(f"  {'ok  ' if r['verdict']['passed'] else 'FAIL'} {Path(r['wav']).name}: "
                  f"seam {r['seam']}, {r['master']}")
        # a cut that lifts in its last seconds (not a loop: it has an end)
        lift = controls + [{"receive": "lift_ui", "value": 1, "at": -5.0}]
        r = tools.render_patch(str(path), str(out_dir / f"drift_{name}_cut19s.wav"), duration=19.0,
                               controls=lift, sr=48000, bits=24, rms_dbfs=-20.0, peak_dbfs=-1.0,
                               expectations=[{"name": "change", "args": ["level", [4, -6], [-2.5, None]],
                                              "kwargs": {"min": 3}}, FILE_CLAIMS[1], FILE_CLAIMS[2]])
        ok &= r["verdict"]["passed"]
        print(f"  {'ok  ' if r['verdict']['passed'] else 'FAIL'} {Path(r['wav']).name}: {r['master']}")
    return ok


if __name__ == "__main__":
    path = build()
    print("built ->", path)
    if "--build-only" in sys.argv:
        sys.exit(0)
    if verify_patch(path) and "--no-deliver" not in sys.argv:
        print("delivering ->", "VERIFIED" if deliver(path) else "NOT VERIFIED")
