"""``agentsdiagram edit``: the plan and edit operations from the command line.

Nodes are named by id, or by name when that is unambiguous (``triage``, ``ask_billing``), so
the commands read well in scripts, tutorials and coding agents. Every command prints the diff;
``--dry-run`` prints it without writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from ..ir import EditRequest, EditResult, Node, Project
from .doc import EditError
from .engine import plan_edit
from .textedit import unified_diff

OPS = {
    "add-agent": "plan a new agent (optionally managed by / delegated from --parent)",
    "add-tool": "plan a tool for an agent (a stub that raises NotImplementedError)",
    "add-mcp": "connect an MCP server (--url or --command) to an agent",
    "connect": "let SOURCE hand work to TARGET (managed agent / delegation tool)",
    "disconnect": "remove the relation from SOURCE to TARGET",
    "remove": "remove a tool, MCP server, toolset or agent",
    "set-model": "change the model of an agent",
    "set-instructions": "change (or, with '', remove) the instructions of an agent",
    "export-spec": "PydanticAI: move an agent's settings to an Agent Spec YAML",
}


def add_parser(sub: argparse._SubParsersAction) -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-p", "--project", default=".", help="project folder or file (default: .)")
    common.add_argument("--dry-run", action="store_true", help="print the diff, write nothing")
    common.add_argument("--json", action="store_true", help="print the result as JSON")

    edit = sub.add_parser(
        "edit",
        help="change the code: plan agents and tools, connect, remove, set models",
        description="Plan and edit agents from the command line. Each command prints the diff it applies.",
    )
    ops = edit.add_subparsers(dest="op", required=True, metavar="OPERATION")

    def op(name: str) -> argparse.ArgumentParser:
        return ops.add_parser(name, parents=[common], help=OPS[name], description=OPS[name].capitalize() + ".")

    p = op("add-agent")
    p.add_argument("name")
    p.add_argument("--file", help="file to write it in, created if missing (default: the parent's file)")
    p.add_argument("--framework", choices=["smolagents", "pydantic_ai"])
    p.add_argument("--parent", help="agent that manages (smolagents) or delegates to (PydanticAI) the new one")
    p.add_argument("--model")
    p.add_argument("--instructions")
    p.add_argument("--description")
    p.add_argument("--class", dest="agent_class", choices=["CodeAgent", "ToolCallingAgent"], help="smolagents")

    p = op("add-tool")
    p.add_argument("agent")
    p.add_argument("name")
    p.add_argument("--description")
    p.add_argument("--params", help="parameter list, e.g. 'order_id: str, limit: int = 5' (default: 'query: str')")
    p.add_argument("--returns", help="return type (default: str)")

    p = op("add-mcp")
    p.add_argument("agent")
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--url")
    target.add_argument("--command", dest="mcp_command", help="stdio command line, e.g. 'uvx mcp-server-fetch'")
    p.add_argument("--name", help="variable name (default: derived from the URL or command)")

    p = op("connect")
    p.add_argument("source")
    p.add_argument("target")
    p.add_argument("--description", help="smolagents: description for TARGET if it has none")

    p = op("disconnect")
    p.add_argument("source")
    p.add_argument("target")

    p = op("remove")
    p.add_argument("node")

    p = op("set-model")
    p.add_argument("agent")
    p.add_argument("model")

    p = op("set-instructions")
    p.add_argument("agent")
    p.add_argument("instructions")

    p = op("export-spec")
    p.add_argument("agent")
    p.add_argument("--path", help="spec file relative to the project root (default: next to the agent)")
    p.add_argument("--no-replace", action="store_true", help="only write the YAML, keep the code")


def resolve(project: Project, ref: str, kind: str | None = None) -> Node:
    """A node by id, by name, or by the end of its id (``agents.triage``)."""
    exact = project.node(ref)
    if exact is not None:
        return exact
    pool = [n for n in project.nodes if kind is None or n.kind == kind]
    for match in (lambda n: n.name == ref, lambda n: n.id.endswith("." + ref)):
        found = [n for n in pool if match(n)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            ids = "\n  ".join(n.id for n in found)
            raise EditError(f"`{ref}` is ambiguous; use one of these ids:\n  {ids}")
    what = f"{kind.replace('_', ' ')} " if kind else ""
    raise EditError(f"no {what}named `{ref}` (see `agentsdiagram scan -f json` for ids).")


def build_request(args: argparse.Namespace, project: Project) -> dict:
    agent = lambda ref: resolve(project, ref, "agent").id  # noqa: E731
    if args.op == "add-agent":
        framework = args.framework
        parent = agent(args.parent) if args.parent else None
        if parent:
            framework = framework or project.node(parent).framework  # type: ignore[union-attr]
        file = args.file or (project.node(parent).source.file if parent and project.node(parent).source else None)  # type: ignore[union-attr]
        if not file:
            raise EditError("Say where to write the agent with --file path/to/agents.py.")
        if framework is None:
            if len(project.frameworks) != 1:
                raise EditError("Say which framework with --framework smolagents|pydantic_ai.")
            framework = project.frameworks[0]
        return {
            "op": "add_agent",
            "framework": framework,
            "name": args.name,
            "file": file,
            "parent": parent,
            "model": args.model,
            "instructions": args.instructions,
            "description": args.description,
            "agent_class": args.agent_class,
        }
    if args.op == "add-tool":
        return {
            "op": "add_tool",
            "agent": agent(args.agent),
            "name": args.name,
            "description": args.description,
            "params": args.params,
            "returns": args.returns,
        }
    if args.op == "add-mcp":
        return {
            "op": "add_mcp",
            "agent": agent(args.agent),
            "url": args.url,
            "command": args.mcp_command,
            "name": args.name,
        }
    if args.op == "connect":
        return {
            "op": "connect",
            "source": agent(args.source),
            "target": agent(args.target),
            "description": args.description,
        }
    if args.op == "disconnect":
        source, target = resolve(project, args.source), resolve(project, args.target)
        edges = [e for e in project.edges if e.source == source.id and e.target == target.id]
        if not edges:
            hint = ""
            via = [
                project.node(e.target)
                for e in project.edges
                if e.source == source.id and any(d.source == e.target and d.target == target.id for d in project.edges)
            ]
            if via and via[0] is not None:
                hint = f" It goes through `{via[0].name}`: remove that instead."
            raise EditError(f"`{source.name}` is not directly connected to `{target.name}`.{hint}")
        return {"op": "disconnect", "edge": edges[0].id}
    if args.op == "remove":
        return {"op": "remove", "node": resolve(project, args.node).id}
    if args.op == "set-model":
        return {"op": "set_model", "agent": agent(args.agent), "model": args.model}
    if args.op == "set-instructions":
        return {"op": "set_instructions", "agent": agent(args.agent), "instructions": args.instructions}
    if args.op == "export-spec":
        return {"op": "export_spec", "agent": agent(args.agent), "path": args.path, "replace": not args.no_replace}
    raise EditError(f"unknown operation {args.op}")


def run(args: argparse.Namespace) -> int:
    from ..analyze import analyze

    path = Path(args.project)
    if not path.exists():
        print(f"agentsdiagram: {path} does not exist", file=sys.stderr)
        return 2
    try:
        project = analyze(path)
        request = TypeAdapter(EditRequest).validate_python(build_request(args, project))
        outcome = plan_edit(Path(project.root), request)
    except (EditError, ValidationError) as exc:
        message = str(exc)
        if args.json:
            print(EditResult(ok=False, message=message).model_dump_json(indent=2))
        else:
            print(f"agentsdiagram: {message}", file=sys.stderr)
        return 1
    if not args.dry_run:
        outcome.write()
    if args.json:
        result = EditResult(ok=True, message=outcome.message, files=outcome.files, focus=outcome.focus)
        data = result.model_dump(mode="json") | {"written": not args.dry_run}
        print(json.dumps(data, indent=2))
        return 0
    for change in outcome.changes:
        sys.stdout.write(unified_diff(change.rel, change.before, change.after))
    suffix = " (dry run: nothing written)" if args.dry_run else ""
    print(f"{outcome.message}{suffix}", file=sys.stderr)
    return 0
