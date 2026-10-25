"""pdharness command line: doctor, serve, knowledge, new, run, field-log, install-skill, mcp-config."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, knowledge

PERSIST_LABELS = {
    "posix": "POSIX sh/bash/zsh",
    "powershell": "PowerShell, this session",
    "windows_setx": "Windows, every new shell",
}


def cmd_doctor(args) -> int:
    from . import tools
    info = tools.doctor(remember=not args.no_remember)
    if args.json:
        print(json.dumps(info, indent=2, default=str))
        return 0 if info.get("ok") else 1
    persist = info.pop("pd_persist", None)
    for k, v in info.items():
        print(f"{k:18s} {v}")
    if info.get("pd_remembered"):
        print()
        print("This Pd is remembered: every later lookup (a fresh shell, a build script, the MCP")
        print(f"server) finds it with no environment variable. ({info['pd_remembered']})")
        print("To pin it another way instead:")
        for key, label in PERSIST_LABELS.items():
            print(f"  {label + ':':28s} {persist[key]}")
    elif persist:
        print()
        print("Every Pd lookup here (doctor, the MCP server, a build script) follows pdverify's rule,")
        print("but a fresh shell may lack this shell's PATH. To make every shell find this same Pd:")
        for key, label in PERSIST_LABELS.items():
            print(f"  {label + ':':28s} {persist[key]}")
        print(f"  ({persist['note']})")
    return 0 if info.get("ok") else 1


def cmd_serve(args) -> int:
    from .server import main
    main()
    return 0


def cmd_knowledge(args) -> int:
    if args.path:
        sys.stdout.write(knowledge.read(args.path))
    else:
        sys.stdout.write(knowledge.index())
    return 0


def _print_layout(out: dict) -> None:
    print(f"{'project root':14s} {out['project_root']}")
    if out.get("note"):
        print(f"{'note':14s} {out['note']}")
    print("layout:")
    for f in out["layout"]:
        print(f"  {f}")
    for f in out.get("generated_by_the_build", []):
        print(f"  {f}   (written when the build runs)")


def cmd_new(args) -> int:
    from . import tools
    try:
        out = tools.new_instrument(args.slug, args.description, args.dir, participant=args.participant,
                                   dry_run=True, exact_dir=args.exact_dir)
    except (ValueError, FileExistsError) as e:
        print(f"pdharness new: {e}", file=sys.stderr)
        return 1
    _print_layout(out)
    if args.dry_run:
        print("(dry run: nothing written)")
        return 0
    out = tools.new_instrument(args.slug, args.description, args.dir, participant=args.participant,
                               exact_dir=args.exact_dir)
    print()
    for k in ("build_script", "readme", "field_log", "participant", "next"):
        print(f"{k:14s} {out[k]}")
    return 0


def cmd_run(args) -> int:
    """Run a build script (or -m module) with the kit's interpreter, PDVERIFY_PD set; stream
    its output and return its exit code."""
    from . import tools
    try:
        cmd, workdir = tools.script_command(args.script, args.args, module=args.module, cwd=args.cwd)
    except (ValueError, FileNotFoundError) as e:
        print(f"pdharness run: {e}", file=sys.stderr)
        return 2
    env = tools.script_env()
    print(f"[pdharness run] {' '.join(cmd)}  (cwd {workdir}; PDVERIFY_PD={env.get('PDVERIFY_PD', 'unset')})",
          file=sys.stderr, flush=True)
    sys.stdout.flush()
    return subprocess.run(cmd, cwd=str(workdir), env=env).returncode


def cmd_field_log(args) -> int:
    from . import tools
    out = tools.field_log_stub(args.slug, args.dir, participant=args.participant, exact_dir=args.exact_dir)
    for k, v in out.items():
        print(f"{k:14s} {v}")
    return 0


def cmd_install_skill(args) -> int:
    """Install the pure-data skill: into ~/.claude/skills by default, into any skills folder with
    --target, or print it (--print) for a runtime to file itself."""
    if args.print:
        sys.stdout.write(knowledge.skill_bundle())
        return 0
    if args.dest:
        dest = Path(args.dest).expanduser()
    elif args.target:
        dest = Path(args.target).expanduser() / knowledge.SKILL_NAME
    else:
        dest = Path.home() / ".claude" / "skills" / knowledge.SKILL_NAME
    src = knowledge.root() / "skill"
    if dest.exists() and not args.force:
        print(f"{dest} exists; pass --force to replace it")
        return 1
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"installed {src} -> {dest}")
    return 0


def cmd_mcp_config(args) -> int:
    exe = shutil.which("pdharness") or sys.argv[0]
    cfg = {"mcpServers": {"pdharness": {"type": "stdio", "command": "pdharness", "args": ["serve"]}}}
    print("# Claude Code (user scope):")
    print("claude mcp add --transport stdio --scope user pdharness -- pdharness serve")
    print()
    print("# Any MCP client (JSON):")
    print(json.dumps(cfg, indent=2))
    print()
    print(f"# resolved executable: {exe}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pdharness",
                                description="Bring your own agent to Pure Data instrument building.")
    p.add_argument("--version", action="version", version=f"pdharness {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="can this machine build and hear a patch? (and which Pd)")
    d.add_argument("--json", action="store_true", help="print the report as JSON")
    d.add_argument("--no-remember", action="store_true",
                   help="do not remember the Pd that passes (by default it is, so a cold shell finds it)")
    d.set_defaults(func=cmd_doctor)

    s = sub.add_parser("serve", help="run the MCP server on stdio")
    s.set_defaults(func=cmd_serve)

    k = sub.add_parser("knowledge", help="print the knowledge bank index, or one document")
    k.add_argument("path", nargs="?")
    k.set_defaults(func=cmd_knowledge)

    n = sub.add_parser("new", help="scaffold <project>/instruments/<slug>/ with a working build script",
                       description="Scaffold <project>/instruments/<slug>/ and <project>/field_tests/. Run it "
                                   "from the project root; from an instruments/ folder (or an instrument "
                                   "folder in one) the project root is the folder above.")
    n.add_argument("slug")
    n.add_argument("description")
    n.add_argument("--dir", default=None, help="project root (default: cwd)")
    n.add_argument("--exact-dir", action="store_true",
                   help="use --dir (or cwd) as the project root even if it is named instruments")
    n.add_argument("--participant", choices=["human", "agent"], default="human",
                   help="whose field log: a study session with a person, or an unattended agent run")
    n.add_argument("--dry-run", action="store_true", help="print the layout, write nothing")
    n.set_defaults(func=cmd_new)

    r = sub.add_parser("run", help="run a build script with the kit's interpreter (the MCP run_script)",
                       description="Run a build script with the Python that has pdbuild and pdverify, with "
                                   "PDVERIFY_PD set to the Pd doctor finds. `pdharness run build_x.py --build-only`; "
                                   "`pdharness run -m pdverify analyze x.pd --dur 6` runs a module.")
    r.add_argument("-m", dest="module", default=None, metavar="MODULE", help="run a module, like python -m")
    r.add_argument("--cwd", default=None, help="working directory (default: the script's folder, or cwd for -m)")
    r.add_argument("script", nargs="?", help="the script (with -m: the module's first argument)")
    r.add_argument("args", nargs=argparse.REMAINDER, help="passed to the script")
    r.set_defaults(func=cmd_run)

    f = sub.add_parser("field-log", help="create field_tests/<date>_<slug>.md from the template")
    f.add_argument("slug")
    f.add_argument("--dir", default=None, help="project root (default: cwd)")
    f.add_argument("--exact-dir", action="store_true")
    f.add_argument("--participant", choices=["human", "agent"], default="human")
    f.set_defaults(func=cmd_field_log)

    i = sub.add_parser("install-skill", help="install the pure-data skill (~/.claude/skills by default)")
    where = i.add_mutually_exclusive_group()
    where.add_argument("--target", default=None, metavar="DIR",
                       help="a skills folder; the skill goes in DIR/pure-data")
    where.add_argument("--dest", default=None, help="the exact folder to install the skill as")
    where.add_argument("--print", action="store_true",
                       help="write every file of the skill to stdout, between FILE markers, and install nothing")
    i.add_argument("--force", action="store_true", help="replace an existing install")
    i.set_defaults(func=cmd_install_skill)

    m = sub.add_parser("mcp-config", help="print how to register the server with an MCP client")
    m.set_defaults(func=cmd_mcp_config)
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
