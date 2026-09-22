"""tend -- a meditation instrument for Pure Data, tended rather than played.

Six dials, seven pads, nothing else. Each dial does one thing you can hear at
once and both of its ends are still music; the pads make the discrete moves
and land them on the bar. Everything else the engine decides. The first
version of tend (five macros, a scale morph, note insertion) verified 49/49
and played badly -- "the only right way to play it is to not touch it" -- so
this is the rework: legible single-purpose dials, DENSITY back, no mode
choices on the surface. See DESIGN.md for the rule and the surface, README.md
for the player's view, field_tests/2026-09-13_tend.md for the round.

What it draws on, named honestly: a Gnawa-derived 12/8 groove (Morocco: the
ternary pulse with its 3-against-2 cross, qraqeb-like metal, a guembri-like
bass), an oud / ney lead on a maqam scale with a quarter-tone degree, a drone
that breathes. A fusion by outsiders, from listening rather than
transcription; none of it reproduces ceremonial music.

Built on pdbuild's Patch (py2pd) with pdbuild.surface and the control modules
that fit (swing_clock, step_tables, scale_degree); the DSP voices are copied
from ember, where each is measured. The verifier holds the instrument to four
contracts on top of the engine checks: every corner of the surface is safe,
every edge of every dial is music, every dial scanned end to end is
continuous and moves its one measurand, and it can be left alone for ten
minutes.

    pdverify/.venv/Scripts/python.exe instruments/tend/build_tend.py
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

from pdbuild import Patch
from pdbuild.modules import gated_value, scale_degree, step_priority, step_tables, swing_clock
from pdbuild.patch import _normalize_escapes
from pdbuild.surface import Control, cc_map, column, control as ui_control, display, note_split
from pdverify import analyze, control
from pdverify.render import RenderSpec, render

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
NAME = "tend"

# =========================================================================
# musical data
# =========================================================================

def _row(s: str, none=0) -> list:
    return [none if t == "." else int(t) for t in s.split()]


REST, HOLD = -99, -98
BARLEN, STEPS = 12, 24                 # 12/8: pulse = 8th, a 2-bar melody loop

# The Gnawa-derived 12/8 family (3+3+3+3), copied from ember. Levels are
# INTENSITY tiers: a hit plays when 0 < level <= INTENSITY (1 sparse, 2 groove,
# 3 full). qlev/qacc/qdbl qraqeb level, accent, double; dlev doum; tlev tek;
# clev clap; bdeg bass scale degree ('.' = rest); blev bass level.
PATTERNS = [
    dict(name="CORE",
         qlev="1 1 1 1 1 1 1 1 1 1 1 1", qacc="1 0 0 0 0 0 1 0 0 0 0 0", qdbl="0 3 2 0 3 2 0 3 2 0 3 2",
         dlev="1 0 0 2 0 0 1 0 0 2 0 0", tlev="0 0 0 0 2 0 0 0 2 0 0 3", clev="0 0 0 3 2 0 0 0 2 3 0 0",
         bdeg="0 . 0 4 . 0 0 . 3 . 4 6", blev="1 0 2 1 0 3 1 0 2 0 2 3"),
    dict(name="HEMIOLA",                    # the 2-against-3 cross on 0 4 8
         qlev="1 1 1 1 1 1 1 1 1 1 1 1", qacc="1 0 0 0 1 0 0 0 1 0 0 0", qdbl="0 2 0 0 2 0 0 2 0 0 2 0",
         dlev="1 0 0 0 2 0 2 0 2 0 0 0", tlev="0 0 2 0 0 0 0 0 0 0 2 3", clev="0 0 0 0 2 0 0 0 2 0 0 0",
         bdeg="0 . . . 3 . . . 4 . . .", blev="1 0 0 0 2 0 0 0 2 0 0 0"),
    dict(name="ROLL",                       # busy: doubles everywhere, teks between
         qlev="1 1 1 1 1 1 1 1 1 1 1 1", qacc="1 0 0 1 0 0 1 0 0 1 0 0", qdbl="0 2 2 0 2 2 0 2 2 0 2 2",
         dlev="1 0 0 2 0 0 1 0 0 2 0 3", tlev="0 2 0 0 2 0 0 2 0 0 2 3", clev="0 0 0 3 0 0 0 0 0 3 0 0",
         bdeg="0 . 0 . 4 4 . 0 . 3 . 6", blev="1 0 2 0 1 3 0 2 0 2 0 3"),
    dict(name="SKELETON",                   # breakdown: the bones of the groove
         qlev="1 2 2 1 2 2 1 2 2 1 2 2", qacc="1 0 0 0 0 0 1 0 0 0 0 0", qdbl="0 0 3 0 0 3 0 0 3 0 0 3",
         dlev="1 0 0 0 0 0 2 0 0 0 0 0", tlev="0 0 0 0 0 0 0 0 3 0 0 0", clev="0 0 0 0 0 0 2 0 0 0 0 0",
         bdeg="0 . . . . . 0 . . . . .", blev="1 0 0 0 0 0 2 0 0 0 0 0"),
]
ROWS = ["qlev", "qacc", "qdbl", "dlev", "tlev", "clev", "bdeg", "blev"]

# Melody seeds: two bars of 12/8 as scale degrees ('.' rest releases the ney, 'h' hold)
PHRASES = [
    ("CALL",   "4 h h 4 5 4 3 h 2 1 h h   0 h h 1 2 1 0 h h . . ."),
    ("RIFF",   "0 . 0 2 . 3 4 . 3 2 . 1   0 . 0 3 . 4 3 . 2 0 . ."),
    ("ASCENT", "0 1 2 3 h 4 5 h 6 7 h h   7 h 6 5 h 4 3 h 2 1 h 0"),
    ("TURN",   "2 3 2 1 h 2 3 4 3 2 h h   1 2 1 0 h h 4 h 3 2 1 0"),
]
PRIO = step_priority(STEPS, BARLEN, 3)     # rank 0 = strongest step (bar downbeats first)
STRONG_RANK = 8                            # ranks below this are beat-level notes: the ney's share

# The one mode: Bayati (D, E half-flat, F, G, A, Bb, C). The neutral second sits
# at the quarter tone (neut 0.5). No mode choice on the surface -- an untrained
# ear cannot know which switch will sound nice, and that was the nervous moment.
SCALE = dict(base=[0, 1, 3, 5, 7, 8, 10], qflag=[0, 1, 0, 0, 0, 0, 0])

# The surface: six dials (name -> (lo, hi, default)), seven pads.
DIALS = dict(tempo=(110, 190, 150), density=(0, 1, 0.55), mutate=(0, 1, 0.12),
             filter=(0, 1, 1.0), storm=(0, 1, 0.15), distance=(0, 1, 0.0))
TEMPO_GLIDE_MS = 2000                      # the dial sets where the band is heading; it gets there in 2 s
# Engine internals with a loadbang value: set by measurement, no dial.
INTERNALS = dict(run=1, tonic=62, neut=0.5, voice=2, slide=0.25, autoplay=1, pattern=0, phrase=0,
                 intensity=2, tier_pending=1, swing=0.12, ornament=0.3, tremolo=0.21,
                 qmix=0.9, dmix=0.9, bmix=0.9, lmix=0.9, drmix=0.5, space=0.35, echo=0.25, breath=0.5,
                 tempo_now=150)

# Arturia MiniLab 3 (factory map): knobs 1-6 = the dials; pads on channel 10
CCMAP = [(74, "tempo", 110, 190), (71, "density", 0, 1), (76, "mutate", 0, 1),
         (77, "filter", 0, 1), (93, "storm", 0, 1), (18, "distance", 0, 1)]
PAD_CHANNEL = 10
PADS = ["stutter (hold)", "killlow (hold)", "nextpattern", "nextintensity", "nextphrase", "droneon (flip)", "record (flip)", "free"]
OSC_IN_PORT, OSC_OUT_PORT = 9000, 9001

MANIFEST = {
    "instrument": NAME,
    "osc": {"in_port": OSC_IN_PORT, "out_port": OSC_OUT_PORT,
            "in": "/<name> <value> sets a control (lands on <name>_ui); /nextpattern /nextintensity /nextphrase "
                  "/snapshot <n> /recall <n>; twins /playdeg <deg> <vel>, /playmidi <note> <vel>, /fakecc <cc> <val>",
            "out": "/pulse <i> /bar /pulsems <ms> /lastdeg <d> /lastmidi <m> /note <deg> <vel> <voice> <startdeg> <glide> "
                   "/mel <len> <steps...> (once per bar) /ctl <name> <value> (every dial move) "
                   "/pattern <n> /intensity <n> /phrase <n> (when a pad lands) /snapshot <name> <value> /gust"},
    "controls": [],
    "gestures": [],
    "twins": ["playdeg", "playmidi", "fakecc", "fakeosc"],
    "cc": [{"cc": cc, "control": n, "lo": lo, "hi": hi} for cc, n, lo, hi in CCMAP],
    "pads": [dict(pad=i + 1, note=36 + i, channel=PAD_CHANNEL, action=a) for i, a in enumerate(PADS)],
    "events_out": ["pulse", "bar", "pulsems", "lastdeg", "lastmidi", "note", "mel", "ctl", "pattern", "intensity", "phrase",
                   "snapshot", "gust"],
    "files": {"takes": "take_NNN.wav next to the patch (RECORD)",
              "snapshot": "snapshot_<n>.txt next to the patch (the six dials + DRONE; SNAPSHOT / RECALL take a slot number)"},
    "about": ("tend is tended, not played: it plays itself, you steer. A meditation instrument by outsiders, made from "
              "listening rather than transcription: a Gnawa-derived 12/8 groove (Morocco: the ternary pulse with its "
              "3-against-2 cross, qraqeb-like metal, a guembri-like bass), an oud / ney lead on a maqam scale with a "
              "quarter-tone degree, a drone that breathes. None of it reproduces ceremonial music and it should not "
              "be presented as one."),
}


def _manifest_control(name, kind, lo, hi, default, label, group):
    MANIFEST["controls"].append(dict(name=name, receive=f"{name}_ui", kind=kind, lo=lo, hi=hi,
                                     default=default, label=label, group=group))


def _manifest_gesture(name, label, group):
    MANIFEST["gestures"].append(dict(name=name, receive=name, label=label, group=group))


# =========================================================================
# builder helpers
# =========================================================================

def raw(p: Patch, text: str, ins: int | None, outs: int | None, x=None, y=None):
    """An object with explicit inlet/outlet counts (for the few objects whose
    arity py2pd would otherwise guess wrong)."""
    px, py = p._place(x, y)
    return p.pd.add(_normalize_escapes(text), x_pos=px, y_pos=py, num_inlets=ins, num_outlets=outs)


def smooth(p: Patch, recv: str, ms: int = 20):
    """[r recv] -> [pack f ms] -> [line~]: a zipper-free control signal."""
    r = p.obj(f"r {recv}"); pk = p.obj(f"pack f {ms}"); ln = p.obj("line~")
    p.chain(r, pk, ln)
    return ln


def lvl(p: Patch, sig, recv: str):
    ln = smooth(p, recv)
    m = p.obj("*~"); p.link(sig, 0, m, 0); p.link(ln, 0, m, 1)
    return m


def loadmsg(p: Patch, text: str):
    m = p.msg(text); p.link(p.loadbang(), 0, m, 0)
    return m


# =========================================================================
# kstring~ -- Karplus-Strong string (ember's, ported to Patch)
# =========================================================================

def build_kstring() -> str:
    """kstring~.pd -- one-sample-latency Karplus-Strong string.

    Under [clone -s 1 kstring~ N fc gain exc_fc scoop]:
      $1 instance   $2 loop lowpass Hz   $3 loop gain   $4 excitation lowpass cap Hz
      $5 scoop flag (1 = fretless scoop into each note, depth/time from [r slide])
    inlet: list <freq Hz> <vel 0..1> <start Hz or 0> <glide ms or 0>
    outlet~: the string. The loop lowpass adds (1-c)/c samples of delay,
    compensated in the delay time so the pitch lands (measured).
    """
    a = Patch(700, 520, 10)
    a.comment("kstring~  Karplus-Strong string in a block~ 1 canvas (1-sample feedback)", 20, 6)
    a.comment("args: arg1 clone# | arg2 loop lowpass Hz | arg3 loop gain | arg4 excite lowpass cap Hz | arg5 scoop on/off", 20, 22)
    a.comment("inlet: freq vel start glide", 20, 38)
    a.obj("block~ 1", 520, 40)
    inl = a.obj("inlet", 20, 55)
    unp = a.obj("unpack f f f f", 20, 75)
    a.link(inl, 0, unp, 0)
    lb = a.obj("loadbang", 250, 40)
    sr = a.obj("samplerate~", 250, 70)
    a.link(lb, 0, sr, 0)
    comp = a.obj("expr (1000/$f1) * (1 - 6.2831853*$2/$f1) / (6.2831853*$2/$f1)", 250, 100)
    a.link(sr, 0, comp, 0)
    rsl = a.obj("r slide", 430, 40)
    dep = a.obj("expr $f1*0.06*$5", 430, 70)
    a.link(rsl, 0, dep, 0)
    gt = a.obj("expr 15 + $f1*110*$5", 430, 100)
    a.link(rsl, 0, gt, 0)
    tf = a.obj("t f f f f", 20, 100)
    a.link(unp, 0, tf, 0)
    exfc = a.obj("expr min(max($f1*4, 600), $4)", 330, 130)
    a.link(tf, 3, exfc, 0)
    blen = a.obj("expr max(2.5, 1200/$f1)", 330, 160)
    a.link(tf, 2, blen, 0)
    exact = a.obj("expr 1000/$f1 - $f2", 20, 160)
    a.link(tf, 0, exact, 0)
    a.link(comp, 0, exact, 1)
    start = a.obj("expr 1000/if($f2>0, $f2, $f1*(1-$f3)) - $f4", 120, 130)
    a.link(tf, 1, start, 0)
    a.link(unp, 2, start, 1)
    a.link(dep, 0, start, 2)
    a.link(comp, 0, start, 3)
    jump = a.msg("$1 0", 120, 160)
    a.link(start, 0, jump, 0)
    gl = a.obj("expr if($f1>0, $f1, $f2)", 430, 130)
    a.link(unp, 3, gl, 0)
    a.link(gt, 0, gl, 1)
    ramp = a.obj("pack f f", 20, 190)
    a.link(exact, 0, ramp, 0)
    a.link(gl, 0, ramp, 1)
    ln = a.obj("line~", 20, 220)
    a.link(jump, 0, ln, 0)
    a.link(ramp, 0, ln, 0)
    vg = a.obj("* 4", 250, 160)
    a.link(unp, 1, vg, 0)
    amp = a.obj("*~", 250, 280)
    a.link(vg, 0, amp, 1)
    burst = a.msg("1 0.3, 0 $1 0.3", 250, 190)
    a.link(blen, 0, burst, 0)
    env = a.obj("vline~", 250, 220)
    a.link(burst, 0, env, 0)
    nz = a.obj("noise~", 330, 220)
    exm = a.obj("*~", 250, 250)
    a.link(nz, 0, exm, 0)
    a.link(env, 0, exm, 1)
    a.link(exm, 0, amp, 0)
    exlp = a.obj("lop~ $4", 250, 310)
    a.link(amp, 0, exlp, 0)
    a.link(exfc, 0, exlp, 1)
    sm = a.obj("+~", 250, 340)
    a.link(exlp, 0, sm, 0)
    dw = a.obj("delwrite~ $0-ks 300", 250, 370)
    a.link(sm, 0, dw, 0)
    vd = a.obj("vd~ $0-ks", 20, 280)
    a.link(ln, 0, vd, 0)
    lp = a.obj("lop~ $2", 20, 310)
    a.link(vd, 0, lp, 0)
    g = a.obj("*~ $3", 20, 340)
    a.link(lp, 0, g, 0)
    a.link(g, 0, sm, 1)
    out = a.obj("outlet~", 250, 420)
    a.link(sm, 0, out, 0)
    return a.render()


# =========================================================================
# the engine
# =========================================================================

def build_main() -> str:
    p = Patch(1500, 900, 10, origin=(780, 40), step=26, bottom=1560, column=185)
    p.comment("TEND -- a meditation instrument. Six dials, seven pads. It plays itself; you steer.", 20, 6)
    p.link(p.loadbang(), 0, p.msg("; pd dsp 1", 1300, 6), 0)

    # ---------------- the surface ----------------
    p.comment("DIALS -- each does one thing; both ends are music", 20, 30)
    labels = dict(tempo="TEMPO  (slow ... fast; the band gets there in two seconds)",
                  density="DENSITY  (none of the melody ... all of it, strong beats first)",
                  mutate="MUTATE  (the tune holds ... keeps rewriting itself)",
                  filter="FILTER  (dark ... open: a resonant dive to 200 Hz on the left)",
                  storm="STORM  (dry ... the dub storm)",
                  distance="DISTANCE  (at the fire ... over the dune)")
    column(p, 20, 50, [Control(n, "hsl", d, labels[n], lo=lo, hi=hi, size=220) for n, (lo, hi, d) in DIALS.items()],
           plumb_dx=(240, 290))
    for n, (lo, hi, d) in DIALS.items():
        _manifest_control(n, "float", lo, hi, d, labels[n], "dials")
    y = 50 + 6 * 58
    p.comment("PADS -- the discrete moves; they land on the next bar", 20, y - 6)
    y += 16
    pads_spec = [("stutter", "tgl", 0, "STUTTER (hold: freeze the last pulse)", "#aa00aa", "momentary"),
                 ("killlow", "tgl", 0, "KILL LOW (hold: drums and bass out)", "#0055cc", "momentary"),
                 ("nextpattern", "bng", None, "PATTERN+ (next groove variant, on the bar)", "#00aa66", "gesture"),
                 ("nextintensity", "bng", None, "INTENSITY+ (sparse / groove / full, on the bar)", "#00aa66", "gesture"),
                 ("nextphrase", "bng", None, "PHRASE+ (re-seed the tune, at the loop's end)", "#cc8800", "gesture"),
                 ("droneon", "tgl", 1, "DRONE (on / off)", "#666600", "toggle"),
                 ("record", "tgl", 0, "RECORD (a take: take_NNN.wav next to the patch)", "#cc0000", "toggle")]
    for i, (name, kind, default, label, color, mkind) in enumerate(pads_spec):
        ui_control(p, name, kind, x=20 + (i % 4) * 130, y=y + (i // 4) * 44, default=default, label=None, color=color,
                   plumb_dx=(560 + (i % 4) * 60, 560 + (i % 4) * 60), label_at=None)
        p.comment(label.split(" (")[0], 20 + (i % 4) * 130 + 26, y + (i // 4) * 44 + 4)
        if mkind == "gesture":
            _manifest_gesture(name, label, "pads")
        else:
            _manifest_control(name, mkind, 0, 1, default, label, "pads")
    _manifest_gesture("snapshot", "SNAPSHOT <slot> (save the dials to snapshot_<n>.txt)", "scenes")
    _manifest_gesture("recall", "RECALL <slot> (load them back)", "scenes")
    y += 100
    p.comment("stutter / kill low: hold. pattern+ intensity+: land on the next bar. phrase+: at the loop's end. drone, record: flip.", 20, y)
    y += 30
    p.comment("last note:  degree / MIDI (x.5 = quarter tone)", 20, y)
    display(p, "lastdeg", 20, y + 20)
    display(p, "lastmidi", 90, y + 20)
    p.comment("LAST CC seen:", 200, y)
    display(p, "lastcc", 200, y + 20, width=5)
    display(p, "lastccval", 250, y + 20, width=5)
    p.comment("MiniLab 3: knobs 1-6 = TEMPO DENSITY MUTATE FILTER STORM DISTANCE | pads 1-7 = the pad row (pads on ch 10)", 380, 30)
    p.comment("keys (ch 1) = scale degrees, C4 = tonic (the expert path) | computer keys a s d f g h j k l ; '", 380, 48)
    p.comment(f"API: OSC in UDP {OSC_IN_PORT} (/density 0.7, /nextpattern, /snapshot 2 ...), OSC out UDP {OSC_OUT_PORT}", 380, 74)
    p.comment("(/pulse /bar /note /mel /ctl /pattern /intensity /phrase ...). Manifest: tend.json. Mouse face: tend_play.pd (needs ELSE).", 380, 92)
    p.comment("Every internal control (tempo_now, intensity, pattern, phrase, swing, tonic, the bus levels ...) is still a receive for scripts and tests.", 380, 118)

    # ================= machinery (flows in columns to the right) =============
    p.cursor(780, 200)

    # ---- tables + internals ------------------------------------------------
    p.comment("-- tables, the one mode, the internals --")
    p.obj("table scale 8"); p.obj("table qflag 8")
    p.obj("table mel 24"); p.obj("table prio 24")
    loadmsg(p, "; scale 0 " + " ".join(map(str, SCALE["base"])) + " ; qflag 0 " + " ".join(map(str, SCALE["qflag"]))
            + " ; prio 0 " + " ".join(map(str, PRIO)))
    for name, val in INTERNALS.items():
        m = loadmsg(p, str(val)); s = p.obj(f"s {name}"); p.link(m, 0, s, 0)

    # ---- TEMPO: the dial is a destination; the band glides there ---------------
    p.comment("-- TEMPO dial -> [line] glide -> tempo_now (the clock's tempo) --")
    #   [change 150]: the dial's own init is not a move (a [line] re-sends its value every grain for the
    #   whole ramp, which would override anything that set tempo_now directly in those two seconds)
    rtd = p.obj("r tempo"); tch = p.obj(f"change {DIALS['tempo'][2]}"); tpk = p.obj(f"pack f {TEMPO_GLIDE_MS}")
    tln = p.obj(f"line {DIALS['tempo'][2]} 20"); stn = p.obj("s tempo_now")
    p.chain(rtd, tch, tpk, tln, stn)

    # ---- pads: cycle logic and the latches that land them on the bar -------------
    p.comment("-- pads: PATTERN+ / INTENSITY+ latch to the bar's last pulse (no reset hiccup); PHRASE+ to the loop's end --")

    def cycle(trigger: str, pending: str, n: int, init: int | None = None):
        rt_ = p.obj(f"r {trigger}"); f_ = p.obj("f"); rp_ = p.obj(f"r {pending}")
        p.link(rt_, 0, f_, 0); p.link(rp_, 0, f_, 1)
        inc = p.obj("+ 1"); md = p.obj(f"mod {n}"); s_ = p.obj(f"s {pending}")
        p.chain(f_, inc, md, s_)
        if init is not None:
            im = loadmsg(p, str(init)); sp_ = p.obj(f"s {pending}"); p.link(im, 0, sp_, 0)

    def latch(pending: str, out: str, loop_end: bool = False, plus: int = 0, tag: str | None = None):
        """On the bar's last pulse (or the loop's), emit the pending value if it changed."""
        rp_ = p.obj("r pulse"); sl = p.obj("sel 11"); p.link(rp_, 0, sl, 0)
        src = sl
        if loop_end:
            pf = p.obj("f"); rlp = p.obj("r looppar"); p.link(rlp, 0, pf, 1); p.link(sl, 0, pf, 0)
            s1 = p.obj("sel 1"); p.link(pf, 0, s1, 0); src = s1
        f_ = p.obj("f"); rpd = p.obj(f"r {pending}"); p.link(rpd, 0, f_, 1); p.link(src, 0, f_, 0)
        node = f_
        if plus:
            pl = p.obj(f"+ {plus}"); p.link(f_, 0, pl, 0); node = pl
        ch = p.obj("change"); p.link(node, 0, ch, 0)
        st = p.msg("set $1"); rcur = p.obj(f"r {out}"); p.link(rcur, 0, st, 0); p.link(st, 0, ch, 0)   # a direct set keeps the latch honest
        so = p.obj(f"s {out}"); p.link(ch, 0, so, 0)
        if tag:
            pr = p.obj(f"print {tag}"); p.link(ch, 0, pr, 0)

    cycle("nextpattern", "pattern_pending", len(PATTERNS))
    latch("pattern_pending", "pattern", tag="groove")
    cycle("nextintensity", "tier_pending", 3)                  # tier_pending 0..2 -> intensity 1..3 (init 1 = groove)
    latch("tier_pending", "intensity", plus=1, tag="tier")
    cycle("nextphrase", "phrase_pending", len(PHRASES))
    latch("phrase_pending", "phrase", loop_end=True, tag="page")
    #   a direct set (a script, a test, a scene) is the new pending value too -- otherwise the latch
    #   would revert it on the next bar (measured: every timing check broke that way)
    for src, dst, delta in (("pattern", "pattern_pending", 0), ("intensity", "tier_pending", -1), ("phrase", "phrase_pending", 0)):
        r_ = p.obj(f"r {src}"); s_ = p.obj(f"s {dst}")
        if delta:
            d_ = p.obj(f"+ {delta}"); p.link(r_, 0, d_, 0); p.link(d_, 0, s_, 0)
        else:
            p.link(r_, 0, s_, 0)
    for name in ("droneon", "record"):                          # MIDI pads flip these against the current value
        rf_ = p.obj(f"r flip_{name}"); ff = p.obj("f"); rc_ = p.obj(f"r {name}")
        p.link(rf_, 0, ff, 0); p.link(rc_, 0, ff, 1)
        eq = p.obj("== 0"); so = p.obj(f"s {name}_ui"); p.chain(ff, eq, so)

    # ---- clock + patterns (pdbuild.modules) ------------------------------------
    p.comment("-- clock: swing_clock (pulse = 8th, per-pulse retime = swing), reading tempo_now --")
    clock = swing_clock(p, groups=(3, 3, 3, 3), tempo_recv="tempo_now")
    p.comment("-- patterns: step_tables (one message per variant, INTENSITY tiers, reset on change) --")
    presets = [{r: _row(m[r], none=REST if r == "bdeg" else 0) for r in ROWS} for m in PATTERNS]
    tabs = step_tables(p, presets, rows=ROWS, gate_rows=["qdbl", "dlev", "tlev", "clev"])
    qacc = gated_value(p, tabs, "qlev", "qacc"); sqh = p.obj("s qhit"); p.link(qacc, 0, sqh, 0)
    ddel = p.obj("del 90"); p.link(tabs.hits["qdbl"], 0, ddel, 0)
    rh = p.obj("r halfpulse"); p.link(rh, 0, ddel, 1)
    dz = p.msg("0"); p.link(ddel, 0, dz, 0); p.link(dz, 0, sqh, 0)
    for row, snd in (("dlev", "doum"), ("tlev", "tek"), ("clev", "clap")):
        s = p.obj(f"s {snd}"); p.link(tabs.hits[row], 0, s, 0)
    bdeg = gated_value(p, tabs, "blev", "bdeg"); sbd = p.obj("s bass_deg"); p.link(bdeg, 0, sbd, 0)

    # ---- percussion voices (ember's, measured) ------------------------------------
    p.comment("-- qraqeb: noise burst -> metallic resonator bank --")
    rq = p.obj("r qhit"); qt = p.obj("t b b f"); p.link(rq, 0, qt, 0)
    qamp = p.obj("expr (0.45 + 0.4*$f1) * (0.9 + 0.2*$f2/100)"); p.link(qt, 2, qamp, 0)
    qrnd = p.obj("random 100"); p.link(qt, 1, qrnd, 0); p.link(qrnd, 0, qamp, 1)
    qvca = p.obj("*~"); p.link(qamp, 0, qvca, 1)
    qring = p.obj("sel 0"); p.link(qt, 2, qring, 0)
    qr0 = p.msg("1 0.3, 0 55 0.3"); qr1 = p.msg("1 0.3, 0 100 0.3")
    p.link(qring, 0, qr0, 0); p.link(qring, 1, qr1, 0)
    qrenv = p.obj("vline~"); p.link(qr0, 0, qrenv, 0); p.link(qr1, 0, qrenv, 0)
    qburst = p.msg("1 0.2, 0 3.5 0.2"); p.link(qt, 0, qburst, 0)
    qbenv = p.obj("vline~"); p.link(qburst, 0, qbenv, 0)
    qnz = p.obj("noise~"); qex = p.obj("*~"); p.link(qnz, 0, qex, 0); p.link(qbenv, 0, qex, 1)
    prev = None
    for f, q, gn in ((2350, 16, 1.0), (3700, 20, 0.85), (5900, 24, 0.65), (8800, 18, 0.5)):
        bp = p.obj(f"bp~ {f} {q}"); p.link(qex, 0, bp, 0)
        gg = p.obj(f"*~ {gn}"); p.link(bp, 0, gg, 0)
        if prev is None:
            prev = gg
        else:
            ad = p.obj("+~"); p.link(prev, 0, ad, 0); p.link(gg, 0, ad, 1); prev = ad
    qclick = p.obj("hip~ 3000"); qcg = p.obj("*~ 0.25"); p.link(qex, 0, qclick, 0); p.link(qclick, 0, qcg, 0)
    qsum = p.obj("+~"); p.link(prev, 0, qsum, 0); p.link(qcg, 0, qsum, 1)
    qring_m = p.obj("*~"); p.link(qsum, 0, qring_m, 0); p.link(qrenv, 0, qring_m, 1)
    p.link(qring_m, 0, qvca, 0)
    qhp = p.obj("hip~ 1200"); p.link(qvca, 0, qhp, 0)
    qout = p.obj("*~ 2.2"); p.link(qhp, 0, qout, 0)

    p.comment("-- tbel doum / tek / claps --")
    rd = p.obj("r doum")
    dpe = p.msg("140, 68 45"); dae = p.msg("1 1.5, 0 200 1.5"); dce = p.msg("1 0.2, 0 7 0.2")
    p.link(rd, 0, dpe, 0); p.link(rd, 0, dae, 0); p.link(rd, 0, dce, 0)
    dpv = p.obj("vline~"); dav = p.obj("vline~"); dcv = p.obj("vline~")
    p.link(dpe, 0, dpv, 0); p.link(dae, 0, dav, 0); p.link(dce, 0, dcv, 0)
    dosc = p.obj("osc~"); p.link(dpv, 0, dosc, 0)
    dvca = p.obj("*~"); p.link(dosc, 0, dvca, 0); p.link(dav, 0, dvca, 1)
    dsat = p.obj("expr~ tanh($v1*1.4)"); p.link(dvca, 0, dsat, 0)
    dnz = p.obj("noise~"); dcm = p.obj("*~"); p.link(dnz, 0, dcm, 0); p.link(dcv, 0, dcm, 1)
    dcbp = p.obj("bp~ 800 1.5"); p.link(dcm, 0, dcbp, 0)
    dcgn = p.obj("*~ 0.6"); p.link(dcbp, 0, dcgn, 0)
    dsum = p.obj("+~"); p.link(dsat, 0, dsum, 0); p.link(dcgn, 0, dsum, 1)
    dlp = p.obj("lop~ 1400"); p.link(dsum, 0, dlp, 0)
    dout = p.obj("*~ 0.5"); p.link(dlp, 0, dout, 0)
    rtk = p.obj("r tek")
    tke = p.msg("1 0.3, 0 60 0.3"); tpe = p.msg("1 0.3, 0 22 0.3")
    p.link(rtk, 0, tke, 0); p.link(rtk, 0, tpe, 0)
    tkv = p.obj("vline~"); tpv = p.obj("vline~"); p.link(tke, 0, tkv, 0); p.link(tpe, 0, tpv, 0)
    tnz = p.obj("noise~"); tkm = p.obj("*~"); p.link(tnz, 0, tkm, 0); p.link(tkv, 0, tkm, 1)
    tb1 = p.obj("bp~ 2100 6"); tb2 = p.obj("bp~ 3700 8"); p.link(tkm, 0, tb1, 0); p.link(tkm, 0, tb2, 0)
    tbs = p.obj("+~"); p.link(tb1, 0, tbs, 0); p.link(tb2, 0, tbs, 1)
    tping = p.obj("osc~ 1180"); tpm = p.obj("*~"); p.link(tping, 0, tpm, 0); p.link(tpv, 0, tpm, 1)
    tpg = p.obj("*~ 0.3"); p.link(tpm, 0, tpg, 0)
    tsum = p.obj("+~"); p.link(tbs, 0, tsum, 0); p.link(tpg, 0, tsum, 1)
    thp = p.obj("hip~ 900"); p.link(tsum, 0, thp, 0)
    tout = p.obj("*~ 0.7"); p.link(thp, 0, tout, 0)
    rcl = p.obj("r clap")
    ce = p.msg("1 0.5, 0.15 8 0.5, 1 0.5 9, 0.15 8 10, 1 0.5 19, 0 160 20"); p.link(rcl, 0, ce, 0)
    cv = p.obj("vline~"); p.link(ce, 0, cv, 0)
    cnz = p.obj("noise~"); cm = p.obj("*~"); p.link(cnz, 0, cm, 0); p.link(cv, 0, cm, 1)
    cbp = p.obj("bp~ 1150 2.5"); p.link(cm, 0, cbp, 0)
    chp = p.obj("hip~ 500"); p.link(cbp, 0, chp, 0)
    cout = p.obj("*~ 1.1"); p.link(chp, 0, cout, 0)

    # ---- bass: guembri (ember's) --------------------------------------------------
    p.comment("-- guembri: kstring~ (low, damped) + thump + sersera rattle; two octaves below the lead --")
    rbd = p.obj("r bass_deg"); bm14 = p.obj("- 14"); p.link(rbd, 0, bm14, 0)
    bmq = scale_degree(p, bm14); bmt = p.obj("mtof"); p.link(bmq, 0, bmt, 0)
    btf2 = p.obj("t f f f"); p.link(bmt, 0, btf2, 0)
    bvel = p.obj("expr 0.7 + 0.25*$f2/100"); brnd = p.obj("random 100"); bbng = p.obj("t b")
    p.link(btf2, 2, bbng, 0); p.link(bbng, 0, brnd, 0); p.link(brnd, 0, bvel, 1)
    bpk = p.obj("pack f f"); p.link(btf2, 1, bvel, 0); p.link(bvel, 0, bpk, 1)
    bmsg = p.msg("1 $1 $2 0 0"); p.link(btf2, 0, bpk, 0); p.link(bpk, 0, bmsg, 0)
    bcl = raw(p, "clone -s 1 kstring~ 1 1200 0.992 900 0", 1, 1); p.link(bmsg, 0, bcl, 0)
    bthe = p.msg("1 1, 0 70 1"); p.link(btf2, 0, bthe, 0)
    bthv = p.obj("vline~"); p.link(bthe, 0, bthv, 0)
    bosc = p.obj("osc~"); p.link(btf2, 1, bosc, 0)
    bthm = p.obj("*~"); p.link(bosc, 0, bthm, 0); p.link(bthv, 0, bthm, 1)
    bthg = p.obj("*~ 0.45"); p.link(bthm, 0, bthg, 0)
    brat = p.msg("0.6 1, 0 45 1"); p.link(btf2, 0, brat, 0)
    bratv = p.obj("vline~"); p.link(brat, 0, bratv, 0)
    bnz = p.obj("noise~"); bratm = p.obj("*~"); p.link(bnz, 0, bratm, 0); p.link(bratv, 0, bratm, 1)
    bratb = p.obj("bp~ 3200 5"); p.link(bratm, 0, bratb, 0)
    bratg = p.obj("*~ 0.12"); p.link(bratb, 0, bratg, 0)
    bs1 = p.obj("+~"); p.link(bcl, 0, bs1, 0); p.link(bthg, 0, bs1, 1)
    bs2 = p.obj("+~"); p.link(bs1, 0, bs2, 0); p.link(bratg, 0, bs2, 1)
    bsat = p.obj("expr~ tanh($v1*1.3)"); p.link(bs2, 0, bsat, 0)
    bout = p.obj("*~ 0.65"); p.link(bsat, 0, bout, 0)

    # ---- input: MIDI keys (degrees), pads, CCs, computer keys ----
    p.comment("-- input: note_split (pads on ch 10) | keys -> degrees (C4 = tonic) | pads -> the pad row | cc_map --")
    note_split(p, pad_channel=PAD_CHANNEL, x=p.x, y=p.y); p.cursor(p.x + 185, 40)
    rmi = p.obj("r midi_in"); mun = p.obj("unpack f f"); p.link(rmi, 0, mun, 0)
    vtf = p.obj("t f f"); p.link(mun, 1, vtf, 0)
    onpk = p.obj("pack f f"); p.link(vtf, 1, onpk, 1)
    vgt = p.obj("> 0"); p.link(vtf, 0, vgt, 0)
    vtf2 = p.obj("t f f"); p.link(vgt, 0, vtf2, 0)
    sp_on = p.obj("spigot"); sp_off = p.obj("spigot"); p.link(vtf2, 1, sp_on, 1)
    veq = p.obj("== 0"); p.link(vtf2, 0, veq, 0); p.link(veq, 0, sp_off, 1)
    nm60 = p.obj("- 60"); p.link(mun, 0, nm60, 0)
    ntf = p.obj("t f f"); p.link(nm60, 0, ntf, 0); p.link(ntf, 1, sp_off, 0)
    sloff = p.obj("s lead_off"); p.link(sp_off, 0, sloff, 0)
    p.link(ntf, 0, onpk, 0); p.link(onpk, 0, sp_on, 0)
    ktl = p.obj("t l b"); p.link(sp_on, 0, ktl, 0)          # hand-played notes are strong: the ney takes them
    kny = p.msg("1"); p.link(ktl, 1, kny, 0); kns = p.obj("s neyok"); p.link(kny, 0, kns, 0)
    snin = p.obj("s note_in"); p.link(ktl, 0, snin, 0)
    #   pads: 36 stutter, 37 killlow (held), 38 pattern+, 39 intensity+, 40 phrase+, 41 flip drone, 42 flip record
    rpi = p.obj("r pad_in"); pun = p.obj("unpack f f"); p.link(rpi, 0, pun, 0)
    pvt = p.obj("t f f"); p.link(pun, 1, pvt, 0)
    von = p.obj("> 0"); voff = p.obj("== 0"); p.link(pvt, 1, von, 0); p.link(pvt, 0, voff, 0)
    spon = p.obj("spigot"); spoff = p.obj("spigot"); p.link(von, 0, spon, 1); p.link(voff, 0, spoff, 1)
    pn36 = p.obj("- 36"); pnm = p.obj("mod 8"); p.link(pun, 0, pn36, 0); p.link(pn36, 0, pnm, 0)
    pnt = p.obj("t f f"); p.link(pnm, 0, pnt, 0); p.link(pnt, 1, spoff, 0); p.link(pnt, 0, spon, 0)
    selon = p.obj("sel 0 1 2 3 4 5 6"); p.link(spon, 0, selon, 0)
    seloff = p.obj("sel 0 1"); p.link(spoff, 0, seloff, 0)
    for i, nm in ((0, "stutter_ui"), (1, "killlow_ui")):
        m1 = p.msg("1"); p.link(selon, i, m1, 0); s1 = p.obj(f"s {nm}"); p.link(m1, 0, s1, 0)
        m0 = p.msg("0"); p.link(seloff, i, m0, 0); s0 = p.obj(f"s {nm}"); p.link(m0, 0, s0, 0)
    for i, nm in ((2, "nextpattern"), (3, "nextintensity"), (4, "nextphrase"), (5, "flip_droneon"), (6, "flip_record")):
        s_ = p.obj(f"s {nm}"); p.link(selon, i, s_, 0)
    cc_map(p, CCMAP, x=p.x, y=p.y); p.cursor(p.x + 440, 40)
    keycodes = [97, 115, 100, 102, 103, 104, 106, 107, 108, 59, 39, 113, 119, 101, 114, 116, 121, 117, 105, 111, 112, 91, 93]
    ksel_on = p.obj("sel " + " ".join(map(str, keycodes))); ksel_off = p.obj("sel " + " ".join(map(str, keycodes)))
    key = p.obj("key"); keyup = p.obj("keyup"); p.link(key, 0, ksel_on, 0); p.link(keyup, 0, ksel_off, 0)
    smi = p.obj("s midi_in")
    kon = p.obj("pack f 100"); koff = p.obj("pack f 0"); p.link(kon, 0, smi, 0); p.link(koff, 0, smi, 0)
    for i, code in enumerate(keycodes):
        note = 60 + (i if i < 11 else 7 + (i - 11))
        m_on = p.msg(str(note)); m_off = p.msg(str(note))
        p.link(ksel_on, i, m_on, 0); p.link(m_on, 0, kon, 0)
        p.link(ksel_off, i, m_off, 0); p.link(m_off, 0, koff, 0)

    # ---- OSC: the API for any face -------------------------------------------------
    p.comment(f"-- OSC in (UDP {OSC_IN_PORT}): /name value -> name_ui | gestures | twins; [r fakeosc] = test twin --")
    onr = raw(p, f"netreceive -u -b {OSC_IN_PORT}", 1, 1)
    opa = raw(p, "oscparse", 1, 1); p.link(onr, 0, opa, 0)
    olt = p.obj("list trim"); p.link(opa, 0, olt, 0)
    sos = p.obj("s oscstream"); p.link(olt, 0, sos, 0)
    rfo = p.obj("r fakeosc"); sos2 = p.obj("s oscstream"); p.link(rfo, 0, sos2, 0)
    ros = p.obj("r oscstream")
    osc_targets = ([(c["name"], c["receive"]) for c in MANIFEST["controls"]]
                   + [(g["name"], g["receive"]) for g in MANIFEST["gestures"]]
                   + [(t, t) for t in ("playdeg", "playmidi", "fakecc")])
    ort = p.obj("route " + " ".join(n for n, _ in osc_targets)); p.link(ros, 0, ort, 0)
    for i, (_, tgt) in enumerate(osc_targets):
        s_ = p.obj(f"s {tgt}"); p.link(ort, i, s_, 0)
    r = p.obj("r playdeg"); ptl = p.obj("t l b"); p.link(r, 0, ptl, 0)
    pny = p.msg("1"); p.link(ptl, 1, pny, 0); pnys = p.obj("s neyok"); p.link(pny, 0, pnys, 0)
    sn = p.obj("s note_in"); p.link(ptl, 0, sn, 0)
    r = p.obj("r playmidi"); sm_ = p.obj("s midi_in"); p.link(r, 0, sm_, 0)
    p.comment(f"-- OSC out (UDP {OSC_OUT_PORT}): pulse bar pulsems lastdeg lastmidi note mel ctl pattern intensity phrase snapshot gust --")
    ons = raw(p, "netsend -u -b", 1, 1)
    ocon = p.msg(f"connect 127.0.0.1 {OSC_OUT_PORT}"); p.link(p.loadbang(), 0, ocon, 0); p.link(ocon, 0, ons, 0)
    opre = p.obj("list prepend send"); otr = p.obj("list trim"); p.link(opre, 0, otr, 0); p.link(otr, 0, ons, 0)
    for name in ("pulse", "pulsems", "lastdeg", "lastmidi", "gust", "bar", "pattern", "intensity", "phrase"):
        r_ = p.obj(f"r {name}"); of_ = raw(p, f"oscformat {name}", 1, 1); p.link(r_, 0, of_, 0); p.link(of_, 0, opre, 0)
    rn_ = p.obj("r lead_on"); ofn = raw(p, "oscformat note", 1, 1); p.link(rn_, 0, ofn, 0); p.link(ofn, 0, opre, 0)
    rb2 = p.obj("r bar"); agm = raw(p, "array get mel", 3, 1); p.link(rb2, 0, agm, 0)
    mlp = p.obj(f"list prepend {STEPS}"); ofm = raw(p, "oscformat mel", 1, 1)
    p.link(agm, 0, mlp, 0); p.link(mlp, 0, ofm, 0); p.link(ofm, 0, opre, 0)
    ofc = raw(p, "oscformat ctl", 1, 1); p.link(ofc, 0, opre, 0)
    for name in DIALS:
        r_ = p.obj(f"r {name}"); lp_ = p.obj(f"list prepend {name}"); p.link(r_, 0, lp_, 0); p.link(lp_, 0, ofc, 0)

    # ---- SNAPSHOT / RECALL: the dials (+ DRONE) as '<name>_ui <value>;' in snapshot_<n>.txt ----
    p.comment("-- SNAPSHOT <n>: [textfile] add <dial>_ui <value>, write snapshot_<n>.txt ; RECALL <n>: read, then '; $1 $2' per line --")
    tfl = raw(p, "textfile", 1, 2)
    rsn = p.obj("r snapshot"); snn = p.obj("t b b f"); p.link(rsn, 0, snn, 0)
    snf = raw(p, "makefilename snapshot_%d.txt", 1, 1); p.link(snn, 2, snf, 0)
    sns = p.obj("symbol"); p.link(snf, 0, sns, 1)
    snt = p.obj("t b b"); p.link(snn, 1, snt, 0)
    clr = p.msg("clear"); p.link(snt, 1, clr, 0); p.link(clr, 0, tfl, 0)
    p.link(snn, 0, sns, 0)
    wrt = p.msg("write $1"); p.link(sns, 0, wrt, 0); p.link(wrt, 0, tfl, 0)
    ofs = raw(p, "oscformat snapshot", 1, 1); p.link(ofs, 0, opre, 0)
    SCENE = list(DIALS) + ["droneon"]
    for name in SCENE:
        f_ = p.obj("f"); r_ = p.obj(f"r {name}"); p.link(r_, 0, f_, 1); p.link(snt, 0, f_, 0)
        m_ = p.msg(f"add {name}_ui $1"); p.link(f_, 0, m_, 0); p.link(m_, 0, tfl, 0)
        lp_ = p.obj(f"list prepend {name}"); p.link(f_, 0, lp_, 0); p.link(lp_, 0, ofs, 0)
    rrc = p.obj("r recall"); rct = p.obj("t b b f"); p.link(rrc, 0, rct, 0)
    rcf = raw(p, "makefilename snapshot_%d.txt", 1, 1); p.link(rct, 2, rcf, 0)
    rcs = p.obj("symbol"); p.link(rcf, 0, rcs, 1); p.link(rct, 1, rcs, 0)
    rdm = p.msg("read $1, rewind"); p.link(rcs, 0, rdm, 0); p.link(rdm, 0, tfl, 0)
    unt = p.obj("until"); p.link(rct, 0, unt, 0); p.link(unt, 0, tfl, 0); p.link(tfl, 1, unt, 1)
    lst = p.obj("list"); p.link(tfl, 0, lst, 0)
    snd = p.msg("; $1 $2"); p.link(lst, 0, snd, 0)
    #   every 32 bars, print the tune (the unattended test reads it; harmless in use)
    rbm_ = p.obj("r bar"); mcnt = p.obj("f"); minc = p.obj("+ 1"); mmod = p.obj("mod 32")
    p.link(rbm_, 0, mcnt, 0); p.link(mcnt, 0, minc, 0); p.link(minc, 0, mmod, 0); p.link(mmod, 0, mcnt, 1)
    msel0 = p.obj("sel 0"); p.link(mcnt, 0, msel0, 0)
    mag = raw(p, "array get mel", 3, 1); p.link(msel0, 0, mag, 0)
    mpr = p.obj("print melody"); p.link(mag, 0, mpr, 0)

    # ---- the loop: ember's v4 Turing-machine loop, fixed at 24 steps of 12/8 ----
    p.comment("-- the loop: step = pulse + 12*parity; DENSITY priority mask; MUTATE rewrites (scale-aware, gravity) --")
    rphr = p.obj("r phrase"); phsel = p.obj("sel 0 1 2 3"); p.link(rphr, 0, phsel, 0)
    for i, (_, toks) in enumerate(PHRASES):
        vals = [REST if t == "." else HOLD if t == "h" else int(t) for t in toks.split()]
        assert len(vals) == STEPS
        pm = p.msg("; mel 0 " + " ".join(map(str, vals))); p.link(phsel, i, pm, 0)
    rbar2 = p.obj("r bar"); parf = p.obj("f"); parinc = p.obj("+ 1"); parmod = p.obj("mod 2")
    p.link(rbar2, 0, parf, 0); p.link(parf, 0, parinc, 0); p.link(parinc, 0, parmod, 0); p.link(parmod, 0, parf, 1)
    rrst = p.obj("r reset"); pz = p.msg("0"); p.link(rrst, 0, pz, 0); p.link(pz, 0, parf, 1)
    spar = p.obj("s looppar"); p.link(parf, 0, spar, 0)
    par12 = p.obj("* 12"); p.link(parf, 0, par12, 0)
    rpa = p.obj("r pulse"); aspg = p.obj("spigot"); p.link(rpa, 0, aspg, 0)
    rauto = p.obj("r autoplay"); p.link(rauto, 0, aspg, 1)
    stp = p.obj("+"); p.link(aspg, 0, stp, 0); p.link(par12, 0, stp, 1)
    st4 = p.obj("t f f f f"); p.link(stp, 0, st4, 0)
    tpr = p.obj("tabread prio"); p.link(st4, 3, tpr, 0)
    prt = p.obj("t f f f"); p.link(tpr, 0, prt, 0)
    actlt = p.obj("<"); p.link(prt, 2, actlt, 0)
    rden = p.obj("r density"); d24 = p.obj("* 24"); p.link(rden, 0, d24, 0); p.link(d24, 0, actlt, 1)
    strlt = p.obj(f"< {STRONG_RANK}"); p.link(prt, 1, strlt, 0)
    strf = p.obj("f"); p.link(strlt, 0, strf, 1)
    ttk = p.obj("tabread mel"); p.link(st4, 2, ttk, 0)
    tkt = p.obj("t f f"); p.link(ttk, 0, tkt, 0)
    tokf = p.obj("f"); p.link(tkt, 0, tokf, 1)
    bmo = p.obj("moses -97.5"); p.link(tkt, 1, bmo, 0)
    mtb = p.obj("t b f"); p.link(st4, 1, mtb, 0)
    twr = raw(p, "tabwrite mel", 2, 0); p.link(mtb, 1, twr, 1)
    mrn = p.obj("random 1000"); p.link(mtb, 0, mrn, 0)
    mlt = p.obj("<"); p.link(mrn, 0, mlt, 0)
    rmut = p.obj("r mutate"); m1000 = p.obj("* 1000"); p.link(rmut, 0, m1000, 0); p.link(m1000, 0, mlt, 1)
    msel1 = p.obj("sel 1"); p.link(mlt, 0, msel1, 0)
    grn = p.obj("random 100"); p.link(msel1, 0, grn, 0)
    # every [random] is banged through [t b]: a float into its left inlet sets the range (the v1-v3 drift bug)
    gm1 = p.obj("moses 50"); p.link(grn, 0, gm1, 0)
    g1b = p.obj("t b"); p.link(gm1, 0, g1b, 0)
    g1 = p.obj("random 2"); p.link(g1b, 0, g1, 0)
    g1e = p.obj("expr if($f2>7, -1, if($f2<1, 1, 2*$f1-1))")          # gravity: down above the octave, up at the tonic
    p.link(g1, 0, g1e, 0); p.link(bmo, 1, g1e, 1)
    gadd = p.obj("+ 4"); p.link(bmo, 1, gadd, 1); p.link(g1e, 0, gadd, 0)
    gclip = p.obj("clip -3 10"); p.link(gadd, 0, gclip, 0); p.link(gclip, 0, twr, 0)
    gm2 = p.obj("moses 65"); p.link(gm1, 1, gm2, 0)
    g2b = p.obj("t b"); p.link(gm2, 0, g2b, 0)
    g2 = p.obj("random 2"); p.link(g2b, 0, g2, 0)
    g2e = p.obj("expr if($f2>6, -2, if($f2<2, 2, 4*$f1-2))")
    p.link(g2, 0, g2e, 0); p.link(bmo, 1, g2e, 1); p.link(g2e, 0, gadd, 0)
    gm3 = p.obj("moses 80"); p.link(gm2, 1, gm3, 0)
    gjb = p.obj("t b"); p.link(gm3, 0, gjb, 0)
    gj = p.obj("random 3"); gjs = p.obj("sel 0 1 2"); p.link(gjb, 0, gj, 0); p.link(gj, 0, gjs, 0)
    for i, v in enumerate((0, 4, 7)):                                    # leaps: tonic, fifth, octave
        jm = p.msg(str(v)); p.link(gjs, i, jm, 0); p.link(jm, 0, twr, 0)
    gm4 = p.obj("moses 90"); p.link(gm3, 1, gm4, 0)
    grest = p.msg(str(REST)); p.link(gm4, 0, grest, 0); p.link(grest, 0, twr, 0)
    ghold = p.msg(str(HOLD)); p.link(gm4, 1, ghold, 0); p.link(ghold, 0, twr, 0)
    ptb = p.obj("t b"); p.link(st4, 0, ptb, 0); p.link(ptb, 0, tokf, 0)
    pmo1 = p.obj("moses -98.5"); p.link(tokf, 0, pmo1, 0)
    relb = p.obj("t b"); p.link(pmo1, 0, relb, 0)
    snr = p.obj("s ney_release"); p.link(relb, 0, snr, 0)
    pmo2 = p.obj("moses -97.5"); p.link(pmo1, 1, pmo2, 0)
    pact = p.obj("spigot"); p.link(pmo2, 1, pact, 0); p.link(actlt, 0, pact, 1)
    etf = p.obj("t f b b"); p.link(pact, 0, etf, 0)
    p.link(etf, 2, strf, 0)
    sny = p.obj("s neyok"); p.link(strf, 0, sny, 0)
    vrn = p.obj("random 15"); p.link(etf, 1, vrn, 0)
    vex = p.obj("expr 70 + if($f2<4, 30, if($f2<12, 15, 0)) + $f1"); p.link(vrn, 0, vex, 0); p.link(prt, 0, vex, 1)
    epk = p.obj("pack f f"); p.link(vex, 0, epk, 1); p.link(etf, 0, epk, 0)
    snin2 = p.obj("s note_in"); p.link(epk, 0, snin2, 0)

    # ---- voice allocation + ornament + tremolo (ember's) --------------------------
    p.comment("-- note_in (deg vel) -> +voice -> ornament (inflection | mordent) -> tremolo -> lead_on (deg vel voice startdeg glide) --")
    rni = p.obj("r note_in"); atl = p.obj("t l b"); p.link(rni, 0, atl, 0)
    vrf = p.obj("f"); vrinc = p.obj("+ 1"); vrmod = p.obj("mod 3"); vrp1 = p.obj("+ 1")
    p.link(atl, 1, vrf, 0); p.link(vrf, 0, vrinc, 0); p.link(vrinc, 0, vrmod, 0); p.link(vrmod, 0, vrf, 1)
    p.link(vrf, 0, vrp1, 0)
    apk = p.obj("pack f f f -99 0"); p.link(vrp1, 0, apk, 2)
    aun = p.obj("unpack f f"); p.link(atl, 0, aun, 0); p.link(aun, 1, apk, 1); p.link(aun, 0, apk, 0)
    otl = p.obj("t l l b"); p.link(apk, 0, otl, 0)
    ornd = p.obj("random 100"); olt = p.obj("<"); p.link(otl, 2, ornd, 0); p.link(ornd, 0, olt, 0)
    rorn = p.obj("r ornament"); o100 = p.obj("* 100"); p.link(rorn, 0, o100, 0); p.link(o100, 0, olt, 1)
    otf = p.obj("t f f"); p.link(olt, 0, otf, 0)
    ospA = p.obj("spigot"); ospB = p.obj("spigot"); p.link(otf, 1, ospA, 1)
    oeq = p.obj("== 0"); p.link(otf, 0, oeq, 0); p.link(oeq, 0, ospB, 1)
    p.link(otl, 1, ospA, 0); p.link(otl, 0, ospB, 0)
    snout = p.obj("s note_out"); p.link(ospB, 0, snout, 0)
    otl2 = p.obj("t l l b b"); p.link(ospA, 0, otl2, 0)
    dirr = p.obj("random 4"); dire = p.obj("== 0"); dirm = p.obj("* -2"); dirp = p.obj("+ 1")
    p.chain(dirr, dire, dirm, dirp); p.link(otl2, 3, dirr, 0)
    kind = p.obj("random 2"); ktf = p.obj("t f f"); p.link(otl2, 2, kind, 0); p.link(kind, 0, ktf, 0)
    spI = p.obj("spigot"); spM = p.obj("spigot"); p.link(ktf, 1, spM, 1)
    keq = p.obj("== 0"); p.link(ktf, 0, keq, 0); p.link(keq, 0, spI, 1)
    p.link(otl2, 1, spI, 0); p.link(otl2, 0, spM, 0)
    iun = p.obj("unpack f f f"); p.link(spI, 0, iun, 0)
    ipk = p.obj("pack f f f f 70"); p.link(iun, 2, ipk, 2); p.link(iun, 1, ipk, 1)
    itf = p.obj("t f f"); p.link(iun, 0, itf, 0)
    inb = p.obj("+"); p.link(dirp, 0, inb, 1); p.link(itf, 1, inb, 0); p.link(inb, 0, ipk, 3)
    p.link(itf, 0, ipk, 0); p.link(ipk, 0, snout, 0)
    mun_ = p.obj("unpack f f f"); p.link(spM, 0, mun_, 0)
    mpipe = raw(p, "pipe f f f 50", 4, 3); p.link(mun_, 2, mpipe, 2); p.link(mun_, 1, mpipe, 1); p.link(mun_, 0, mpipe, 0)
    mpk = p.obj("pack f f f -99 0"); p.link(mpipe, 2, mpk, 2); p.link(mpipe, 1, mpk, 1); p.link(mpipe, 0, mpk, 0)
    p.link(mpk, 0, snout, 0)
    gpk = p.obj("pack f f f -99 0"); p.link(mun_, 2, gpk, 2)
    gvel = p.obj("* 0.7"); p.link(mun_, 1, gvel, 0); p.link(gvel, 0, gpk, 1)
    gnb = p.obj("+"); p.link(dirp, 0, gnb, 1); p.link(mun_, 0, gnb, 0); p.link(gnb, 0, gpk, 0)
    p.link(gpk, 0, snout, 0)
    rno = p.obj("r note_out"); ttl = p.obj("t l l b"); p.link(rno, 0, ttl, 0)
    trnd = p.obj("random 100"); tlt = p.obj("<"); p.link(ttl, 2, trnd, 0); p.link(trnd, 0, tlt, 0)
    rtr = p.obj("r tremolo"); t100 = p.obj("* 100"); p.link(rtr, 0, t100, 0); p.link(t100, 0, tlt, 1)
    tsp = p.obj("spigot"); p.link(tlt, 0, tsp, 1); p.link(ttl, 1, tsp, 0)
    tun_ = p.obj("unpack f f f"); p.link(tsp, 0, tun_, 0)
    tpipe = raw(p, "pipe f f f 90", 4, 3); p.link(tun_, 2, tpipe, 2); p.link(tun_, 1, tpipe, 1); p.link(tun_, 0, tpipe, 0)
    rh2 = p.obj("r halfpulse"); p.link(rh2, 0, tpipe, 3)
    tpk_ = p.obj("pack f f f -99 0"); p.link(tpipe, 2, tpk_, 2)
    tvel_ = p.obj("* 0.7"); p.link(tpipe, 1, tvel_, 0); p.link(tvel_, 0, tpk_, 1); p.link(tpipe, 0, tpk_, 0)
    slon = p.obj("s lead_on"); p.link(tpk_, 0, slon, 0); p.link(ttl, 0, slon, 0)

    # ---- lead dispatch: degree -> scale pitch -> oud (3 x kstring~) / ney (ember's) ----
    p.comment("-- lead: (deg vel voice startdeg glide) -> scale_degree -> mtof -> oud / ney (VOICE = both: the ney takes the strong notes) --")
    rlo = p.obj("r lead_on"); lun = p.obj("unpack f f f f f"); p.link(rlo, 0, lun, 0)
    lpk = p.obj("pack f f f f f"); p.link(lun, 4, lpk, 3); p.link(lun, 2, lpk, 4)
    smo = p.obj("moses -98"); p.link(lun, 3, smo, 0)
    sz = p.msg("0"); p.link(smo, 0, sz, 0); p.link(sz, 0, lpk, 2)
    smq = scale_degree(p, (smo, 1)); smt = p.obj("mtof"); p.link(smq, 0, smt, 0); p.link(smt, 0, lpk, 2)
    lv = p.obj("/ 127"); lvc = p.obj("clip 0 1"); p.link(lun, 1, lv, 0); p.link(lv, 0, lvc, 0); p.link(lvc, 0, lpk, 1)
    ldt = p.obj("t f f"); p.link(lun, 0, ldt, 0)
    sldg = p.obj("s lastdeg"); p.link(ldt, 1, sldg, 0)
    lmq = scale_degree(p, ldt); lmt = p.obj("t f f"); p.link(lmq, 0, lmt, 0)
    slm = p.obj("s lastmidi"); p.link(lmt, 1, slm, 0)
    lmtof = p.obj("mtof"); p.link(lmt, 0, lmtof, 0); p.link(lmtof, 0, lpk, 0)
    lmsg = p.msg("$5 $1 $2 $3 $4"); p.link(lpk, 0, lmsg, 0)
    rv = p.obj("r voice"); vtb = p.obj("t b f"); p.link(rv, 0, vtb, 0)
    vo = p.obj("!= 1"); p.link(vtb, 1, vo, 0)
    nyf = p.obj("f"); rny = p.obj("r neyok"); p.link(rny, 0, nyf, 0); p.link(vtb, 0, nyf, 0)
    vn = p.obj("expr ($f2==1)||(($f2==2)&&($f1>0))"); p.link(nyf, 0, vn, 0); p.link(vtb, 1, vn, 1)
    spo = p.obj("spigot"); spn = p.obj("spigot"); p.link(vo, 0, spo, 1); p.link(vn, 0, spn, 1)
    p.link(lmsg, 0, spo, 0); p.link(lmsg, 0, spn, 0)
    oud = raw(p, "clone -s 1 kstring~ 3 3000 0.996 5000 1", 1, 1); p.link(spo, 0, oud, 0)
    obody = p.obj("bp~ 230 1.2"); obg = p.obj("*~ 0.35"); p.link(oud, 0, obody, 0); p.link(obody, 0, obg, 0)
    osum = p.obj("+~"); p.link(oud, 0, osum, 0); p.link(obg, 0, osum, 1)
    oout = p.obj("*~ 1.15"); p.link(osum, 0, oout, 0)
    p.comment("-- ney --")
    nun = p.obj("unpack f f f f f"); p.link(spn, 0, nun, 0)
    nvel = p.obj("* 0.9"); nvpk = p.obj("pack f 35"); nvln = p.obj("line~")
    p.link(nun, 2, nvel, 0); p.link(nvel, 0, nvpk, 0); p.link(nvpk, 0, nvln, 0)
    rsl2 = p.obj("r slide"); ngl = p.obj("expr 10 + $f1*140"); p.link(rsl2, 0, ngl, 0)
    ngl2 = p.obj("expr if($f1>0, $f1, $f2)"); p.link(nun, 4, ngl2, 0); p.link(ngl, 0, ngl2, 1)
    nfpk = p.obj("pack f f"); p.link(ngl2, 0, nfpk, 1)
    nfln = p.obj("line~")
    nst = p.obj("moses 1"); p.link(nun, 3, nst, 0)
    njmp = p.msg("$1 0"); p.link(nst, 1, njmp, 0); p.link(njmp, 0, nfln, 0)
    p.link(nun, 1, nfpk, 0); p.link(nfpk, 0, nfln, 0)
    vib = p.obj("osc~ 5.3"); vibd = p.obj("*~ 0.012"); vib1 = p.obj("+~ 1"); p.chain(vib, vibd, vib1)
    nf = p.obj("*~"); p.link(nfln, 0, nf, 0); p.link(vib1, 0, nf, 1)
    o1 = p.obj("osc~"); p.link(nf, 0, o1, 0)
    f2 = p.obj("*~ 2"); o2 = p.obj("osc~"); o2g = p.obj("*~ 0.4"); p.link(nf, 0, f2, 0); p.link(f2, 0, o2, 0); p.link(o2, 0, o2g, 0)
    f3 = p.obj("*~ 3"); o3 = p.obj("osc~"); o3g = p.obj("*~ 0.15"); p.link(nf, 0, f3, 0); p.link(f3, 0, o3, 0); p.link(o3, 0, o3g, 0)
    nnz = p.obj("noise~"); nvcf = p.obj("vcf~ 1000 7"); nbg = p.obj("*~ 0.35")
    p.link(nnz, 0, nvcf, 0); p.link(f2, 0, nvcf, 1); p.link(nvcf, 0, nbg, 0)
    ns1 = p.obj("+~"); p.link(o1, 0, ns1, 0); p.link(o2g, 0, ns1, 1)
    ns2 = p.obj("+~"); p.link(ns1, 0, ns2, 0); p.link(o3g, 0, ns2, 1)
    ns3 = p.obj("+~"); p.link(ns2, 0, ns3, 0); p.link(nbg, 0, ns3, 1)
    nvca = p.obj("*~"); p.link(ns3, 0, nvca, 0); p.link(nvln, 0, nvca, 1)
    nlp = p.obj("lop~ 3200"); p.link(nvca, 0, nlp, 0)
    nout = p.obj("*~ 0.32"); p.link(nlp, 0, nout, 0)
    rlof = p.obj("r lead_off"); leq = p.obj("expr $f1==$f2"); p.link(rlof, 0, leq, 0)
    rld = p.obj("r lastdeg"); p.link(rld, 0, leq, 1)
    lsel = p.obj("sel 1"); p.link(leq, 0, lsel, 0)
    nrel = p.msg("0 160"); p.link(lsel, 0, nrel, 0); p.link(nrel, 0, nvln, 0)
    rnr = p.obj("r ney_release"); p.link(rnr, 0, nrel, 0)
    lead = p.obj("+~"); p.link(oout, 0, lead, 0); p.link(nout, 0, lead, 1)

    # ---- drone (ember's breathing drone) ----
    p.comment("-- drone: tonic saw pair + fifth + sub; BREATH = slow walks + gusts (internal, 0.5) --")
    rtn = p.obj("r tonic"); dm12 = p.obj("- 12"); dmt = p.obj("mtof"); p.chain(rtn, dm12, dmt)
    dtf3 = p.obj("t f f f f"); p.link(dmt, 0, dtf3, 0)
    rbr = p.obj("r breath"); bstep = p.obj("* 0.12"); p.link(rbr, 0, bstep, 0)
    wclk = p.obj("metro 250"); won = loadmsg(p, "1"); p.link(won, 0, wclk, 0)
    wtb = p.obj("t b b b"); p.link(wclk, 0, wtb, 0)

    def walk(outlet, init):
        rnd = p.obj("random 200"); p.link(wtb, outlet, rnd, 0)
        cen = p.obj("- 100"); scl = p.obj("* 0.01"); p.chain(rnd, cen, scl)
        stp_ = p.obj("*"); p.link(scl, 0, stp_, 0); p.link(bstep, 0, stp_, 1)
        acc_ = p.obj(f"+ {init}"); p.link(stp_, 0, acc_, 0)
        clp = p.obj("clip 0 1"); p.link(acc_, 0, clp, 0)
        tff = p.obj("t f f"); p.link(clp, 0, tff, 0); p.link(tff, 1, acc_, 1)
        pk = p.obj("pack f 250"); ln = p.obj("line~"); p.link(tff, 0, pk, 0); p.link(pk, 0, ln, 0)
        return tff, ln

    wAc, wA = walk(2, 0.5); wBc, wB = walk(1, 0.5); wCc, wC = walk(0, 0.3)
    spr = p.obj("*~ 0.006"); p.link(wC, 0, spr, 0)
    spr1 = p.obj("+~ 0.001"); p.link(spr, 0, spr1, 0)
    upA = p.obj("+~ 1"); p.link(spr1, 0, upA, 0)
    dnB = p.obj("*~ -1"); p.link(spr1, 0, dnB, 0)
    dnB1 = p.obj("+~ 1"); p.link(dnB, 0, dnB1, 0)
    fA = p.obj("*~"); p.link(upA, 0, fA, 0); p.link(dtf3, 0, fA, 1)
    fB = p.obj("*~"); p.link(dnB1, 0, fB, 0); p.link(dtf3, 1, fB, 1)
    dF = p.obj("* 1.498"); dS = p.obj("* 0.5"); p.link(dtf3, 2, dF, 0); p.link(dtf3, 3, dS, 0)
    phA = p.obj("phasor~"); phB = p.obj("phasor~"); phF = p.obj("phasor~"); sub = p.obj("osc~")
    p.link(fA, 0, phA, 0); p.link(fB, 0, phB, 0); p.link(dF, 0, phF, 0); p.link(dS, 0, sub, 0)
    cA = p.obj("-~ 0.5"); cB = p.obj("-~ 0.5"); cF = p.obj("-~ 0.5")
    p.link(phA, 0, cA, 0); p.link(phB, 0, cB, 0); p.link(phF, 0, cF, 0)
    fgl = p.obj("vline~"); fginit = loadmsg(p, "0.3"); p.link(fginit, 0, fgl, 0)
    fg = p.obj("*~"); p.link(cF, 0, fg, 0); p.link(fgl, 0, fg, 1)
    sg = p.obj("*~ 0.2"); p.link(sub, 0, sg, 0)
    ds1 = p.obj("+~"); p.link(cA, 0, ds1, 0); p.link(cB, 0, ds1, 1)
    ds2 = p.obj("+~"); p.link(ds1, 0, ds2, 0); p.link(fg, 0, ds2, 1)
    ds3 = p.obj("+~"); p.link(ds2, 0, ds3, 0); p.link(sg, 0, ds3, 1)
    dlp2 = p.obj("lop~ 750"); p.link(ds3, 0, dlp2, 0)
    brie = p.obj("expr 400*pow(5.5, $f1)"); p.link(wBc, 0, brie, 0); p.link(brie, 0, dlp2, 1)
    dlp3 = p.obj("lop~ 1500"); p.link(dlp2, 0, dlp3, 0)
    dvib = p.obj("osc~ 0.17"); dvg = p.obj("*~ 0.1"); dv1 = p.obj("+~ 0.9"); p.chain(dvib, dvg, dv1)
    lvle = p.obj("*~ 0.65"); p.link(wA, 0, lvle, 0)
    lvl1 = p.obj("+~ 0.35"); p.link(lvle, 0, lvl1, 0)
    dam0 = p.obj("*~"); p.link(dlp3, 0, dam0, 0); p.link(dv1, 0, dam0, 1)
    dam = p.obj("*~"); p.link(dam0, 0, dam, 0); p.link(lvl1, 0, dam, 1)
    drout = p.obj("*~ 0.35"); p.link(dam, 0, drout, 0)
    gdel = p.obj("del 12000"); gon = loadmsg(p, "bang"); p.link(gon, 0, gdel, 0)
    gtb = p.obj("t b b b"); p.link(gdel, 0, gtb, 0)
    gr = p.obj("random 20000"); p.link(gtb, 2, gr, 0)
    gr8 = p.obj("+ 8000"); p.link(gr, 0, gr8, 0)
    gsc = p.obj("expr $f1*(1-0.7*$f2)"); p.link(gr8, 0, gsc, 0)
    rbr2 = p.obj("r breath"); p.link(rbr2, 0, gsc, 1)
    p.link(gsc, 0, gdel, 1); p.link(gtb, 1, gdel, 0)
    ggate = p.obj("spigot"); p.link(gtb, 0, ggate, 0)
    rbr3 = p.obj("r breath"); gcmp = p.obj("> 0.05"); p.link(rbr3, 0, gcmp, 0); p.link(gcmp, 0, ggate, 1)
    gsw = p.msg("0.85 1500, 0.3 4000 1500"); p.link(ggate, 0, gsw, 0); p.link(gsw, 0, fgl, 0)
    sgu = p.obj("s gust"); p.link(ggate, 0, sgu, 0)

    # ---- mix, DISTANCE math, echo, reverb, FILTER, STORM, STUTTER, DISTANCE stage, out, RECORD ----
    p.comment("-- mix: buses -> line~ ; KILL LOW ; DRONE ; echo ; rev3~ with DISTANCE pre-delay ; FILTER ladder ; STORM dub loop ; STUTTER ; DISTANCE ; out --")
    rds = p.obj("r distance"); dtf6 = p.obj("t f f f f f f"); p.link(rds, 0, dtf6, 0)
    dlpe = p.obj("expr 20000*pow(0.025, $f1)"); dlpp = p.obj("pack f 60"); dlpl = p.obj("line~")
    p.link(dtf6, 0, dlpe, 0); p.chain(dlpe, dlpp, dlpl)
    dgne = p.obj("expr pow(10, -18*$f1/20)"); dgnp = p.obj("pack f 60"); dgnl = p.obj("line~")
    p.link(dtf6, 1, dgne, 0); p.chain(dgne, dgnp, dgnl)
    dwde = p.obj("expr $f1*0.9"); dwdp = p.obj("pack f 60"); dwdl = p.obj("line~")
    p.link(dtf6, 2, dwde, 0); p.chain(dwde, dwdp, dwdl)
    drve = p.obj("expr 1+$f1*2.5"); drvp = p.obj("pack f 60"); drvl = p.obj("line~")
    p.link(dtf6, 3, drve, 0); p.chain(drve, drvp, drvl)
    dpde = p.obj("expr 5+$f1*110"); dpdp = p.obj("pack f 60"); dpdl = p.obj("line~")
    p.link(dtf6, 4, dpde, 0); p.chain(dpde, dpdp, dpdl)
    dsfe = p.obj("expr 12000*pow(0.1, $f1)"); dsfp = p.obj("pack f 60"); dsfl = p.obj("line")
    p.link(dtf6, 5, dsfe, 0); p.chain(dsfe, dsfp, dsfl)
    qL0 = lvl(p, qout, "qmix")
    qL = p.obj("lop~ 12000"); p.link(qL0, 0, qL, 0); p.link(dsfl, 0, qL, 1)
    drums = p.obj("+~"); p.link(dout, 0, drums, 0); p.link(tout, 0, drums, 1)
    drums2 = p.obj("+~"); p.link(drums, 0, drums2, 0); p.link(cout, 0, drums2, 1)
    dL0 = lvl(p, drums2, "dmix")
    bL0 = lvl(p, bout, "bmix")
    #   KILL LOW (held pad): fast mute on drums + bass
    rkl = p.obj("r killlow"); kex = p.obj("expr 1-$f1"); kpk = p.obj("pack f 40"); kln = p.obj("line~")
    p.chain(rkl, kex, kpk, kln)
    dL1 = p.obj("*~"); p.link(dL0, 0, dL1, 0); p.link(kln, 0, dL1, 1)
    dL = p.obj("lop~ 12000"); p.link(dL1, 0, dL, 0); p.link(dsfl, 0, dL, 1)
    bL = p.obj("*~"); p.link(bL0, 0, bL, 0); p.link(kln, 0, bL, 1)
    lL = lvl(p, lead, "lmix")
    drL0 = lvl(p, drout, "drmix")
    rdo = p.obj("r droneon"); dopk = p.obj("pack f 30"); doln = p.obj("line~"); p.chain(rdo, dopk, doln)
    drL = p.obj("*~"); p.link(drL0, 0, drL, 0); p.link(doln, 0, drL, 1)
    edw = p.obj("delwrite~ tendecho 3000")
    efb = p.obj("*~ 0.38")
    ein = p.obj("+~"); p.link(lL, 0, ein, 0); p.link(efb, 0, ein, 1); p.link(ein, 0, edw, 0)
    edr = p.obj("delread~ tendecho 280")
    rpm3 = p.obj("r pulsems"); e15 = p.obj("* 1.5"); p.link(rpm3, 0, e15, 0); p.link(e15, 0, edr, 0)
    p.link(edr, 0, efb, 0)
    ehp = p.obj("hip~ 300"); p.link(edr, 0, ehp, 0)
    eL = lvl(p, ehp, "echo")
    rs1 = p.obj("*~ 0.5"); p.link(lL, 0, rs1, 0)
    rs2 = p.obj("*~ 0.3"); p.link(drL, 0, rs2, 0)
    rs3 = p.obj("*~ 0.12"); p.link(dL, 0, rs3, 0)
    rs4 = p.obj("*~ 0.4"); p.link(eL, 0, rs4, 0)
    rsa = p.obj("+~"); p.link(rs1, 0, rsa, 0); p.link(rs2, 0, rsa, 1)
    rsb = p.obj("+~"); p.link(rsa, 0, rsb, 0); p.link(rs3, 0, rsb, 1)
    rsc = p.obj("+~"); p.link(rsb, 0, rsc, 0); p.link(rs4, 0, rsc, 1)
    rpw = p.obj("delwrite~ rvpre 300"); p.link(rsc, 0, rpw, 0)
    rpd = p.obj("vd~ rvpre"); p.link(dpdl, 0, rpd, 0)
    rev = p.obj("rev3~ 100 88 3000 20"); p.link(rpd, 0, rev, 0); p.link(rpd, 0, rev, 1)
    rvL0 = lvl(p, rev, "space")
    rvR_src = p.obj("*~ 1"); p.link(rev, 1, rvR_src, 0)
    rvR0 = lvl(p, rvR_src, "space")
    rvbr = p.obj("r storm"); rvbe = p.obj("expr 1+$f1*1.5"); rvbp = p.obj("pack f 60"); rvbl = p.obj("line~")
    p.chain(rvbr, rvbe, rvbp, rvbl)
    rvL1 = p.obj("*~"); p.link(rvL0, 0, rvL1, 0); p.link(rvbl, 0, rvL1, 1)
    rvR1 = p.obj("*~"); p.link(rvR0, 0, rvR1, 0); p.link(rvbl, 0, rvR1, 1)
    rvL = p.obj("*~"); p.link(rvL1, 0, rvL, 0); p.link(drvl, 0, rvL, 1)
    rvR = p.obj("*~"); p.link(rvR1, 0, rvR, 0); p.link(drvl, 0, rvR, 1)

    def pan(sig, gl_, gr_):
        l = p.obj(f"*~ {gl_}"); r_ = p.obj(f"*~ {gr_}")
        p.link(sig, 0, l, 0); p.link(sig, 0, r_, 0)
        return l, r_

    def sumall(parts):
        acc_ = parts[0]
        for x in parts[1:]:
            s = p.obj("+~"); p.link(acc_, 0, s, 0); p.link(x, 0, s, 1); acc_ = s
        return acc_

    qLl, qLr = pan(qL, 0.7, 1.0); dLl, dLr = pan(dL, 1.0, 1.0); bLl, bLr = pan(bL, 1.0, 1.0)
    lLl, lLr = pan(lL, 1.0, 0.85); drl, drr = pan(drL, 1.0, 1.0); eLl, eLr = pan(eL, 0.7, 1.0)
    mixL = sumall([qLl, dLl, bLl, lLl, drl, eLl, rvL])
    mixR = sumall([qLr, dLr, bLr, lLr, drr, eLr, rvR])
    #   FILTER: a ladder lowpass dive over the WHOLE dial (200 Hz at 0, open at 1), resonance rising into the
    #   dive, 0 when open (the ladder's passband droops with resonance, measured). Ember split the dial into a
    #   dive and a highpass build; the sweep contract showed the dive's whole action then sat in a tenth of
    #   the travel, and the thin end was the least musical edge -- one dial, one thing.
    p.comment("-- FILTER: ladder dive, dark (200 Hz, resonant) at 0 -> open at 1 --")
    rfx = p.obj("r filter"); xtf = p.obj("t f f"); p.link(rfx, 0, xtf, 0)
    lpe = p.obj("expr 200*pow(100, $f1)"); p.link(xtf, 0, lpe, 0)
    lppk = p.obj("pack f 40"); lpln = p.obj("line~"); p.chain(lpe, lppk, lpln)
    ree = p.obj("expr pow(1-$f1, 1.3)*2.2"); p.link(xtf, 1, ree, 0)
    repk = p.obj("pack f 40"); reln = p.obj("line~"); p.chain(ree, repk, reln)
    #   STORM: dub loop feedback / wet / send, plus a slight dry duck at the top (ember's FX Y)
    rfy = p.obj("r storm"); ytf = p.obj("t f f f f"); p.link(rfy, 0, ytf, 0)
    fbe = p.obj("expr min(0.95, $f1*1.05)"); fbp = p.obj("pack f 40"); fbl = p.obj("line~"); p.link(ytf, 0, fbe, 0); p.chain(fbe, fbp, fbl)
    wte = p.obj("expr pow($f1, 1.2)*0.85"); wtp = p.obj("pack f 40"); wtl = p.obj("line~"); p.link(ytf, 1, wte, 0); p.chain(wte, wtp, wtl)
    sne = p.obj("expr min(1, $f1*8)*0.75"); snp = p.obj("pack f 40"); snl = p.obj("line~"); p.link(ytf, 2, sne, 0); p.chain(sne, snp, snl)
    dke = p.obj("expr 1 - 0.25*max(0, $f1-0.6)/0.4"); dkp = p.obj("pack f 80"); dkl = p.obj("line~"); p.link(ytf, 3, dke, 0); p.chain(dke, dkp, dkl)
    #   STUTTER gate + loop length (one pulse), dub delay time (three pulses)
    rst = p.obj("r stutter"); stf = p.obj("t f f"); p.link(rst, 0, stf, 0)
    sie = p.obj("expr 1-$f1"); sip = p.obj("pack f 8"); sil = p.obj("line~"); p.link(stf, 1, sie, 0); p.chain(sie, sip, sil)
    sgp = p.obj("pack f 8"); sgl = p.obj("line~"); p.link(stf, 0, sgp, 0); p.link(sgp, 0, sgl, 0)
    rpm4 = p.obj("r pulsems"); stpk = p.obj("pack f 60"); stln = p.obj("line~"); p.chain(rpm4, stpk, stln)
    rpm5 = p.obj("r pulsems"); dt3 = p.obj("* 3"); dtp = p.obj("pack f 60"); dtl = p.obj("line~"); p.chain(rpm5, dt3, dtp, dtl)

    def fx_channel(mix):
        ret = p.obj("+~"); p.link(mix, 0, ret, 0)     # dub echoes re-enter here
        bob = p.obj("bob~"); p.link(ret, 0, bob, 0); p.link(lpln, 0, bob, 1); p.link(reln, 0, bob, 2)
        ov = loadmsg(p, "oversample 2"); p.link(ov, 0, bob, 0)
        h1 = p.obj("hip~ 15"); p.link(bob, 0, h1, 0)
        return ret, h1

    retL, fxL = fx_channel(mixL)
    retR, fxR = fx_channel(mixR)
    sdm = p.obj("+~"); p.link(fxL, 0, sdm, 0); p.link(fxR, 0, sdm, 1)
    sdg = p.obj("*~ 0.5"); p.link(sdm, 0, sdg, 0)
    ssn = p.obj("*~"); p.link(sdg, 0, ssn, 0); p.link(snl, 0, ssn, 1)
    din = p.obj("+~"); p.link(ssn, 0, din, 0)
    ddw = p.obj("delwrite~ tenddub 2600"); p.link(din, 0, ddw, 0)
    dvd = p.obj("vd~ tenddub"); p.link(dtl, 0, dvd, 0)
    dlp4 = p.obj("lop~ 3800"); p.link(dvd, 0, dlp4, 0)
    dhp = p.obj("hip~ 130"); p.link(dlp4, 0, dhp, 0)
    dfb = p.obj("*~"); p.link(dhp, 0, dfb, 0); p.link(fbl, 0, dfb, 1)
    dcl = p.obj("clip~ -0.9 0.9"); p.link(dfb, 0, dcl, 0); p.link(dcl, 0, din, 1)
    dwt = p.obj("*~"); p.link(dcl, 0, dwt, 0); p.link(wtl, 0, dwt, 1)
    p.link(dwt, 0, retL, 1); p.link(dwt, 0, retR, 1)

    def stut_channel(sig, name):
        sv = p.obj(f"vd~ {name}"); p.link(stln, 0, sv, 0)
        a_ = p.obj("*~"); p.link(sig, 0, a_, 0); p.link(sil, 0, a_, 1)
        b_ = p.obj("*~"); p.link(sv, 0, b_, 0); p.link(sgl, 0, b_, 1)
        s_ = p.obj("+~"); p.link(a_, 0, s_, 0); p.link(b_, 0, s_, 1)
        dw_ = p.obj(f"delwrite~ {name} 1500"); p.link(s_, 0, dw_, 0)
        return s_

    stL = stut_channel(fxL, "stutL"); stR = stut_channel(fxR, "stutR")
    p.comment("-- DISTANCE stage: ladder lowpass (no resonance, oversampled), level, image to mono; then duck, hip~, clip~, dac~ --")

    def far_channel(sig):
        lp = p.obj("bob~"); p.link(sig, 0, lp, 0); p.link(dlpl, 0, lp, 1)
        ov_ = loadmsg(p, "oversample 2"); p.link(ov_, 0, lp, 0)
        g = p.obj("*~"); p.link(lp, 0, g, 0); p.link(dgnl, 0, g, 1)
        return g

    farL = far_channel(stL); farR = far_channel(stR)
    midS = p.obj("+~"); p.link(farL, 0, midS, 0); p.link(farR, 0, midS, 1)
    midH = p.obj("*~ 0.5"); p.link(midS, 0, midH, 0)

    def narrow(side):
        d_ = p.obj("-~"); p.link(midH, 0, d_, 0); p.link(side, 0, d_, 1)
        w_ = p.obj("*~"); p.link(d_, 0, w_, 0); p.link(dwdl, 0, w_, 1)
        o_ = p.obj("+~"); p.link(side, 0, o_, 0); p.link(w_, 0, o_, 1)
        return o_

    nL = narrow(farL); nR = narrow(farR)
    mL = p.obj("*~ 0.3"); mR = p.obj("*~ 0.3"); p.link(nL, 0, mL, 0); p.link(nR, 0, mR, 0)
    dkL = p.obj("*~"); p.link(mL, 0, dkL, 0); p.link(dkl, 0, dkL, 1)
    dkR = p.obj("*~"); p.link(mR, 0, dkR, 0); p.link(dkl, 0, dkR, 1)
    hL = p.obj("hip~ 30"); hR = p.obj("hip~ 30"); p.link(dkL, 0, hL, 0); p.link(dkR, 0, hR, 0)
    cL = p.obj("clip~ -1 1"); cR = p.obj("clip~ -1 1"); p.link(hL, 0, cL, 0); p.link(hR, 0, cR, 0)
    dac = p.obj("dac~"); p.link(cL, 0, dac, 0); p.link(cR, 0, dac, 1)
    p.comment("-- RECORD: [r record] 1 -> open take_NNN.wav + start ; 0 -> stop (writesf~ 2, 24-bit) --")
    rrec2 = p.obj("r record"); rsel = p.obj("sel 1 0"); p.link(rrec2, 0, rsel, 0)
    tkf = p.obj("f"); tki = p.obj("+ 1"); p.link(rsel, 0, tkf, 0); p.link(tkf, 0, tki, 0); p.link(tki, 0, tkf, 1)
    mkf = raw(p, "makefilename take_%03d.wav", 1, 1); p.link(tki, 0, mkf, 0)
    opn = p.msg("open -bytes 3 $1, start"); p.link(mkf, 0, opn, 0)
    wsf = raw(p, "writesf~ 2", 2, 0); p.link(opn, 0, wsf, 0)
    stpm = p.msg("stop"); p.link(rsel, 1, stpm, 0); p.link(stpm, 0, wsf, 0)
    p.link(cL, 0, wsf, 0); p.link(cR, 0, wsf, 1)

    unval = p.unvalidated()
    print(f"unvalidated objects ({len(unval)}):", ", ".join(unval[:40]))
    return p.render()


def build_play() -> str:
    """tend_play.pd -- the mouse face: ELSE on-screen keys (the expert path,
    keys = degrees) and an X-Y pad on DENSITY / FILTER; opens tend.pd alongside.
    Kept out of the engine: ELSE GUI objects hang a headless real-time Pd."""
    q = Patch(760, 420, 10)
    q.comment("TEND -- mouse face (needs ELSE). Opens tend.pd next to it; everything talks over the engine's sends.", 20, 6)
    lb = q.obj("loadbang", 20, 30); dr = q.msg("dir", 20, 54); q.link(lb, 0, dr, 0)
    pc = q.obj("pdcontrol", 20, 78); q.link(dr, 0, pc, 0)
    lp = q.obj("list prepend tend.pd", 20, 102); q.link(pc, 0, lp, 0)
    op = q.msg("; pd open $1 $2", 20, 126); q.link(lp, 0, op, 0)
    q.comment("keys: each key = the next scale degree, C4 = tonic (lower = louder)", 20, 170)
    kb = q.obj("else/keyboard -width 18 -height 80 -oct 2 -lowc 4", 20, 190)
    smi = q.obj("s midi_in", 20, 290); q.link(kb, 0, smi, 0)
    q.comment("X-Y pad: X = DENSITY | Y = FILTER", 420, 170)
    pad = q.obj("else/pad 140 140", 420, 190)
    prt = q.obj("route list", 580, 194); pux = q.obj("unpack f f", 580, 218)
    q.link(pad, 0, prt, 0); q.link(prt, 0, pux, 0)
    xd = q.obj("/ 140", 580, 242); xc = q.obj("clip 0 1", 580, 266); xs = q.obj("s density_ui", 580, 290)
    q.link(pux, 0, xd, 0); q.link(xd, 0, xc, 0); q.link(xc, 0, xs, 0)
    yd = q.obj("expr (140-$f1)/140", 660, 242); yc = q.obj("clip 0 1", 660, 266); ys = q.obj("s filter_ui", 660, 290)
    q.link(pux, 1, yd, 0); q.link(yd, 0, yc, 0); q.link(yc, 0, ys, 0)
    return q.render()


def build_all():
    MANIFEST["controls"].clear(); MANIFEST["gestures"].clear()
    (HERE / "kstring~.pd").write_text(build_kstring(), encoding="utf-8")
    main = HERE / f"{NAME}.pd"
    main.write_text(build_main(), encoding="utf-8")
    (HERE / f"{NAME}_play.pd").write_text(build_play(), encoding="utf-8")
    (HERE / f"{NAME}.json").write_text(json.dumps(MANIFEST, indent=2), encoding="utf-8")
    return main


# =========================================================================
# verification
# =========================================================================

def _hear(path, dur=8.0, skip=0.6, notes=(), **sends):
    """Render with injected control values (at 0.05 s, after the loadbang
    inits); `skip` drops the startup window; `notes` = extra control events."""
    ctrls = []
    for name, val in sends.items():
        if isinstance(val, (list, tuple)):
            ctrls += control.send(name, *val, at=0.05)
        else:
            ctrls += control.send(name, val, at=0.05)
    ctrls += list(notes)
    res = render(str(path), RenderSpec(duration=dur, controls=tuple(ctrls), search_paths=(str(HERE),)))
    audio = res.audio
    if skip:
        cut = int(skip * audio.sr)
        audio = type(audio)(audio.samples[cut:], audio.sr)
    return analyze(audio), res


def cents(a, b):
    return 1200 * math.log2(a / b)


def _partial_cents(rep, f, tol=35):
    best = None
    for pf in rep.top_partials[:10]:
        if pf <= 0:
            continue
        c = cents(pf, f)
        if abs(c) < tol and (best is None or abs(c) < abs(best)):
            best = c
    return best


def _ioi(rep):
    t = np.asarray(rep.onset_times, dtype=float)
    if len(t) < 3:
        return None, None
    iv = np.diff(t)
    return float(np.mean(iv)), float(np.std(iv) / np.mean(iv))


def _mono(res):
    x = np.asarray(res.audio.samples, dtype=float)
    return x.mean(axis=1) if x.ndim > 1 else x


def _win_rep(res, t0, t1):
    a = res.audio
    return analyze(type(a)(a.samples[int(t0 * a.sr):int(t1 * a.sr)], a.sr))


def _fp_sim(r1, r2):
    a = np.asarray(r1.fingerprint, dtype=float); b = np.asarray(r2.fingerprint, dtype=float)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def _seq_sim(res, loop_s, t0=0.0, nseg=8, skip_first=1):
    seg = loop_s / nseg
    sims = []
    for i in range(skip_first, nseg):
        a = _win_rep(res, t0 + i * seg, t0 + (i + 1) * seg)
        b = _win_rep(res, t0 + loop_s + i * seg, t0 + loop_s + (i + 1) * seg)
        sims.append(_fp_sim(a, b))
    return float(np.mean(sims))


def _win_rms(res, t0, t1):
    x = _mono(res); sr = res.audio.sr
    seg = x[int(t0 * sr):int(t1 * sr)]
    if not len(seg):
        return -240.0
    return 20 * math.log10(float(np.sqrt(np.mean(seg ** 2))) + 1e-12)


def _console(res, tag):
    return [l for l in res.pd_console.splitlines() if l.startswith(tag + ":")]


def _write_wav(path, audio):
    import wave
    x = np.asarray(audio.samples, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1]); w.setsampwidth(2); w.setframerate(audio.sr)
        w.writeframes(pcm.tobytes())
    return path


TEMPO = 168                                   # timing checks pin the clock's tempo directly (no glide)
PERC_ONLY = dict(lmix=0, bmix=0, drmix=0, autoplay=0, space=0, echo=0, tempo_now=TEMPO)
LEAD_ONLY = dict(qmix=0, dmix=0, bmix=0, drmix=0, autoplay=0, space=0, echo=0, ornament=0, tremolo=0, tempo_now=TEMPO)
DRONE_ONLY = dict(qmix=0, dmix=0, bmix=0, lmix=0, autoplay=0, space=0, echo=0)
D4 = 293.66
EDGE_WINDOW = (-50.0, -8.0)                   # every edge of every dial (others at default) must sit here, dBFS
                                              # (-47 is DISTANCE 1: the band over the dune, a whisper by design)


def _sweep_events(dial, lo, hi, t_up=(3.0, 9.0), t_down=(11.0, 17.0), n=30):
    """The dial sits at `lo` from the start (no jump from its default inside the
    measured window), rises to `hi` over six seconds, holds, comes back."""
    ev = control.send(dial, lo, at=0.05)
    for i in range(n + 1):
        ev += control.send(dial, lo + (hi - lo) * i / n, at=t_up[0] + (t_up[1] - t_up[0]) * i / n)
    for i in range(n + 1):
        ev += control.send(dial, hi - (hi - lo) * i / n, at=t_down[0] + (t_down[1] - t_down[0]) * i / n)
    return ev


def verify(path) -> bool:
    checks, reps = [], []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:50s} {detail}")

    def hear(tag, **kw):
        rep, res = _hear(path, **kw)
        reps.append((tag, rep, res))
        return rep

    pulse = 30.0 / TEMPO
    LOOP = STEPS * pulse
    lowfrac = lambda r: r.bands.get("sub", 0) + r.bands.get("bass", 0)

    print("\n-- whole rig --")
    r = hear("default", dur=8.0)
    bad = [l for l in reps[-1][2].pd_console.splitlines() if "error" in l.lower() or "couldn't" in l.lower()]
    check("loads clean (no Pd errors)", not bad, "; ".join(bad[:3]))
    check("default: sounds, many onsets", (not r.is_silent) and r.onset_count >= 10,
          f"onsets {r.onset_count} peak {r.peak_dbfs:.1f} dBFS rms {r.rms_dbfs:.1f} | {r.summary()}")
    full = hear("everything up", dur=8.0, tempo=190, density=1.0, mutate=1.0, storm=1.0, intensity=3)
    check("everything up: not clipped", not full.is_clipped, f"peak {full.peak_dbfs:.1f} dBFS")
    z = hear("all off", dur=4.0, skip=1.0, qmix=0, dmix=0, bmix=0, lmix=0, drmix=0, echo=0, space=0, autoplay=0)
    check("all buses 0: silent", z.is_silent, f"peak {z.peak_dbfs:.1f}")

    print("-- the engine: clock, patterns, swing, tiers (percussion only, tempo pinned) --")
    dA = hear("core doum", dur=7.0, skip=0.8, qmix=0, pattern=0, intensity=1, swing=0, **PERC_ONLY)
    dD = hear("skeleton doum", dur=11.0, skip=0.8, qmix=0, pattern=3, intensity=1, swing=0, **PERC_ONLY)
    for name, rep, exp in (("CORE: doum every 6 pulses (half-bar)", dA, 6 * pulse),
                           ("SKELETON: doum once a bar (12 pulses)", dD, 12 * pulse)):
        m, _ = _ioi(rep)
        check(name, m is not None and abs(m - exp) / exp < 0.12, f"mean IOI {m and round(m, 3)} s, expected {exp:.3f} s")
    t120 = hear("tempo 120", dur=7.0, skip=0.8, qmix=0, pattern=0, intensity=1, swing=0, **{**PERC_ONLY, "tempo_now": 120})
    t200 = hear("tempo 200", dur=7.0, skip=0.8, qmix=0, pattern=0, intensity=1, swing=0, **{**PERC_ONLY, "tempo_now": 200})
    m1, _ = _ioi(t120); m2, _ = _ioi(t200)
    check("tempo_now 120 -> 200 shortens the bar", m1 and m2 and 1.45 < m1 / m2 < 1.9, f"IOI {m1 and round(m1, 3)} -> {m2 and round(m2, 3)} s")
    s0 = hear("swing 0", dur=6.0, skip=0.8, dmix=0, pattern=0, intensity=1, swing=0, **PERC_ONLY)
    s4 = hear("swing 0.4", dur=6.0, skip=0.8, dmix=0, pattern=0, intensity=1, swing=0.4, **PERC_ONLY)
    _, cv0 = _ioi(s0); _, cv4 = _ioi(s4)
    check("swing 0 -> 0.4 makes the pulses uneven", cv0 is not None and cv4 is not None and cv0 < 0.1 and cv4 > cv0 + 0.12,
          f"IOI spread {cv0 and round(cv0, 3)} -> {cv4 and round(cv4, 3)}")
    i1 = hear("intensity 1", dur=6.0, skip=0.8, pattern=0, intensity=1, **PERC_ONLY)
    i3 = hear("intensity 3", dur=6.0, skip=0.8, pattern=0, intensity=3, **PERC_ONLY)
    check("intensity sparse -> full adds energy", i3.rms_dbfs > i1.rms_dbfs + 1.5, f"rms {i1.rms_dbfs:.1f} -> {i3.rms_dbfs:.1f} dBFS")

    print("-- the voices, one at a time --")
    q = hear("qraqeb", dur=5.0, skip=0.8, dmix=0, **PERC_ONLY)
    check("qraqeb: bright metallic clatter", q.centroid_hz > 2500 and q.onset_count >= 12, f"centroid {q.centroid_hz:.0f} Hz, onsets {q.onset_count}")
    dr = hear("drums", dur=5.0, skip=0.8, qmix=0, **PERC_ONLY)
    check("drums: doum-led, low-heavy", dr.centroid_hz < 1500 and (dr.dominant_hz or 999) < 250, f"centroid {dr.centroid_hz:.0f} Hz")
    b = hear("bass", dur=5.0, skip=0.8, qmix=0, dmix=0, lmix=0, drmix=0, autoplay=0, space=0, echo=0, tempo_now=TEMPO)
    bc = b.pitch_hz and cents(b.pitch_hz, D4 / 4)
    check("guembri: rooted two octaves down (D2)", bc is not None and abs(bc) < 60,
          f"root {b.pitch_hz and round(b.pitch_hz, 1)} Hz by {b.pitch_source} ({bc and round(bc)} c) | {b.summary()}")
    dn = hear("drone", dur=4.0, skip=0.8, **DRONE_ONLY)
    dc = dn.dominant_hz and cents(dn.dominant_hz, D4 / 2)
    check("drone: steady D3", dc is not None and abs(dc) < 50 and dn.sustain_ratio > 0.7,
          f"dominant {dn.dominant_hz and round(dn.dominant_hz, 1)} Hz, sustain {dn.sustain_ratio:.2f}")
    hear("drone breath 0", dur=32.0, skip=0, breath=0.0, **DRONE_ONLY); rb0 = reps[-1][2]
    hear("drone breath 1", dur=32.0, skip=0, breath=1.0, **DRONE_ONLY); rb1 = reps[-1][2]
    lv0 = [_win_rms(rb0, t, t + 1.0) for t in range(2, 31)]; lv1 = [_win_rms(rb1, t, t + 1.0) for t in range(2, 31)]
    range0, range1 = max(lv0) - min(lv0), max(lv1) - min(lv1)
    pb = _win_rep(rb1, 12.0, 16.0); pbc = pb.dominant_hz and cents(pb.dominant_hz, D4 / 2)
    check("BREATH (internal): the drone drifts at 1, holds still at 0, stays on D3",
          range1 > range0 + 2.5 and range0 < 3.5 and pbc is not None and abs(pbc) < 60,
          f"1-s level range over 30 s: {range0:.1f} dB still vs {range1:.1f} dB breathing; pitch {pbc and round(pbc)} c")

    print("-- the scale (Bayati, one note at a time), the ney, the keys --")

    def note_partial(label, deg, expect_cents, **extra):
        rep = hear(label, dur=3.0, skip=0.5, notes=control.send("playdeg", deg, 100, at=0.6), lmix=1.0, voice=0, **LEAD_ONLY, **extra)
        f = D4 * 2 ** (expect_cents / 1200)
        c = _partial_cents(rep, f)
        check(label, c is not None and abs(c) < 30, f"expected {f:.1f} Hz (+{expect_cents}c): nearest partial {c and round(c, 1)} c away")

    note_partial("deg 0 = the tonic D4", 0, 0)
    note_partial("deg 1 = E half-flat (+150c): the quarter tone", 1, 150)
    note_partial("  ... HALF-FLAT 0 (internal) -> Eb (+100c)", 1, 100, neut=0.0)
    note_partial("  ... HALF-FLAT 1 (internal) -> E (+200c)", 1, 200, neut=1.0)
    note_partial("deg 3 = G (+500c)", 3, 500)
    note_partial("deg 7 = the octave", 7, 1200)
    ny = hear("ney deg 1", dur=3.0, skip=0.5, notes=control.send("playdeg", 1, 100, at=0.6), lmix=1.0, voice=1, **LEAD_ONLY)
    nc = ny.dominant_hz and cents(ny.dominant_hz, D4 * 2 ** (150 / 1200))
    check("ney: sustained E half-flat", nc is not None and abs(nc) < 30 and ny.sustain_ratio > 0.6,
          f"dominant {ny.dominant_hz and round(ny.dominant_hz, 1)} Hz ({nc and round(nc)} c), sustain {ny.sustain_ratio:.2f}")
    mi = hear("MIDI note 61", dur=3.0, skip=0.5, notes=control.note(61, at=0.6, dur=1.0), lmix=1.0, voice=0, **LEAD_ONLY)
    mc = _partial_cents(mi, D4 * 2 ** (150 / 1200))
    check("MIDI keys (the expert path): note 61 -> degree 1", mc is not None and abs(mc) < 30, f"nearest partial {mc and round(mc, 1)} c")

    print("-- the loop (lead only, embellishments off, tempo pinned) --")
    LEADBED = dict(lmix=1.0, autoplay=1, ornament=0, tremolo=0, qmix=0, dmix=0, bmix=0, drmix=0, space=0, echo=0, tempo_now=TEMPO)
    hear("locked loop", dur=2 * LOOP + 0.4, skip=0, mutate=0, density=1, phrase=1, **LEADBED); rl = reps[-1][2]
    sim_locked = _seq_sim(rl, LOOP)
    hear("mutating loop", dur=2 * LOOP + 0.4, skip=0, mutate=1.0, density=1, phrase=1, **LEADBED)
    sim_rand = _seq_sim(reps[-1][2], LOOP)
    check("MUTATE 0: the 2-bar loop repeats beat for beat", sim_locked > 0.9, f"beat-wise similarity {sim_locked:.3f}")
    check("MUTATE 1: the loop evolves", sim_rand < sim_locked - 0.05, f"{sim_rand:.3f} vs locked {sim_locked:.3f}")
    beat = 3 * pulse
    riff_open = _win_rep(rl, LOOP, LOOP + beat)
    hear("phrase 0 (call)", dur=LOOP + beat + 0.3, skip=0, mutate=0, density=1, phrase=0, **LEADBED)
    call_open = _win_rep(reps[-1][2], LOOP, LOOP + beat)

    def loudest_is(rep, f, kmax=4, tol=40):
        top = rep.top_partials[0] if rep.top_partials else 0
        return top > 0 and any(abs(cents(top, k * f)) < tol for k in range(1, kmax + 1))

    check("phrase bank: 'riff' opens on the tonic, 'call' on the 5th",
          loudest_is(riff_open, D4) and loudest_is(call_open, D4 * 1.5) and not loudest_is(call_open, D4, kmax=1),
          f"loudest: riff {riff_open.top_partials[:1]} Hz, call {call_open.top_partials[:1]} Hz")
    d0 = hear("density 0", dur=2 * LOOP + 0.4, skip=1.5, mutate=0, density=0.0, phrase=1, **LEADBED)   # skip the load-time note's tail
    dlo = hear("density 0.2", dur=2 * LOOP + 0.4, skip=0.45, mutate=0, density=0.2, phrase=1, **LEADBED)
    dhi = hear("density 1", dur=2 * LOOP + 0.4, skip=0.45, mutate=0, density=1.0, phrase=1, **LEADBED)
    check("DENSITY 0: no melody at all; 0.2 -> 1 adds notes to the loop, strong beats first",
          d0.is_silent and dhi.onset_count > dlo.onset_count * 1.5 and dlo.onset_count >= 3,
          f"onsets {d0.onset_count} / {dlo.onset_count} / {dhi.onset_count}")
    vboth = hear("voice both", dur=6.0, skip=0.8, voice=2, mutate=0, density=1, phrase=1, **LEADBED)
    voud = hear("voice oud", dur=6.0, skip=0.8, voice=0, mutate=0, density=1, phrase=1, **LEADBED)
    check("VOICE both (the default): the oud still cuts through the ney", vboth.onset_count >= voud.onset_count * 0.7,
          f"onsets both {vboth.onset_count} vs oud alone {voud.onset_count}")
    from pdverify.music import pitch_sequence
    hear("mutate 1 for 26 s", dur=26.0, skip=0, mutate=1.0, density=0.8, phrase=1, **LEADBED); rlong = reps[-1][2]
    ev = [e for e in pitch_sequence(rlong.audio) if e.time > 16.0]
    midis = [round(e.midi) for e in ev]
    med = float(np.median([e.midi for e in ev])) if ev else 0.0
    check("MUTATE 1 for 26 s: the tune keeps moving and stays in range",
          len(ev) >= 8 and len(set(midis)) >= 4 and 57 <= med <= 75,
          f"last 10 s: {len(ev)} notes, {len(set(midis))} distinct pitches, median MIDI {med:.1f} (tonic 62)")

    print("-- the dials --")
    QBED = dict(dmix=0, bmix=0, lmix=0, drmix=0, autoplay=0, space=0, echo=0)
    FXBED = dict(lmix=0, drmix=0, autoplay=0, space=0, echo=0)                    # perc + bass, broadband
    # (intensity 1: no qraqeb doubles, so the onset interval is the pulse; the dial glides 150 -> 120 in the first 2 s)
    hear("tempo glide", dur=9.0, skip=0, notes=control.send("tempo", 190, at=3.0), tempo=120, intensity=1, **QBED); tg = reps[-1][2]
    ioi_before = _ioi(_win_rep(tg, 2.2, 3.0))[0]; ioi_mid = _ioi(_win_rep(tg, 3.6, 4.4))[0]; ioi_after = _ioi(_win_rep(tg, 6.0, 9.0))[0]
    check("TEMPO: a jump on the dial arrives over ~2 s (120 -> 190: the pulse 250 -> 158 ms, passing through)",
          ioi_before is not None and abs(ioi_before - 0.25) < 0.02 and ioi_after is not None and abs(ioi_after - 30 / 190) < 0.015
          and ioi_mid is not None and ioi_after + 0.01 < ioi_mid < ioi_before - 0.01,
          f"pulse {ioi_before and round(ioi_before, 3)} -> mid-glide {ioi_mid and round(ioi_mid, 3)} -> {ioi_after and round(ioi_after, 3)} s")
    qn = hear("qraqeb bed", dur=5.0, skip=0.8, tempo_now=TEMPO, **QBED)
    fxn = hear("fx neutral", dur=5.0, skip=0.8, tempo_now=TEMPO, **FXBED)
    fxl = hear("filter 0", dur=5.0, skip=0.8, filter=0.0, tempo_now=TEMPO, **QBED)
    fxm = hear("filter 0.5", dur=5.0, skip=0.8, filter=0.5, tempo_now=TEMPO, **QBED)
    check("FILTER: the dive darkens everything at 0, half-way is half-way, 1 is open",
          fxl.centroid_hz < qn.centroid_hz * 0.15 and fxl.centroid_hz < fxm.centroid_hz < qn.centroid_hz * 0.9,
          f"centroid open {qn.centroid_hz:.0f} -> half {fxm.centroid_hz:.0f} -> dark {fxl.centroid_hz:.0f} Hz")
    mute_at = control.send("qmix", 0, at=3.5) + control.send("dmix", 0, at=3.5) + control.send("bmix", 0, at=3.5)
    hear("storm 0 tail", dur=8.0, skip=1.0, storm=0.0, notes=mute_at, tempo_now=TEMPO, **FXBED); tail_dry = _win_rms(reps[-1][2], 5.5, 7.5)
    hear("storm 0.9 tail", dur=8.0, skip=1.0, storm=0.9, notes=mute_at, tempo_now=TEMPO, **FXBED); tail_wet = _win_rms(reps[-1][2], 5.5, 7.5)
    check("STORM: the dub storm rings on after the band stops", tail_wet > tail_dry + 12, f"tail rms {tail_dry:.1f} -> {tail_wet:.1f} dBFS")
    far = hear("distance 1", dur=5.0, skip=0.8, distance=1.0, tempo_now=TEMPO, **QBED)
    check("DISTANCE 1: the band recedes (>= 15 dB down, dark)", far.rms_dbfs < qn.rms_dbfs - 15 and far.centroid_hz < 1000,
          f"rms {qn.rms_dbfs:.1f} -> {far.rms_dbfs:.1f} dBFS, centroid {qn.centroid_hz:.0f} -> {far.centroid_hz:.0f} Hz")
    mid_ = hear("distance 0.5", dur=5.0, skip=0.8, distance=0.5, tempo_now=TEMPO, **QBED)
    check("DISTANCE 0.5: half-way is in between (a sweep, not a switch)",
          far.rms_dbfs + 3 < mid_.rms_dbfs < qn.rms_dbfs - 3 and far.centroid_hz < mid_.centroid_hz < qn.centroid_hz,
          f"rms {mid_.rms_dbfs:.1f} dBFS, centroid {mid_.centroid_hz:.0f} Hz")

    print("-- the pads --")
    stt = (control.send("stutter", 1, at=3.5) + control.send("qmix", 0, at=3.55) + control.send("dmix", 0, at=3.55) + control.send("bmix", 0, at=3.55))
    hear("stutter hold", dur=8.0, skip=1.0, notes=stt, tempo_now=TEMPO, **FXBED); tail_st = _win_rms(reps[-1][2], 5.5, 7.5)
    check("STUTTER (hold): a one-pulse loop holds after the band stops", tail_st > tail_dry + 12, f"loop rms {tail_st:.1f} vs dead tail {tail_dry:.1f} dBFS")
    kl = hear("kill low", dur=5.0, skip=0.8, killlow=1, tempo_now=TEMPO, **FXBED)
    check("KILL LOW (hold): drums + bass drop out", lowfrac(kl) < 0.12, f"sub+bass {lowfrac(fxn):.2f} -> {lowfrac(kl):.2f}")
    pm = hear("pad pattern+", dur=11.0, skip=0.8, qmix=0, pattern=0, intensity=1, swing=0, notes=control.bang("nextpattern", at=0.5), **PERC_ONLY)
    m_, _ = _ioi(pm); gl = _console(reps[-1][2], "groove")
    check("PATTERN+: core -> hemiola (doum once a bar), landing on the bar", m_ is not None and abs(m_ - 12 * pulse) / (12 * pulse) < 0.12
          and gl and gl[0].split(":")[1].split() == ["1"], f"IOI {m_ and round(m_, 3)} s; console {gl[:1]}")
    ti = hear("pad intensity+", dur=9.0, skip=1.0, pattern=0, notes=control.bang("nextintensity", at=0.5), **PERC_ONLY)
    tl = _console(reps[-1][2], "tier")
    check("INTENSITY+: groove -> full (more energy than sparse), landing on the bar", ti.rms_dbfs > i1.rms_dbfs + 1.5
          and tl and tl[0].split(":")[1].split() == ["3"], f"rms {ti.rms_dbfs:.1f} vs sparse {i1.rms_dbfs:.1f} dBFS; console {tl[:1]}")
    hear("pad phrase+", dur=2 * LOOP + 3.0, skip=0, mutate=0, density=1, phrase=0, notes=control.bang("nextphrase", at=0.5), **LEADBED)
    pg = _console(reps[-1][2], "page")
    check("PHRASE+: re-seeds the tune (phrase 0 -> 1) at the loop's end, not mid-phrase", len(pg) == 1 and pg[0].split(":")[1].split() == ["1"], f"console {pg[:1]}")
    dt = hear("pad drone off", dur=5.0, skip=1.0, notes=control.bang("flip_droneon", at=0.5), **DRONE_ONLY)
    check("DRONE (flip): the drone goes out", dt.is_silent or dt.rms_dbfs < dn.rms_dbfs - 30, f"rms {dt.rms_dbfs:.1f} vs {dn.rms_dbfs:.1f} dBFS")

    print("-- MIDI CC, OSC twins, scenes, the manifest --")
    cslow = hear("cc74 0", dur=8.0, skip=2.5, notes=control.send("fakecc", 74, 0, at=0.06), intensity=1, **QBED)
    cfast = hear("cc74 127", dur=8.0, skip=2.5, notes=control.send("fakecc", 74, 127, at=0.06), intensity=1, **QBED)
    cs, _ = _ioi(cslow); cf, _ = _ioi(cfast)
    check("MiniLab knob 1 (CC 74) is TEMPO: 0 -> 127 = 110 -> 190 BPM", cs is not None and cf is not None and 1.5 < cs / cf < 1.95,
          f"pulse {cs and round(cs, 3)} -> {cf and round(cf, 3)} s via the CC router (expect ratio 1.73)")
    fo = hear("fakeosc distance", dur=5.0, skip=0.8, notes=control.send("fakeosc", "distance", 1.0, at=0.06), tempo_now=TEMPO, **QBED)
    check("OSC in: /distance 1 reaches the stage (fakeosc twin)", fo.rms_dbfs < qn.rms_dbfs - 15, f"rms {fo.rms_dbfs:.1f} dBFS")
    ctr = [c for k, v in QBED.items() for c in control.send(k, v, at=0.05)] + control.send("tempo_now", TEMPO, at=0.05)
    ctr += (control.send("distance", 1.0, at=0.05) + control.send("snapshot", 2, at=1.0)
            + control.send("distance", 0.0, at=1.5) + control.send("recall", 2, at=2.6))
    rs = render(str(path), RenderSpec(duration=5.5, controls=tuple(ctr), search_paths=(str(HERE),), keep_workdir=True))
    reps.append(("snapshot/recall", analyze(rs.audio), rs))
    snapf = rs.wav_path.parent / "snapshot_2.txt"
    snap = snapf.read_text(encoding="utf-8") if snapf.exists() else ""
    near = _win_rep(rs, 1.7, 2.5).centroid_hz; restored = _win_rep(rs, 3.2, 5.2).centroid_hz
    check("SNAPSHOT 2 writes the six dials + DRONE; RECALL 2 restores them", "distance_ui 1;" in snap and snap.count(";") == 7 and restored < near * 0.3,
          f"snapshot_2.txt {snap.count(';')} lines; centroid near {near:.0f} -> recalled {restored:.0f} Hz")
    man = json.loads((HERE / f"{NAME}.json").read_text(encoding="utf-8"))
    names = [c["name"] for c in man["controls"]]
    check("manifest: exactly the surface (6 dials, 4 pad controls, 5 gestures, 8 pads, 6 CCs)",
          names == list(DIALS) + ["stutter", "killlow", "droneon", "record"]
          and [g["name"] for g in man["gestures"]] == ["nextpattern", "nextintensity", "nextphrase", "snapshot", "recall"]
          and len(man["pads"]) == 8 and len(man["cc"]) == 6 and man["osc"]["in_port"] == OSC_IN_PORT, f"{names}")

    print("-- the four contracts --")
    edges = []
    for n, (lo, hi, _) in DIALS.items():
        for v in (lo, hi):
            rep = hear(f"edge {n} {v}", dur=7.0, skip=1.0, **{n: v})
            # level window only: the onset count is not "alive" -- a full dub storm smears every transient and is music
            ok = (not rep.is_clipped) and EDGE_WINDOW[0] < rep.rms_dbfs < EDGE_WINDOW[1]
            edges.append((ok, n, v, rep.rms_dbfs, rep.onset_count))
    bad_e = [e for e in edges if not e[0]]
    check("every edge is music: each dial at either end (others at default) sits inside the level window",
          not bad_e, f"rms {min(e[3] for e in edges):.1f} .. {max(e[3] for e in edges):.1f} dBFS; "
                     + ("; ".join(f"{e[1]}={e[2]}: rms {e[3]:.1f} onsets {e[4]}" for e in bad_e[:4]) or "all inside"))
    corners = [{k: (DIALS[k][0] if bit == 0 else DIALS[k][1]) for k, bit in zip(DIALS, bits)} for bits in itertools.product((0, 1), repeat=len(DIALS))]
    corners.append({k: DIALS[k][2] for k in DIALS})
    worst = []
    for c in corners:
        rep = hear("corner " + "".join("1" if c[k] == DIALS[k][1] else "0" if c[k] == DIALS[k][0] else "m" for k in DIALS), dur=6.0, skip=1.0, **c)
        res = reps[-1][2]
        head, tail = _win_rms(res, 1.0, 3.0), _win_rms(res, 4.0, 6.0)
        # safe = unclipped and not running away; silence is allowed here (FILTER thin + DISTANCE far
        # stack to nothing, and both dials said "take it away") -- musicality is the edge contract's job
        ok = (not rep.is_clipped) and tail < head + 8
        worst.append((ok, c, rep.rms_dbfs, rep.peak_dbfs, tail - head))
    fails = [w for w in worst if not w[0]]
    check(f"every corner is safe: all {len(corners)} corners of the six dials are unclipped and not running away",
          not fails, f"rms {min(w[2] for w in worst):.1f} .. {max(w[2] for w in worst):.1f} dBFS, peak max {max(w[3] for w in worst):.1f}; "
                     + ("; ".join(f"{w[1]}: peak {w[3]:.1f} tail {w[4]:+.1f}" for w in fails[:3]) or "all safe"))
    sweeps = []
    # one bed per dial, chosen so its one measurand can move: the qraqeb alone for the pulse (intensity 1:
    # no doubles), the lead alone for melody onsets, perc + bass for the filter, the mix for the rest
    SWEEP_BED = {"tempo": dict(dmix=0, bmix=0, lmix=0, drmix=0, autoplay=0, space=0, echo=0, intensity=1),
                 "density": dict(lmix=1.0, autoplay=1, ornament=0, tremolo=0, qmix=0, dmix=0, bmix=0, drmix=0, space=0, echo=0, mutate=0, phrase=1),
                 "mutate": {}, "filter": dict(dmix=0, bmix=0, lmix=0, drmix=0, autoplay=0, space=0, echo=0),
                 "storm": dict(drmix=0), "distance": {}}
    for n, (lo, hi, _) in DIALS.items():
        hear(f"sweep {n}", dur=18.0, skip=0, notes=_sweep_events(n, lo, hi), **SWEEP_BED[n]); res = reps[-1][2]
        lv_ = [_win_rms(res, t, t + 1.0) for t in range(2, 17)]
        pairs = [(a, b) for a, b in zip(lv_, lv_[1:]) if a > -60 and b > -60]      # silence -> sound is not a step
        jumps = max(abs(a - b) for a, b in pairs) if pairs else 0.0
        start, top = _win_rep(res, 1.0, 2.8), _win_rep(res, 8.6, 10.8)
        if n == "tempo":
            a, b_ = _ioi(start)[0], _ioi(top)[0]; moved = a is not None and b_ is not None and b_ < 0.75 * a; what = f"pulse {a and round(a, 3)} -> {b_ and round(b_, 3)} s"
        elif n == "density":
            moved = top.onset_count >= start.onset_count + 3; what = f"melody onsets {start.onset_count} -> {top.onset_count}"
        elif n == "filter":
            moved = start.centroid_hz < top.centroid_hz * 0.3; what = f"centroid dark {start.centroid_hz:.0f} -> open {top.centroid_hz:.0f} Hz"
        elif n == "storm":
            moved = top.rms_dbfs > start.rms_dbfs + 1.0; what = f"rms {start.rms_dbfs:.1f} -> {top.rms_dbfs:.1f} dBFS"
        elif n == "distance":
            moved = top.rms_dbfs < start.rms_dbfs - 10; what = f"rms {start.rms_dbfs:.1f} -> {top.rms_dbfs:.1f} dBFS"
        else:
            moved = True; what = "continuity only"
        sweeps.append((jumps < 10.0 and moved, n, jumps, what))
    bad_s = [s for s in sweeps if not s[0]]
    check("every dial scanned end to end is continuous (no 1-s level step > 10 dB) and moves its one measurand",
          not bad_s, "; ".join(f"{s[1]}: max step {s[2]:.1f} dB, {s[3]}" for s in sweeps))
    hear("unattended 10 min", dur=600.0, skip=0); ua = reps[-1][2]; rep_ua = reps[-1][1]
    lvls = [_win_rms(ua, t, t + 10.0) for t in range(5, 595, 10)]
    loop_s = STEPS * 30.0 / DIALS["tempo"][2]
    self_sims = [_seq_sim(ua, loop_s, t0=t) for t in (20.0, 300.0, 580.0)]
    mels = [l.split(":", 1)[1].split() for l in _console(ua, "melody")]
    mels = [m for m in mels if any(v != "0" for v in m)]          # the first print can precede the seed (all zeros)
    changed = sum(a != b for a, b in zip(mels[0], mels[-1])) if len(mels) >= 2 else -1
    check("unattended: ten minutes alone stays level-bounded, still a loop, and has moved on",
          (not rep_ua.is_clipped) and EDGE_WINDOW[0] < min(lvls) and max(lvls) < EDGE_WINDOW[1] and max(lvls) - min(lvls) < 14
          and min(self_sims) > 0.6 and changed >= 12,
          f"10-s levels {min(lvls):.1f} .. {max(lvls):.1f} dBFS; loop self-similarity at 20 / 300 / 580 s {[round(s, 2) for s in self_sims]}; "
          f"{changed} of 24 steps rewritten between the first and last of {len(mels)} melody prints")

    perrs = [(tag, l) for tag, _, res in reps for l in res.pd_console.splitlines() if l.lower().startswith("error")]
    check("no Pd errors in any render", not perrs, "; ".join(f"{t}: {l[:60]}" for t, l in perrs[:3]))
    eng = (HERE / f"{NAME}.pd").read_text(encoding="utf-8")
    check("engine patch is pure vanilla (ELSE lives in tend_play.pd)", "else/" not in eng and "else/" in (HERE / f"{NAME}_play.pd").read_text(encoding="utf-8"))
    integ = all(not rep.has_nan_inf and not rep.is_clipped for _, rep, _ in reps)
    check("integrity across all renders (no clip / NaN)", integ, "worst peak %.1f dBFS" % max(rep.peak_dbfs for _, rep, _ in reps))
    ok = all(c[1] for c in checks)
    print(f"\n{sum(c[1] for c in checks)}/{len(checks)} checks passed")
    print("RESULT:", "TEND VERIFIED" if ok else "NEEDS WORK")
    return ok


def demo(path):
    """Two renders to listen to: three minutes left alone at the defaults, and
    a played minute -- the dials moved the way a hand would, and the pads."""
    res = render(str(path), RenderSpec(duration=180.0, controls=(), search_paths=(str(HERE),)))
    rep = analyze(res.audio); w = _write_wav(HERE / f"{NAME}_demo_unattended.wav", res.audio)
    print(f"\ndemo (unattended) -> {w}  180 s  peak {rep.peak_dbfs:.1f} dBFS  onsets {rep.onset_count}  clip={rep.is_clipped}")
    ev = control.send("density", 0.0, at=0.05) + control.send("tempo", 130, at=0.05)
    for i in range(21):                                   # the melody comes in over ten seconds
        ev += control.send("density", 0.8 * i / 20, at=6.0 + i * 0.5)
    ev += control.bang("nextintensity", at=18.0)          # groove -> full
    for i in range(11):                                   # the band speeds up over five seconds
        ev += control.send("tempo", 130 + 45 * i / 10, at=22.0 + i * 0.5)
    for t, v in ((30.0, 0.7), (30.6, 0.45), (31.2, 0.2), (32.0, 0.5), (32.6, 1.0)):     # a filter dive and back
        ev += control.send("filter", v, at=t)
    ev += control.send("storm", 0.55, at=34.0) + control.send("storm", 0.15, at=40.0)
    ev += control.send("killlow", 1, at=41.0) + control.send("killlow", 0, at=43.5)
    ev += control.bang("nextpattern", at=44.0)
    for i in range(11):                                   # over the dune and back
        ev += control.send("distance", i / 10, at=46.0 + i * 0.4)
    for i in range(11):
        ev += control.send("distance", 1 - i / 10, at=52.0 + i * 0.5)
    ev += control.send("stutter", 1, at=56.0) + control.send("stutter", 0, at=56.9)
    for i in range(11):                                   # and the melody goes out
        ev += control.send("density", 0.8 * (1 - i / 10), at=57.0 + i * 0.3)
    res = render(str(path), RenderSpec(duration=62.0, controls=tuple(ev), search_paths=(str(HERE),)))
    rep = analyze(res.audio); w = _write_wav(HERE / f"{NAME}_demo_played.wav", res.audio)
    print(f"demo (played) -> {w}  62 s  peak {rep.peak_dbfs:.1f} dBFS  onsets {rep.onset_count}  clip={rep.is_clipped}")
    try:
        from pdverify.viz import spectrogram
        spectrogram(res.audio, HERE / f"{NAME}_demo_played.png", fmax=8000, title="tend, played")
    except Exception as e:
        print("spectrogram skipped:", e)


if __name__ == "__main__":
    path = build_all()
    print("built ->", path, f"({path.read_text().count(chr(10))} lines)")
    if "--build-only" in sys.argv:
        sys.exit(0)
    ok = verify(path)
    if ok or "--demo" in sys.argv:
        demo(path)
