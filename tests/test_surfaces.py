"""The kit as an agent without a persistent shell, an MCP client, or a person at the
machine meets it: one Pd per process and the line that persists it, a CLI `run`, a
`new` that keeps one project root, a skill that can be printed or filed anywhere, and a
field log for unattended runs."""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

from pdharness import __version__, cli, knowledge, scaffold, tools

ROOT = Path(__file__).resolve().parents[1]
HAS_PD = shutil.which("pd") is not None or os.environ.get("PDVERIFY_PD")


@pytest.fixture(autouse=True)
def fresh_pd():
    """Each test starts with no Pd settled on, and leaves none behind."""
    tools._PD = None
    yield
    tools._PD = None


@pytest.fixture
def fake_pd(tmp_path, monkeypatch):
    """A file PDVERIFY_PD can point at.  Never executed by these tests (the version query
    fails quietly), only located."""
    pd = tmp_path / "bin dir" / "fake_pd"
    pd.parent.mkdir()
    pd.write_text("", encoding="utf-8")
    monkeypatch.setenv("PDVERIFY_PD", str(pd))
    return pd


# ----------------------------------------------------------------- 1. one Pd

def test_locate_pd_says_which_pd_and_how(fake_pd):
    pd = tools.locate_pd(refresh=True)
    assert Path(pd["path"]) == fake_pd.resolve()
    assert pd["source"] == "env"
    assert "PDVERIFY_PD" in pd["found_by"]
    persist = pd["persist"]
    assert persist["posix"].startswith("export PDVERIFY_PD=") and str(fake_pd) in persist["posix"]
    assert "'" in persist["posix"]  # the path has a space: quoted for sh
    assert str(fake_pd) in persist["powershell"] and str(fake_pd) in persist["windows_setx"]


def test_persist_lines_quote_for_each_shell():
    p = "/opt/my pd/it's/pd"
    lines = tools.persist_lines(p)
    assert lines["posix"] == "export PDVERIFY_PD='/opt/my pd/it'\"'\"'s/pd'"
    assert lines["powershell"] == "$env:PDVERIFY_PD = '/opt/my pd/it''s/pd'"
    assert lines["windows_setx"] == 'setx PDVERIFY_PD "/opt/my pd/it\'s/pd"'


def test_the_located_pd_is_the_one_renders_and_scripts_get(fake_pd, tmp_path, monkeypatch):
    """Once settled, the process keeps its Pd: a render spec names it, and a script started
    with run_script finds it in PDVERIFY_PD even after this process's own variable is gone."""
    tools.locate_pd(refresh=True)
    monkeypatch.delenv("PDVERIFY_PD")
    assert Path(tools._spec(tmp_path / "x.pd", 1.0, None).pd_binary) == fake_pd.resolve()
    script = tmp_path / "show_env.py"
    script.write_text("import os, sys\nprint('PD=' + os.environ.get('PDVERIFY_PD', 'unset'))\n"
                      "print('PY=' + sys.executable)\n", encoding="utf-8")
    r = tools.run_script(str(script))
    assert r["returncode"] == 0, r
    out = "\n".join(r["output_tail"])
    assert f"PD={fake_pd.resolve()}" in out, out
    assert Path(r["pd"]) == fake_pd.resolve()
    assert Path(r["python"]) == Path(sys.executable)


def test_a_missing_pdverify_pd_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("PDVERIFY_PD", str(tmp_path / "nowhere" / "pd"))
    w = tools._env_warning()
    assert w and "does not exist" in w and "nowhere" in w


def test_source_classification_without_pdverify_saying():
    assert tools._classify_source(str(Path("proj") / "tools" / "pd-0.56-2" / "bin" / "pd")) == "dev"
    assert tools._classify_source(str(Path("/nowhere/special/pd"))) == "default"
    assert set(tools.PD_SOURCES) >= {"explicit", "env", "remembered", "path", "default", "dev"}


@pytest.mark.skipif(not HAS_PD, reason="Pd not on PATH")
def test_doctor_reports_the_pd_the_renders_use():
    info = tools.doctor()
    assert info["ok"], info
    assert info["pd"] == tools.locate_pd()["path"]
    assert info["pd_source"] in tools.PD_SOURCES
    assert info["pd"] in info["pd_persist"]["windows_setx"]
    assert info["pdharness"] == __version__ and info["python_executable"] == sys.executable


@pytest.mark.skipif(not HAS_PD, reason="Pd not on PATH")
def test_doctor_cli_prints_the_persist_lines(capsys):
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    pd = tools.locate_pd()["path"]
    assert re.search(r"^pd\s+" + re.escape(pd) + r"\s*$", out, re.M), out
    assert "export PDVERIFY_PD=" in out and "$env:PDVERIFY_PD" in out and "setx PDVERIFY_PD" in out
    assert cli.main(["doctor", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["pd"] == pd


# ----------------------------------------------------------------- 2. CLI run

def test_cli_run_uses_the_kit_interpreter_and_passes_args(tmp_path, capfd):
    script = tmp_path / "echo_args.py"
    script.write_text("import sys\nprint('ARGS', sys.argv[1:])\nprint('PY', sys.executable)\n"
                      "sys.exit(3 if '--fail' in sys.argv else 0)\n", encoding="utf-8")
    assert cli.main(["run", str(script), "a", "--build-only"]) == 0
    out = capfd.readouterr()
    assert "ARGS ['a', '--build-only']" in out.out
    assert f"PY {sys.executable}" in out.out
    assert "[pdharness run]" in out.err  # the header goes to stderr, the script's output to stdout
    assert cli.main(["run", str(script), "--fail"]) == 3


def test_cli_run_module(tmp_path, capfd):
    data = tmp_path / "d.json"
    data.write_text('{"tempo": 120}', encoding="utf-8")
    assert cli.main(["run", "-m", "json.tool", str(data)]) == 0
    assert '"tempo": 120' in capfd.readouterr().out


def test_cli_run_missing_script(tmp_path, capfd):
    assert cli.main(["run", str(tmp_path / "nope.py")]) == 2
    assert "nope.py" in capfd.readouterr().err


# ----------------------------------------------------------------- 3. new keeps one root

def test_new_from_an_instruments_folder_uses_its_parent(tmp_path):
    inst = tmp_path / "instruments"
    inst.mkdir()
    out = tools.new_instrument("drone", "a drone", str(inst))
    assert Path(out["project_root"]) == tmp_path.resolve()
    assert Path(out["build_script"]) == (tmp_path / "instruments" / "drone" / "build_drone.py").resolve()
    assert Path(out["field_log"]).parent == (tmp_path / "field_tests").resolve()
    assert "instruments/ folder" in out["note"]
    assert not (inst / "instruments").exists()


def test_new_from_inside_an_instrument_folder_uses_the_project_root(tmp_path):
    other = tmp_path / "instruments" / "other"
    other.mkdir(parents=True)
    (other / "build_other.py").write_text("", encoding="utf-8")
    out = tools.new_instrument("drone", "a drone", str(other))
    assert Path(out["project_root"]) == tmp_path.resolve()
    # a folder under instruments/ that is not an instrument is taken at its word
    plain = tmp_path / "instruments" / "projects"
    plain.mkdir()
    assert Path(scaffold.plan("drone", plain)["project_root"]) == plain.resolve()


def test_new_exact_dir_and_plain_root(tmp_path):
    inst = tmp_path / "instruments"
    inst.mkdir()
    out = tools.new_instrument("drone", "a drone", str(inst), exact_dir=True)
    assert Path(out["project_root"]) == inst.resolve() and "note" not in out
    plain = tmp_path / "proj"
    plain.mkdir()
    out = tools.new_instrument("drone", "a drone", str(plain))
    assert Path(out["build_script"]).parent == (plain / "instruments" / "drone").resolve()
    assert Path(out["field_log"]).parent == (plain / "field_tests").resolve()
    assert "note" not in out


def test_new_dry_run_writes_nothing_and_lists_the_layout(tmp_path):
    out = tools.new_instrument("drone", "a drone", str(tmp_path), dry_run=True)
    assert out["dry_run"] and not any(tmp_path.iterdir())
    assert [Path(p).name for p in out["layout"]] == ["build_drone.py", "README.md",
                                                     f"{_dt.date.today().isoformat()}_drone.md"]


def test_cli_new_prints_the_layout_first(tmp_path, capsys):
    inst = tmp_path / "instruments"
    inst.mkdir()
    assert cli.main(["new", "drone", "a drone", "--dir", str(inst), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("project root") and str(tmp_path.resolve()) in out
    assert str((tmp_path / "instruments" / "drone" / "build_drone.py").resolve()) in out
    assert "dry run" in out and not (inst / "drone").exists()
    assert cli.main(["new", "drone", "a drone", "--dir", str(inst)]) == 0
    assert (inst / "drone" / "build_drone.py").exists()
    assert cli.main(["new", "drone", "a drone", "--dir", str(inst)]) == 1  # exists: refused, clearly
    assert "build_drone.py" in capsys.readouterr().err


def test_scaffolded_script_says_to_run_it_with_the_kit(tmp_path):
    out = tools.new_instrument("drone", "a drone", str(tmp_path))
    assert "pdharness run build_drone.py" in Path(out["build_script"]).read_text(encoding="utf-8")
    assert out["next"].startswith("pdharness run ")


# ----------------------------------------------------------------- 5. the skill anywhere

def test_install_skill_print_writes_every_file(capsys):
    assert cli.main(["install-skill", "--print"]) == 0
    out = capsys.readouterr().out
    files = knowledge.skill_files()
    assert files[0][0] == "SKILL.md"
    assert out.index("===== FILE: SKILL.md =====") < out.index("===== FILE: references/")
    for rel, text in files:
        assert f"===== FILE: {rel} =====" in out and f"===== END FILE: {rel} =====" in out
        body = out.split(f"===== FILE: {rel} =====\n", 1)[1].split(f"\n===== END FILE: {rel} =====", 1)[0]
        assert body == text.replace("\r\n", "\n").rstrip("\n"), rel


def test_install_skill_target(tmp_path, capsys):
    skills = tmp_path / "my skills"
    assert cli.main(["install-skill", "--target", str(skills)]) == 0
    got = sorted(p.relative_to(skills / "pure-data").as_posix() for p in (skills / "pure-data").rglob("*") if p.is_file())
    assert got == sorted(rel for rel, _ in knowledge.skill_files())
    assert cli.main(["install-skill", "--target", str(skills)]) == 1
    assert cli.main(["install-skill", "--target", str(skills), "--force"]) == 0
    with pytest.raises(SystemExit):
        cli.main(["install-skill", "--print", "--target", str(skills)])


# ----------------------------------------------------------------- 6. the agent's field log

def test_agent_field_log(tmp_path):
    out = tools.field_log_stub("drone", str(tmp_path), participant="agent")
    text = Path(out["path"]).read_text(encoding="utf-8")
    assert "unattended agent run" in text and "drone" in text
    assert _dt.date.today().isoformat() in text and f"pdharness {__version__}" in text
    assert "probe_patch" in text and "Participant (runtime)" in text
    assert not re.search(r"<(slug|date|kit|pd)>", text), text
    assert str(Path.home()) not in text  # the logs go back anonymised


def test_home_paths_are_anonymised_in_the_log():
    home = str(Path.home())
    assert scaffold._home_as_tilde(str(Path(home) / "pd" / "bin" / "pd")).startswith("~")
    assert scaffold._home_as_tilde("/usr/bin/pd") == "/usr/bin/pd"


def test_human_field_log_is_the_synced_template(tmp_path):
    out = tools.field_log_stub("drone", str(tmp_path))
    text = Path(out["path"]).read_text(encoding="utf-8")
    assert text == knowledge.read("field_test/LOG_TEMPLATE.md").replace("<slug>", "drone")
    with pytest.raises(ValueError):
        tools.field_log_stub("drone", str(tmp_path), participant="robot")


def test_field_log_from_an_instruments_folder_lands_beside_it(tmp_path):
    inst = tmp_path / "instruments"
    inst.mkdir()
    out = tools.field_log_stub("drone", str(inst), participant="agent")
    assert Path(out["path"]).parent == (tmp_path / "field_tests").resolve()


def test_new_with_an_agent_participant_writes_the_agent_log(tmp_path):
    out = tools.new_instrument("drone", "a drone", str(tmp_path), participant="agent")
    assert "unattended agent run" in Path(out["field_log"]).read_text(encoding="utf-8")
    assert cli.main(["field-log", "hum", "--dir", str(tmp_path), "--participant", "agent"]) == 0


# ----------------------------------------------------------------- 2. surfaces, documented

def _mcp_tools() -> dict:
    import anyio
    from pdharness import server

    return {t.name: t for t in anyio.run(server.mcp.list_tools)}


def _readme_rows() -> list[str]:
    return [l for l in (ROOT / "README.md").read_text(encoding="utf-8").splitlines() if l.startswith("| ")]


def test_readme_labels_every_mcp_tool_with_its_surface():
    rows = _readme_rows()
    for name in _mcp_tools():
        row = next((r for r in rows if r.startswith(f"| `{name}`") or f", `{name}`" in r.split("|")[1]), None)
        assert row, f"README's tool table lacks {name}"
        surface = row.split("|")[3].strip()
        assert surface == "both" or surface.startswith("MCP"), (name, surface)
    run_row = next(r for r in rows if r.startswith("| `run_script`"))
    assert "pdharness run" in run_row


def test_readme_names_every_cli_command():
    import argparse

    parser = cli.build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for cmd in sub.choices:
        assert f"pdharness {cmd}" in readme, cmd


def test_mcp_tools_take_the_new_parameters():
    t = _mcp_tools()
    assert {"participant", "dry_run", "exact_dir"} <= set(t["new_instrument"].input_schema["properties"])
    assert {"participant", "exact_dir"} <= set(t["field_log_stub"].input_schema["properties"])


def test_readme_install_line_names_a_python_the_package_allows():
    """The install line pins the interpreter (uv floats to the newest otherwise), and the
    version it names must satisfy requires-python."""
    import tomllib

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"uv tool install --python (\d+)\.(\d+) git\+", readme)
    assert m, "the install line should name a Python"
    req = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]
    floor = re.fullmatch(r">=(\d+)\.(\d+)", req)
    assert floor, f"requires-python {req!r}: a floor only (no upper bound without evidence)"
    assert (int(m.group(1)), int(m.group(2))) >= (int(floor.group(1)), int(floor.group(2)))
