"""pdharness command line: doctor, serve, knowledge, new, install-skill, mcp-config."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__, knowledge


def cmd_doctor(args) -> int:
    from . import tools
    info = tools.doctor()
    for k, v in info.items():
        print(f"{k:16s} {v}")
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


def cmd_new(args) -> int:
    from . import tools
    out = tools.new_instrument(args.slug, args.description, args.dir)
    for k, v in out.items():
        print(f"{k:14s} {v}")
    return 0


def cmd_install_skill(args) -> int:
    """Copy the pure-data skill into ~/.claude/skills so Claude Code loads it for Pd work."""
    dest = Path(args.dest).expanduser() if args.dest else Path.home() / ".claude" / "skills" / "pure-data"
    src = knowledge.root() / "skill"
    if dest.exists() and not args.force:
        print(f"{dest} exists; pass --force to replace it")
        return 1
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
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
    d = sub.add_parser("doctor", help="can this machine build and hear a patch?")
    d.set_defaults(func=cmd_doctor)
    s = sub.add_parser("serve", help="run the MCP server on stdio")
    s.set_defaults(func=cmd_serve)
    k = sub.add_parser("knowledge", help="print the knowledge bank index, or one document")
    k.add_argument("path", nargs="?")
    k.set_defaults(func=cmd_knowledge)
    n = sub.add_parser("new", help="scaffold instruments/<slug>/ with a working build script")
    n.add_argument("slug")
    n.add_argument("description")
    n.add_argument("--dir", default=None, help="project directory (default: cwd)")
    n.set_defaults(func=cmd_new)
    i = sub.add_parser("install-skill", help="copy the pure-data skill into ~/.claude/skills")
    i.add_argument("--dest", default=None)
    i.add_argument("--force", action="store_true")
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
