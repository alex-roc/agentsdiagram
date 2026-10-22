"""Command line interface: ``agentsdiagram scan|check|schema|lsp``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .ir import json_schema

FORMATS = ("mermaid", "json", "html", "markdown")


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("path", nargs="?", default=".", help="file or directory (default: .)")
    p.add_argument(
        "--framework",
        action="append",
        choices=["pydantic_ai", "smolagents"],
        help="only analyse this framework (repeatable)",
    )
    p.add_argument("--include", action="append", default=[], help="glob relative to the project root (repeatable)")
    p.add_argument("--exclude", action="append", default=[], help="glob relative to the project root (repeatable)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentsdiagram",
        description="Static diagrams of AI agents, tools and flows (PydanticAI, smolagents).",
    )
    parser.add_argument("--version", action="version", version=f"agentsdiagram {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="analyse code and print a diagram")
    _common(scan)
    scan.add_argument("-f", "--format", choices=FORMATS, default="mermaid")
    scan.add_argument("-o", "--output", help="write to this file instead of stdout")
    scan.add_argument("--title", help="diagram title")

    check = sub.add_parser("check", help="report diagnostics; exit 1 on errors (for CI / pre-commit)")
    _common(check)
    check.add_argument("--strict", action="store_true", help="also fail on warnings")
    check.add_argument("--json", action="store_true", help="print diagnostics as JSON")

    sub.add_parser("schema", help="print the JSON Schema of the IR")

    lsp = sub.add_parser("lsp", help="run the language server over stdio (needs agentsdiagram[lsp])")
    lsp.add_argument("--stdio", action="store_true", help="accepted for editor compatibility (stdio is the default)")
    return parser


def _write(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "schema":
        _write(json.dumps(json_schema(), indent=2) + "\n", None)
        return 0
    if args.command == "lsp":
        try:
            from .lsp import serve
        except ImportError as exc:  # pragma: no cover - depends on the optional extra
            print(
                f"agentsdiagram lsp needs the [lsp] extra: uvx --from 'agentsdiagram[lsp]' agentsdiagram lsp"
                f" or pip install 'agentsdiagram[lsp]' ({exc})",
                file=sys.stderr,
            )
            return 2
        serve()
        return 0

    from .analyze import analyze

    path = Path(args.path)
    if not path.exists():
        print(f"agentsdiagram: {path} does not exist", file=sys.stderr)
        return 2
    project = analyze(path, frameworks=args.framework, include=args.include, exclude=args.exclude)

    if args.command == "check":
        failing = {"error", "warning"} if args.strict else {"error"}
        if args.json:
            _write(json.dumps([d.model_dump(mode="json") for d in project.diagnostics], indent=2) + "\n", None)
        else:
            for d in project.diagnostics:
                where = f"{d.ref.file}:{d.ref.range.start.line}:{d.ref.range.start.column + 1}" if d.ref else "-"
                print(f"{where}: {d.severity} {d.code} {d.message}")
            n_agents = sum(1 for n in project.nodes if n.kind == "agent")
            print(
                f"{n_agents} agents, {len(project.nodes)} nodes, {len(project.diagnostics)} diagnostics",
                file=sys.stderr,
            )
        return 1 if any(d.severity in failing for d in project.diagnostics) else 0

    title = args.title or (path.resolve().name if path.is_dir() else path.name)
    if args.format == "json":
        text = project.model_dump_json(indent=2) + "\n"
    elif args.format == "html":
        from .render.html import ViewerBundleMissing
        from .render.html import render as render_html

        try:
            text = render_html(project, title=title)
        except ViewerBundleMissing as exc:
            print(f"agentsdiagram: {exc}", file=sys.stderr)
            return 2
    else:
        from .render.mermaid import MAX_EDGES, render, too_large

        if too_large(project):
            print(
                f"agentsdiagram: {len(project.edges)} edges exceeds Mermaid's default limit ({MAX_EDGES}); "
                "narrow it with --include or use --format html",
                file=sys.stderr,
            )
        diagram = render(project, title=title if args.format == "mermaid" else None)
        text = diagram if args.format == "mermaid" else f"# {title}\n\n```mermaid\n{diagram}```\n"
    _write(text, args.output)
    if not project.nodes:
        print("agentsdiagram: no PydanticAI or smolagents agents found", file=sys.stderr)
        if args.include:
            print(f"  note: --include globs are relative to the project root ({project.root})", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
