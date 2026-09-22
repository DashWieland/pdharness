"""The knowledge bank: the documents shipped inside the package.

Everything under ``pdharness/knowledge/`` is served as MCP resources
(``knowledge://<relative path>``) and through ``pdharness knowledge``.  The
bank is the product: it is what turned a mediocre blind agent into one that
built ember in an afternoon.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

_ROOT = Path(str(resources.files("pdharness") / "knowledge"))

# Reading order for an agent that has nothing loaded.  Everything else is reference.
START = "00_START_HERE.md"
CORE = [
    START,
    "skill/SKILL.md",
    "lessons/LESSONS.md",
    "cookbook/COOKBOOK.md",
    "modules/CATALOGUE.md",
]

DESCRIPTIONS = {
    "00_START_HERE.md": "Read first: the loop, the iron rule, the tools, the deliverable, the deal.",
    "skill/SKILL.md": "Pure Data semantics for agents: the file format, execution order, the five things that bite.",
    "skill/references/file-format.md": "The .pd file format, field by field, verified against the runtime.",
    "skill/references/objects.md": "Object reference: inlets, outlets, arguments, the ones that mislead.",
    "skill/references/headless-verify.md": "Rendering without a sound card: how pdverify captures audio.",
    "lessons/LESSONS.md": "Every lesson from every field test, by theme. The compounding asset.",
    "cookbook/COOKBOOK.md": "pdbuild's field guide: patterns that work, gotchas that cost days.",
    "cookbook/PDBUILD_README.md": "pdbuild's API: Patch, init(), floatatom slots, extraction.",
    "modules/CATALOGUE.md": "Every verified module in pdbuild.modules and pdbuild.surface, with signatures.",
    "examples/tend/README.md": "tend, a complete verified instrument: what it is, for the player.",
    "examples/tend/DESIGN.md": "tend's design rule (one dial, one audible thing) and its four contracts.",
    "examples/tend/build_tend.py": "tend's build script: 2500 lines of Pd from pdbuild, with its 50-check verifier.",
    "examples/tend/tend.json": "tend's manifest: the control surface as a contract.",
    "field_test/PROTOCOL.md": "How a build session with a participant is run and measured.",
    "field_test/LOG_TEMPLATE.md": "The field log every build writes when it is done.",
}


def root() -> Path:
    return _ROOT


def paths() -> list[str]:
    out = []
    for p in sorted(_ROOT.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            out.append(p.relative_to(_ROOT).as_posix())
    # core first, in reading order, then the rest alphabetically
    core = [c for c in CORE if c in out]
    rest = [p for p in out if p not in core]
    return core + rest


def read(path: str) -> str:
    p = (_ROOT / path).resolve()
    if _ROOT.resolve() not in p.parents and p != _ROOT.resolve():
        raise FileNotFoundError(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    return p.read_text(encoding="utf-8")


def index() -> str:
    lines = ["# pdharness knowledge bank", "",
             "Read in this order when starting cold: " + ", ".join(f"`{c}`" for c in CORE) + ".", "",
             "| path | what |", "|---|---|"]
    for p in paths():
        lines.append(f"| `{p}` | {DESCRIPTIONS.get(p, '')} |")
    return "\n".join(lines) + "\n"
