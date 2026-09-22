# The .pd file format

Plain text. Records are `;`-terminated and may span physical lines. Reference
(unofficial but core-stable): https://puredata.info/docs/developer/PdFileFormat

## Records

```
#N canvas <x> <y> <width> <height> <font>;        top-level window
#N canvas <x> <y> <w> <h> <name> <open>;          subpatch (opens a nested scope)
#X restore <x> <y> pd <name>;                     ...closes it, placing [pd name]

#X obj   <x> <y> <class> <args...>;
#X msg   <x> <y> <content>;
#X text  <x> <y> <comment text>;
#X floatatom  <x> <y> <w> <lo> <hi> <labelpos> <label> <recv> <send> <font>;
#X symbolatom <x> <y> ...;                        (same ten fields as floatatom)


#X connect <src_index> <outlet> <dst_index> <inlet>;

#X declare -path <dir> -lib <libname>;            dependencies
#X coords ...;                                    graph-on-parent geometry
```

## Indices — the thing that breaks patches

Objects are numbered **0, 1, 2, … in file order, per canvas**, and **every**
`#X` element counts: objects, messages, **comments**, floatatoms, GUI objects.
`#X connect` refers to those numbers. Insert a comment in the middle of a patch
and every subsequent connection silently shifts.

A subpatch (`#N canvas … #X restore`) counts as **one** index on the parent; the
objects inside it have their own independent numbering.

Pd drops connections with out-of-range indices and warns in the console rather
than refusing to load — so a mis-indexed patch opens and is quietly mis-wired.

## Number and symbol boxes (gatoms)

The ten fields, in Pd's own order — the two name slots are **receive first,
then send** (verified against the Pd runtime, not documentation):

```
#X floatatom  30 100 8  0 0 0  <label> <receive> <send> <font>;
#X symbolatom 30 140 12 0 0 0  <label> <receive> <send> <font>;
```

- **receive** (slot 8) — the box *displays* what is sent to that name.
- **send** (slot 9) — typing in the box, or a value arriving at it, *outputs*
  to that name.

Cross them and you get a box that looks wired and is inert. **No audio render
can catch this** — a headless render never types into a box. Check the emitted
record, or probe it at runtime (below).

**A gatom with a receive set has no inlet.** Give the receive slot a name and
the box's inlet disappears, exactly like a GUI object's does; any patch cord
into it then fails to load with:

```
error: <patch>.pd <a> 0 <b> 0 (receive->gatom) connection failed
```

So pick one: either set the receive field, *or* wire `[r name] → box inlet` and
leave the receive field `-`. Both display; only the wired form can also be fed
by a cord.

**Runtime probe for read-out boxes** — the check that substitutes for a human
looking at the screen: on a *copy* of the patch, write a name into the box's
**send** slot, add `[r thatname] → [print]`, drive the patch (`\; hit-happy
bang`), and run it headless. The box re-emits whatever it displays, so the
print proves the read-out really updates.

## Escaping

Inside message boxes **and comments**:

| Char | Write as | Why |
|---|---|---|
| `,` | `\,` | otherwise it separates messages — the tail gets sent somewhere and errors |
| `;` | `\;` | otherwise it redirects to a named receiver |
| `$` | `\$` | **always**, for `$1`…`$9` and `$0` in object boxes, message boxes and comments — see below |

A message box beginning `\; name args` sends `args` to `[receive name]` — this
is how `; pd dsp 1` turns audio on.

**Dollar signs in files are written escaped: `\$1`, `\$0-name`.** This is how
Pd itself saves them, and it is not optional: an *unescaped* `$1` in a `.pd`
file is evaluated while the file is being read, against nothing — the box is
built with `0` in its place and the console says `$1: argument number out of
range` (verified on Pd 0.56: `f $2` in an abstraction instantiated as
`[abs 5 111]` gave 0; `f \$2` gave 111). The symptom is an abstraction whose
`[lop~ \$2]`/`[*~ \$3]` all came out as 0 — silence with no other error.
The escaped form `\$1`–`\$9` in an **object** box expands at creation from the
abstraction's creation args (under `[clone]`, `\$1` is the instance number and
the user's args start at `\$2`); `\$0` expands to a per-instance unique number.
In a **message** box, `\$1…` expand from the incoming message at message time.
`$v1`/`$f1`/`$i1` (expr family variables) are not touched — `$` followed by a
non-digit is left alone, so `expr~ tanh($v1)` is safe to write literally.
(Comments with `$1` in them are *also* evaluated at load and error the same
way — don't put bare dollars in comments.)

## Arrays with saved data

```
#N canvas 0 0 450 300 (subpatch) 0;
#X array myseq 16 float 2;
#A 0 60 62 64 67 64 62 60 60 …;
#X coords 0 1 16 -1 200 140 1;
#X restore 100 100 graph;
```

`float 2` = save contents; `#A <start_index> <values…>` supplies them. The whole
block is one index on the parent. `[table name size]` creates an array *without*
saved contents — fine when you fill it at runtime, useless for baked-in data.

If you don't need persistence, it is often simpler to avoid arrays entirely:
a `[sel 0 1 2 …]` fanning into per-step message boxes stores a fixed pattern
with no array bookkeeping, and a builder generates it mechanically.

## GUI objects

IEM GUIs are `#X obj` with long positional parameter lists. Get them from a
patch Pd saved rather than inventing them:

```
#X obj 30 40 tgl 22 0 empty empty empty 0 -9 0 12 #202020 #00ffcc #000000 0 1;
#X obj 30 80 hradio 26 1 0 4 empty empty empty 0 -9 0 12 #fcfcfc #000000 #000000 0;
#X obj 30 120 hsl 160 22 0 1 0 0 empty empty empty -2 -9 0 12 #fcfcfc #000000 #000000 0 1;
#X obj 30 160 bng 30 250 50 0 empty empty empty 0 -9 0 12 #fcfcfc #000000 #000000;
```

Colours are `#rrggbb` in current Pd (old files use negative integers). The
`send`/`receive` symbol fields let a GUI talk without cords — very useful for
control surfaces. Note the `init` flag: with it **off** (the common default) the
control emits nothing at load.

## Line endings & encoding

Write UTF-8 with `\n`; Pd is line-ending tolerant. Paths inside message boxes
should use forward slashes (works on Windows too) and be **absolute** where a
relative path would be resolved against the wrong canvas. Avoid spaces in paths
used inside messages — they tokenize as separate atoms.
