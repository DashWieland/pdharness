# tend

A meditation instrument for Pure Data. It plays itself; you steer. Six dials,
seven pads. Each dial does one thing you can hear at once, and there is no
wrong position on any of them.

It draws on a Gnawa-derived 12/8 groove from Morocco (the rolling three-pulse
beat with its two-against-three cross, the clatter of iron castanets, a low
plucked bass), an oud and a reed flute on a scale with one quarter-tone step,
and a drone that breathes. It is a fusion made by outsiders, from listening
rather than transcription; none of it reproduces ceremonial music, and it
should not be presented as if it did.

## The dials

| | left | right |
|---|---|---|
| **TEMPO** | slow | fast. The band takes about two seconds to get where you point it, so a quick turn sounds like the music speeding up, not a knob being turned. |
| **DENSITY** | no melody, just the groove | all of the tune. The strong beats come in first, so a little DENSITY is the same tune with fewer, longer notes. |
| **MUTATE** | the tune holds | the tune keeps rewriting itself as it plays |
| **FILTER** | dark: a resonant dive, only the lows left | open |
| **STORM** | dry | the dub storm: echoes feeding back, the room opening |
| **DISTANCE** | you are at the fire | the band is over the next dune: quiet, dark, late |

## The pads

| | |
|---|---|
| **STUTTER** | hold to freeze the last pulse |
| **KILL LOW** | hold to drop the drums and bass |
| **PATTERN+** | the next groove variant. It waits for the bar. |
| **INTENSITY+** | sparse, groove, full, round again. It waits for the bar. |
| **PHRASE+** | a fresh seed for the tune. It waits for the end of the loop. |
| **DRONE** | the drone on or off |
| **RECORD** | writes a take next to the patch |

Left alone it keeps going, and keeps changing, for as long as you like.

## Files

| File | What |
|---|---|
| `tend.pd` | the engine: pure vanilla Pd, runs headless (`pd -nogui -noaudio`) |
| `tend_play.pd` | a mouse face: on-screen keys and an X-Y pad, X = DENSITY, Y = FILTER (needs ELSE) |
| `kstring~.pd` | the plucked string |
| `tend.json` | the manifest: the whole surface, the MIDI map, the OSC ports and events |
| `build_tend.py` | generates everything, verifies it, renders the demos |
| `osc_smoke.py` | a real-time smoke test of the OSC API, and the smallest example client |
| `DESIGN.md` | the rule, the surface, what the rework removed, the four contracts |
| `tend_demo_unattended.wav`, `tend_demo_played.wav` | three minutes left alone; a played minute (regenerated, not committed) |

```bash
pdverify/.venv/Scripts/python.exe instruments/tend/build_tend.py
pdverify/.venv/Scripts/python.exe instruments/tend/osc_smoke.py
```

Close the patch in Pd before running either: the engine binds UDP 9000.

## A MiniLab 3, or anything else

| Control | MIDI | Does |
|---|---|---|
| Knobs 1 to 6 | CC 74, 71, 76, 77, 93, 18 | TEMPO, DENSITY, MUTATE, FILTER, STORM, DISTANCE |
| Pads 1 to 7 (channel 10) | notes 36 to 42 | STUTTER, KILL LOW, PATTERN+, INTENSITY+, PHRASE+, DRONE, RECORD |
| Keys (channel 1) | notes | the expert path: exact scale degrees, C4 = the tonic |

Over OSC on UDP 9000: `/density 0.7`, `/tempo 160`, `/nextpattern`,
`/record 1`, `/snapshot 2`, `/recall 2`. The engine reports on UDP 9001:
`/pulse`, `/bar`, `/note`, `/mel` (the tune, once a bar), `/ctl <name>
<value>` on every dial move, `/pattern`, `/intensity`, `/phrase` when a pad
lands, `/gust`. Everything is in `tend.json`.

## What the verifier holds it to

Every claim above is a check in `build_tend.py`, rendered headless and
measured: the groove's bar lengths and swing, each voice on its own, the
scale's quarter tone, the loop repeating and mutating, DENSITY from silence
to the whole tune, each dial doing what its name says, each pad landing where
it should, the MIDI map, the OSC twins, scenes, the manifest. On top of the
engine checks, four contracts: every corner of the six dials is safe, every
edge of every dial is music, every dial scanned end to end is continuous and
moves one thing, and ten minutes alone stays level, stays a loop, and moves
on. The real-time smoke test drives it over real UDP and records a take.

## In the browser

Live at <https://www.apophenia.blog/tend> (2026-09-22).

The engine compiles to WebAssembly with [pd4web](https://github.com/charlesneimog/pd4web);
the face is generated from `tend.json`. Nothing is hand-edited: the export is
deterministic and the web patch is held to the same render as the original.

```bash
pdverify/.venv/Scripts/python.exe instruments/tend/web_export.py --compile   # web/ + parity check + pd4web build
pdverify/.venv/Scripts/python.exe instruments/tend/web_export.py --serve     # http://localhost:8090/ with the COOP/COEP headers
```

| File | What |
|---|---|
| `web_export.py` | writes `web/tend.pd` (+ `declare -path Libs`, clone args as integers), `web/Libs/kstring~.pd`, `web/face.html`; renders both patches with pdverify and requires similarity 1.000 and a clean console; compiles; installs the face |
| `face_template.py` | the page: six dials, seven pads, the pulse, the tune once a bar, MIDI passthrough |
| `web/WebPatch/` | the deploy folder (not committed): `index.html`, `pd4web.js/.wasm/.data`, `_headers` |

Deploy by dropping `web/WebPatch/` on Netlify or Cloudflare Pages; the `_headers`
file sets `Cross-Origin-Opener-Policy: same-origin` and
`Cross-Origin-Embedder-Policy: require-corp`, which the runtime needs. On a host
that cannot set headers, `pd4web.threads.js` reloads once through a service
worker instead. RECORD and the OSC ports do not exist in the browser; everything
else on the surface does, and a MIDI controller plugged in before you press
begin drives it with the map above.

The pd4web toolchain lives outside the repo (`%LOCALAPPDATA%\Temp\p4w\v2`,
`pip install pd4web==3.3.3` in a `uv venv` at a short path); see
`instruments/lila_rig/WEB_PATH.md` for the install notes and gotchas.
