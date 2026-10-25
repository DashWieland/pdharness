"""The kit says who builds what, wherever a builder or an agent first meets it: the
README, the bank's start page, the server's instructions, and each worked example."""

from pathlib import Path

from pdharness import knowledge, server

ROOT = Path(__file__).resolve().parents[1]


def test_readme_says_who_builds_what():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Who builds what" in readme
    assert "You build your instrument" in readme
    assert "tools, not instruments" in readme


def test_the_agent_hears_it_too():
    assert "Who builds what" in knowledge.read("00_START_HERE.md")
    assert "not engines to adapt" in server.INSTRUCTIONS


def test_every_worked_example_says_it_is_not_an_engine():
    base = Path(knowledge.__file__).parent / "knowledge" / "examples"
    for readme in sorted(base.glob("*/README.md")):
        head = readme.read_text(encoding="utf-8")[:600]
        assert "worked example" in head.lower(), readme.parent.name
