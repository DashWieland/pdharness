# Module catalogue

Every function in `pdbuild.modules` and `pdbuild.surface`, with its
signature. Each module ships with a render-verified test that it makes the
sound it claims. Compose from these before writing raw Pd, and audit each
one against what this instrument actually needs (Lessons, "the claw hammer").

Usage pattern: every module takes the `Patch` first, then its inputs (a
trigger node, a signal node, a control node), then keyword parameters, and
returns the node(s) to wire onward. Import as
`from pdbuild.modules import voices, drums, filters, effects, envelopes, control, sequencing, scales`
and `from pdbuild import surface`.

## Synth voices (`pdbuild.modules.voices`)

| Function | Does |
|---|---|
| `oscillator(patch, pitch, *, waveform='saw', glide_ms=0.0)` | A bipolar oscillator at `pitch` (MIDI). `waveform` is 'saw', 'square' or 'sine'. |
| `subtractive_voice(patch, gate, pitch, *, waveform='saw', cutoff=1200.0, resonance=2.0, attack=5.0, decay=200.0, glide_ms=0.0, gain=0.3)` | The classic: oscillator, resonant lowpass, amp envelope. |
| `acid_voice(patch, gate, pitch, *, waveform='saw', cutoff=350.0, env_depth=2200.0, resonance=3.5, decay=180.0, glide_ms=0.0, drive=2.5, gain=0.3)` | TB-303-flavoured: saw into a resonant ladder whose cutoff is swept by the envelope, then drive. |
| `fm_voice(patch, gate, pitch, *, ratio=2.0, index=5.0, attack=3.0, decay=250.0, glide_ms=0.0, gain=0.3)` | Two-operator FM: a modulator at `ratio` x pitch, `index` deep. |

## Drums (`pdbuild.modules.drums`)

| Function | Does |
|---|---|
| `kick(patch, trigger, *, tune=50.0, punch=110.0, pitch_ms=50.0, decay=180.0, drive=1.6, gain=0.8)` | A sine whose pitch drops from `punch` to `tune` fast, with drive. |
| `snare(patch, trigger, *, tone=1800.0, q=2.0, decay=150.0, gain=0.5)` | Band-passed noise burst with a short decay. |
| `hat(patch, trigger, *, cutoff=7000.0, decay=45.0, gain=0.3)` | Bright high-passed noise with a very short decay. |

## Envelopes and control (`envelopes`, `control`)

| Function | Does |
|---|---|
| `envelopes.ad_envelope(patch, trigger, *, attack=5.0, decay=200.0, peak=1.0)` | Attack/decay, retriggered by `trigger`. |
| `envelopes.asr_envelope(patch, gate, *, attack=5.0, release=100.0, peak=1.0)` | Gated attack/sustain/release. |
| `control.glide(patch, control, *, time_ms=50.0)` | Portamento: ramp a stepped control to a smooth signal. |
| `control.smooth(patch, control, *, time_ms=25.0, lo=0.0, hi=1.0)` | Scale a 0..1 control into `lo..hi` and de-zipper it to a signal. |

## Filters and effects (`filters`, `effects`)

| Function | Does |
|---|---|
| `filters.lowpass(patch, sig, *, cutoff=1000.0)` | One-pole `[lop~]`. Darkens. |
| `filters.highpass(patch, sig, *, cutoff=200.0)` | One-pole `[hip~]`. Brightens. |
| `filters.bandpass(patch, sig, *, center=1000.0, q=4.0)` | Resonant `[bp~]`. |
| `filters.resonant_lowpass(patch, sig, *, cutoff=1000.0, resonance=2.0)` | Moog-style ladder `[bob~]`, the acid staple. Two of these in series shave the top octave: measure the bus. |
| `effects.saturate(patch, sig, *, drive=2.0, level=0.7)` | Soft clip through `tanh`. |
| `effects.delay(patch, sig, *, time_ms=250.0, feedback=0.4, mix=0.5, name=None)` | Feedback delay / echo. |
| `effects.chorus(patch, sig, *, rate=0.3, depth_ms=6.0, base_ms=14.0, mix=0.5, name=None)` | LFO-modulated delay mixed with the dry signal. |

## Clocks, patterns and melody (`sequencing`)

| Function | Does |
|---|---|
| `swing_clock(patch, *, groups=(3,3,3,3), tempo_recv='tempo', swing_recv='swing', run_recv='run', factor_recv=None, pulse_div=2, metro_ms=180.0, prefix='')` | One `[metro]` retimed every tick so the first pulse of each beat lands; sends `pulse`, `bar`, `pulsems`. 12/8 by default (four groups of three). |
| `step_tables(patch, presets, *, rows=None, select_recv='pattern', pulse_recv='pulse', intensity_recv='intensity', reset_send='reset', gate_rows=None, prefix='')` | Per-pulse pattern tables loaded by one message per preset, with intensity tiers and a reset on change. |
| `gated_value(patch, tables, gate_row, value_row, *, pulse_recv='pulse', intensity_recv='intensity')` | The value of `value_row` on the pulses where `gate_row` passes its tier. |
| `melody_loop(patch, *, phrases, steps=24, barlen=12, beat=3, ...)` | A Turing-machine-style melody loop: `steps` scale degrees in a table, re-seeded from `phrases`, mutated per pass, thinned by density (strong beats first). **Audit before adopting:** the tend build rejected it (an older drift bug, no gravity, no step send) and built its own; check the current version against your needs. |
| `phrase_steps(phrase, steps)` | A phrase string to a list of step tokens (`.` rest, `h` hold, ints degrees). |
| `step_priority(steps, barlen, beat)` | Rank per step, strongest first, for density thinning. |

## Scales (`scales`)

| Function | Does |
|---|---|
| `scale_tables(patch, scales, *, select_recv='maqam', scale_table='scale', qflag_table='qflag', size=8)` | A bank of scales as two tables: semitone offset per degree and a quarter-tone flag. |
| `scale_degree(patch, degree, *, scale_table='scale', qflag_table='qflag', tonic_recv='tonic', neutral_recv='neut', degrees_per_octave=7)` | Scale degree (any integer, negative below the tonic) to a fractional MIDI note. |
| `euclid(k, n=16)` / `euclid_rows(n=16)` | Euclidean rhythms E(k, n); all rows as presets per density. |

## The control surface (`pdbuild.surface`)

| Function | Does |
|---|---|
| `control(patch, name, kind, *, x, y, default=0, label=None, lo=0.0, hi=1.0, n=4, size=None, color=None, ...)` | One control: the widget with receive `<name>_ui` at `(x, y)`, a `[s name]` twin, initialised to `default`. `kind` is 'hsl', 'vsl', 'tgl', 'nbx', 'hradio', 'bng'. **This is the idiom**: a hand, a MIDI map, an OSC message and a headless test all drive `<name>_ui`. |
| `column(patch, x, y, controls, *, step=58, compact_step=40, ...)` | A vertical column of controls; returns handles and the end y. |
| `display(patch, name, x, y, *, width=7, send=None)` | A number box that shows whatever is sent to `name`. |
| `pad_row(patch, x, y, pads, *, spacing=42, ...)` | A horizontal row of pads, the on-screen twin of a MIDI pad row. |
| `cc_map(patch, entries, *, x, y, fake_recv='fakecc', ...)` | A `[ctlin]` router: `(cc, name, lo, hi)` entries drive `<name>_ui`; `fakecc` lets a test impersonate the controller. |
| `note_split(patch, *, pad_channel=10, x, y, keys_send='midi_in', pads_send='pad_in')` | `[notein]` split by channel into keys and pads. |
| `ui_name(name)` | `<name>_ui`. |
| `widget_size(kind, ...)` / `widget_text(kind, ...)` | Pd's drawn size and the IEM object text, for layout. |

`pdbuild.preview.layout_png(patch)` draws the canvas; `pdbuild.preview.overlaps(...)`
finds widgets that collide. Run it in the build, not by hand afterwards.

## Not in the library yet (requested by field logs)

A pitch follower (`[adc~]` to `sigmund~` with a steadiness gate) and a
`slop~` follower VCA, from the halo build; a pad row with `land_on="bar"`;
a swung clock with a tempo glide that does not glide on init. If you build
one of these, say so in your field log.
