"""Smoke tests for the kit: the bank is complete and readable, the tools run, the
scaffold builds and verifies, and the MCP server answers over stdio."""

from __future__ import annotations

import filecmp
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pdharness import knowledge, tools

ROOT = Path(__file__).resolve().parents[1]
HAS_PD = shutil.which("pd") is not None or os.environ.get("PDVERIFY_PD")


def test_bank_core_documents_exist():
    paths = knowledge.paths()
    for core in knowledge.CORE:
        assert core in paths, core
    assert paths[: len(knowledge.CORE)] == knowledge.CORE
    idx = knowledge.index()
    assert "00_START_HERE.md" in idx and "LESSONS.md" in idx


def test_bank_documents_read_and_are_described():
    for p in knowledge.paths():
        text = knowledge.read(p)
        assert text.strip(), p
        if p.endswith(".md") or p.endswith(".py") or p.endswith(".json"):
            assert p in knowledge.DESCRIPTIONS, f"undescribed knowledge file {p}"


def test_bank_read_refuses_escape():
    with pytest.raises(FileNotFoundError):
        knowledge.read("../pyproject.toml")


def test_plugin_skill_is_the_bank_skill():
    a, b = ROOT / "skills" / "pure-data", knowledge.root() / "skill"
    cmp = filecmp.dircmp(a, b)
    assert not cmp.left_only and not cmp.right_only and not cmp.diff_files, (cmp.left_only, cmp.right_only, cmp.diff_files)


def test_plugin_manifests_parse():
    for f in (ROOT / ".claude-plugin" / "plugin.json", ROOT / ".claude-plugin" / "marketplace.json", ROOT / ".mcp.json"):
        json.loads(f.read_text(encoding="utf-8"))


def test_box_count_ignores_subpatch_contents():
    text = ("#N canvas 0 0 100 100 10;\n#X obj 1 1 osc~;\n#N canvas 0 0 50 50 sub 0;\n#X obj 1 1 inlet;\n"
            "#X obj 1 1 outlet;\n#X restore 1 1 pd sub;\n#X text 1 1 hi;\n#X connect 0 0 1 0;\n")
    assert tools._top_level_box_count(text) == 3


def test_parse_controls_shapes():
    ev = tools.parse_controls([{"receive": "a", "value": 1}, {"bang": "b", "at": 0.5},
                               {"note": 60, "at": 0.1}, {"receive": "c", "values": [1, 2]}])
    assert len(ev) >= 4


@pytest.mark.skipif(not HAS_PD, reason="Pd not on PATH")
def test_doctor_hears_a4():
    info = tools.doctor()
    assert info.get("ok"), info


@pytest.mark.skipif(not HAS_PD, reason="Pd not on PATH")
def test_scaffold_builds_verifies_and_renders(tmp_path):
    out = tools.new_instrument("kit_smoke", "a test tone with a pitch slider", str(tmp_path))
    script = Path(out["build_script"])
    r = tools.run_script(str(script))
    tail = "\n".join(r["output_tail"])
    assert r["returncode"] == 0, tail
    assert "VERIFIED" in tail and "NOT VERIFIED" not in tail, tail
    patch = script.parent / "kit_smoke.pd"
    rep = tools.analyze_patch(str(patch), duration=1.5)
    assert not rep["integrity"]["silent"] and rep["report"]["note"] == "A3", rep["description"]
    # the interaction check: the slider's receive reaches the oscillator
    probe = tools.probe_patch(str(patch), watch=["pitch"], controls=[{"receive": "pitch_ui", "value": 69, "at": 0.2}])
    assert "69" in " ".join(probe["watched"]["pitch"]), probe
    card = tools.verify_patch(str(patch), [{"name": "note", "args": ["A3"]}, {"name": "not_silent"}], duration=1.5)
    assert card["passed"], card
    assert Path(out["field_log"]).exists()


@pytest.mark.skipif(not HAS_PD, reason="Pd not on PATH")
def test_mcp_server_answers_over_stdio():
    """Spawn `pdharness serve` and talk MCP to it with the SDK's client."""
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "pdharness.cli", "serve"])
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                assert {"doctor", "analyze_patch", "verify_patch", "probe_patch", "new_instrument",
                        "list_modules", "knowledge_read"} <= names, names
                res = await s.read_resource("knowledge://00_START_HERE.md")
                assert "iron rule" in res.contents[0].text
                mods = await s.call_tool("list_modules", {})
                assert "acid_voice" in mods.content[0].text
                prompts = {p.name for p in (await s.list_prompts()).prompts}
                assert "build_instrument" in prompts
    anyio.run(go)
