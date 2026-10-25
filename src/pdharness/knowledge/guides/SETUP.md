# Setting up: an agent and its person

The kit is built for two roles working together. They need different
things from a setup, and most first-run trouble comes from a setup that
serves only one of them.

| | The agent | The person |
|---|---|---|
| does | builds, renders, checks claims, iterates, keeps the field log | installs things once, listens, plays, decides what is good |
| needs | a Pd it can find in every command, a project folder that persists, the kit's interpreter | Pd with a GUI, to open and play the `.pd`; the speaker the result will be heard on |
| cannot | hear. Claims are measured, not heard. | read a render's numbers into a sound |

Headless checks catch silence, clipping, a wrong pitch, a seam, or a
missing lift. They cannot tell whether a sound is beautiful, whether a
slider feels right, or whether it works under the picture. That part
is the person's. Get a rough version into their ears early, before
scaling up the verification ("feel before proof").

## 1. Install Pure Data properly, once (the person)

Install Pd where it will stay, from [puredata.info](https://puredata.info/downloads)
(vanilla, 0.54 or later; the kit is tested on 0.54.1 and 0.56.2):

- **Windows:** run the installer. Pd lands in
  `%LOCALAPPDATA%\Programs\Pd` or `Program Files\Pd`, which the kit finds
  without help.
- **macOS:** drag `Pd-<version>.app` into `/Applications`, which the kit
  finds without help. Or `brew install --cask pd`.
- **Linux:** `sudo apt install puredata` (Debian/Ubuntu), or your
  distribution's package. A machine with no display can still render
  headless.

**Avoid unpacking Pd into a throwaway sandbox.** It works for a test, but
the next session starts without it, and a Pd that only one shell can see
is the most common first-hour failure. If the agent runs in a sandbox,
give the sandbox a persistent Pd, or point it at the person's.

**ELSE is optional.** The kit's modules are all vanilla Pd. To add ELSE
anyway, use Pd's Help → Find externals ("else"); `doctor` reports whether
it is found.

## 2. Install the kit and run the doctor (either)

```bash
uv tool install --python 3.14 git+https://github.com/DashWieland/pdharness
pdharness doctor
```

`doctor` renders a one-second sine and checks that it heard an A4. A Pd
that passes is **remembered**: every later lookup finds the same binary
without an environment variable, whether from a fresh shell, a build
script or the MCP server. Run `doctor` again whenever Pd moves.
`pdharness doctor --json` prints the versions, which belong in every
field log.

Register the server with the agent's MCP client (`pdharness mcp-config`
prints the JSON for any client). An agent that only has a shell gets the
same loop from the CLI.

## 3. A project folder that persists, under git (the agent sets it up)

```bash
mkdir my-instruments && cd my-instruments && git init
pdharness new drone "a slow warm drone that opens up when touched"
```

- **Run from the project root.** `new` creates `instruments/<slug>/` and
  `field_tests/` beside it, and prints the layout before it writes
  anything (`--dry-run` to only look).
- **The build script is the source of truth.** The `.pd` is its output.
  Edit the script, never the `.pd`, and commit the script after every
  iteration that passes its claims. Then "what changed?" is a diff, and
  "it was better before" is a checkout.
- **Keep renders out of the history**, or in a separate folder you prune.
  Commit the final deliverables.
- **Pin the kit for a piece of work.** Note `pdharness --version` in the
  field log, and upgrade (`uv tool upgrade pdharness`) between pieces, not
  in the middle of one.

## 4. Habits for an agent with cold shells and no one at the machine

- **Run everything through the kit:** `pdharness run build_x.py`, or
  `pdharness run -m pdverify analyze x.pd --dur 6`. Those always have the
  kit's Python and the doctor's Pd.
- **Put anything that matters in a file or a claim, not in shell state.**
  An environment variable set in one command is gone in the next.
- **Make every claim a check.** Write the claims before building ("D
  dorian", "loops without a seam", "audible on a phone", "lifts in the
  last 4 s") and score them with `verify_patch` or `render_patch(...,
  expectations=...)`. "Sounds eerie" is not a claim; "darker than 800 Hz
  centroid, sparse (under 1 onset a second)" is.
- **Reaching outside the kit is a finding.** If you write numpy, or call
  another tool because the kit could not do something, put that in the
  field log's Lessons and name what was missing. That is how the kit
  learns.
- **Unattended runs:** scaffold with `--participant agent`, and answer the
  playability section from `probe_patch`.

## 5. The loop between the two

1. **The agent** builds to the claims, renders, and hands over three things
   together: the `.wav`, the `.pd`, and the scored claims (`verify_patch`'s
   card).
2. **The person** listens **on the device it will be heard on**. For short
   video that means a phone, at the volume people scroll at. Then they open
   the `.pd` in Pd and move the controls. A patch turns its audio on at
   load. If it is silent, check Media → DSP On, and that Pd's audio output
   is the right device.
3. **The person's words become the next claims.** "Too boomy on the phone"
   becomes a `band_level` claim. "The ending doesn't land" becomes a
   `change` claim over the last seconds. "It's busy" becomes an onset rate.
   The agent iterates against those.
4. **Ship the files the claims passed on, and only those.** For a delivered
   file, run `verify_patch` on the `.wav` itself, not on the patch that made
   it.

For delivered files (loops, a lift near the end, level, format), see
`guides/DELIVERING.md`.
