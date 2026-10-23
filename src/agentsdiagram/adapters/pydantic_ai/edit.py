"""Code the planner and editor write for PydanticAI (verified against pydantic-ai 2.59.0).

- a new agent is ``Agent("<model>", name=..., instructions=...)``;
- a planned tool is an ``@agent.tool_plain`` function after the agent whose body raises the
  planned marker;
- an MCP server is an ``MCPToolset`` (URL, or ``StdioTransport`` for a command) in ``toolsets=``;
- connecting two agents writes a delegation tool: ``@a.tool`` that runs ``b`` with the same
  usage (and the same deps when both agents have the same ``deps_type``);
- an Agent Spec export moves the literal settings to YAML and loads it with ``Agent.from_file``.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import libcst as cst
import yaml

from ...edit.codegen import annotation, command_parts, docstring, free, mcp_name, params_of, tools_anchor, unique
from ...edit.doc import Doc, EditError, append_to_arg, element, find_arg, kwarg, prepend_item, remove_items, with_marker
from ...edit.session import AgentSite, Session, humanize, identifier, py_string
from ...ir import AddAgent, AddMcp, AddTool, Connect, ExportSpec
from ...planned import COMMENT_MARKER, RAISE_MARKER

DEFAULT_MODEL = "openai:gpt-5-mini"
SPEC_FIELDS = ("name", "description", "instructions")


class PydanticAIEditor:
    framework = "pydantic_ai"
    agent_classes = {"Agent"}

    # ------------------------------------------------------------------ agents

    def add_agent(self, s: Session, req: AddAgent) -> str:
        parent = s.agent(req.parent, self.agent_classes) if req.parent else None
        if parent is not None:
            parent.require_top("add a delegation tool")
        doc = s.doc(req.file, create=True)
        name = free(doc, identifier(req.name, "variable name"))
        args = [py_string(req.model or self._default_model(s, doc)), f"name={py_string(name)}"]
        if req.description:
            args.append(f"description={py_string(req.description)}")
        if req.instructions:
            args.append(f"instructions={py_string(req.instructions)}")
        code = f"{name} = Agent(\n    " + ",\n    ".join(args) + ",\n)\n"
        stmts = with_marker(doc.parse_stmts(code), COMMENT_MARKER)
        doc.add_import("pydantic_ai", "Agent")
        if parent is not None and parent.doc is doc:
            doc.insert_before(parent.index, stmts)  # type: ignore[arg-type]
        else:
            doc.append(stmts)
        s.focus = s.node_id("pydantic_ai", "agent", doc, name)
        if parent is None:
            return f"Planned agent `{name}` in {doc.rel}."
        tool = self._delegation(s, parent, doc, name, req.description, None)
        return f"Planned agent `{name}` in {doc.rel}; `{parent.node.name}` hands work to it with `{tool}`."

    def _default_model(self, s: Session, doc: Doc) -> str:
        """The model of another agent, preferring this file; else a sensible default."""
        agents = [n for n in s.project.nodes if n.kind == "agent" and n.framework == "pydantic_ai"]
        agents.sort(key=lambda n: n.source is None or n.source.file != doc.rel)
        for n in agents:
            model = n.attrs.model
            if model and ":" in model and "(" not in model:
                return model
        return DEFAULT_MODEL

    def connect(self, s: Session, source: AgentSite, target: AgentSite, req: Connect) -> str:
        source.require_top("connect it")
        target.require_top("connect it")
        assert target.var is not None
        tool = self._delegation(s, source, target.doc, target.var, target.node.attrs.description, target.node)
        s.focus = source.node.id
        return f"`{source.node.name}` now hands work to `{target.node.name}` with the tool `{tool}`."

    def _delegation(
        self, s: Session, source: AgentSite, target_doc: Doc, target_var: str, description: str | None, target
    ) -> str:
        """``@source.tool async def ask_<target>(ctx, task) -> str`` that runs the target agent."""
        doc = source.doc
        assert source.var is not None and source.index is not None
        fname = f"ask_{target_var}"
        if fname in doc.top_names():
            fname = unique(doc, f"{source.var}_asks_{target_var}")
        deps = source.node.attrs.deps_type
        same_deps = deps is not None and target is not None and target.attrs.deps_type == deps
        ctx = f"RunContext[{deps}]" if deps else "RunContext[None]"
        summary = docstring(description or f"Hand a task to the {humanize(target_var).lower()} agent.")
        deps_arg = "deps=ctx.deps, " if same_deps else ""
        code = (
            f"@{source.var}.tool\n"
            f"async def {fname}(ctx: {ctx}, task: str) -> str:\n"
            f'    """{summary}"""\n'
            f"    result = await {target_var}.run(task, {deps_arg}usage=ctx.usage)\n"
            f"    return result.output\n"
        )
        doc.add_import("pydantic_ai", "RunContext")
        s.import_into(doc, target_doc, target_var)
        doc.insert_after(tools_anchor(doc, source.index, source.var), doc.parse_stmts(code))
        return fname

    def set_model(self, s: Session, site: AgentSite, model: str) -> str:
        literal = site.doc.parse_expr(py_string(model))

        def change(c: cst.Call) -> cst.Call:
            i = find_arg(c, "model", 0)
            if i is None:
                return c.with_changes(args=prepend_item(c.args, cst.Arg(value=literal)))
            args = list(c.args)
            args[i] = args[i].with_changes(value=literal)
            return c.with_changes(args=args)

        site.doc.update(site.call, change)
        s.focus = site.node.id
        return f"`{site.node.name}` now uses `{model}`."

    # ------------------------------------------------------------------ tools and MCP

    def add_tool(self, s: Session, site: AgentSite, req: AddTool) -> str:
        index = site.require_top("add a tool")
        doc, var = site.doc, site.var
        name = free(doc, identifier(req.name, "function name"))
        params, _, _ = params_of(req.params)
        returns = annotation(req.returns)
        summary = docstring(req.description or f"{humanize(name)}.")
        code = f'@{var}.tool_plain\ndef {name}({params}) -> {returns}:\n    """{summary}"""\n    {RAISE_MARKER}\n'
        doc.insert_after(tools_anchor(doc, index, var), doc.parse_stmts(code))  # type: ignore[arg-type]
        s.focus = s.node_id("pydantic_ai", "tool", doc, name)
        return f"Planned tool `{name}` for `{site.node.name}` in {doc.rel}."

    def add_mcp(self, s: Session, site: AgentSite, req: AddMcp) -> str:
        index = site.require_top("add an MCP server")
        doc = site.doc
        if req.name:
            name = free(doc, identifier(req.name, "variable name"))
        else:
            name = unique(doc, mcp_name(req.url, req.command))
        if req.url:
            client = py_string(req.url)
        else:
            command, args = command_parts(req.command or "")
            client = f"StdioTransport(command={command}, args={args})"
            doc.add_import("pydantic_ai.mcp", "StdioTransport")
        doc.insert_before(index, doc.parse_stmts(f"{name} = MCPToolset({client}, id={py_string(name)})\n"))
        doc.add_import("pydantic_ai.mcp", "MCPToolset")
        doc.update(site.call, lambda c: append_to_arg(c, "toolsets", element(cst.Name(name))))
        s.focus = site.node.id
        return f"Connected `{site.node.name}` to the MCP server `{name}`."

    # ------------------------------------------------------------------ Agent Spec

    def export_spec(self, s: Session, site: AgentSite, req: ExportSpec) -> str:
        doc, call = site.doc, site.call
        spec: dict[str, Any] = {}
        keep: list[cst.Arg] = []
        capabilities: list[Any] = []
        for i, a in enumerate(call.args):
            key = a.keyword.value if a.keyword else ("model" if i == 0 and not a.star else None)
            value = _literal(doc, a.value)
            if key == "model" and isinstance(value, str):
                spec["model"] = value
            elif key in SPEC_FIELDS and isinstance(value, str):
                spec[key] = value
            elif key == "capabilities" and isinstance(a.value, cst.List):
                moved = set()
                for j, el in enumerate(a.value.elements):
                    cap = _capability(doc, el.value) if isinstance(el, cst.Element) else None
                    if cap is not None:
                        capabilities.append(cap)
                        moved.add(j)
                rest = remove_items(a.value.elements, moved)
                if rest:
                    keep.append(a.with_changes(value=a.value.with_changes(elements=rest)))
            elif a.keyword is None and not a.star and i == 0:
                keep.append(kwarg("model", a.value))  # from_file takes the path first
            else:
                keep.append(a)
        if not spec and not capabilities:
            raise EditError(f"`{site.node.name}` has no literal settings to move to an Agent Spec.")
        spec.setdefault("name", site.node.name)
        if capabilities:
            spec["capabilities"] = capabilities
        rel = req.path or (Path(doc.rel).parent / f"{site.node.name}.agent.yaml").as_posix()
        if not rel.endswith((".yaml", ".yml", ".json")):
            raise EditError("An Agent Spec file must end in .yaml, .yml or .json.")
        s.extra_files[rel] = _dump(spec, rel)
        s.focus = site.node.id
        if not req.replace:
            return f"Wrote the Agent Spec {rel}."
        spec_path = s.root / rel
        relative = Path(os.path.relpath(spec_path, doc.path.parent)).as_posix()
        path_code = f"Path(__file__).parent / {py_string(relative)}"
        new_call = doc.parse_expr(f"Agent.from_file({path_code})")
        assert isinstance(new_call, cst.Call)
        items = [cst.Arg(value=new_call.args[0].value), *keep]

        def change(c: cst.Call) -> cst.Call:
            first, last = c.args[0], c.args[-1]
            space = cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
            sep = first.comma if isinstance(first.comma, cst.Comma) else space
            args = [a.with_changes(comma=sep, whitespace_after_arg=cst.SimpleWhitespace("")) for a in items[:-1]]
            args.append(items[-1].with_changes(comma=last.comma, whitespace_after_arg=last.whitespace_after_arg))
            return c.with_changes(func=new_call.func, args=args)

        doc.update(call, change)
        doc.add_import("pathlib", "Path")
        return f"Moved the settings of `{site.node.name}` to {rel}; the code now loads it with `Agent.from_file`."


def _literal(doc: Doc, expr: cst.BaseExpression) -> Any:
    """A Python literal (also through a module-level constant), else ``None``."""
    if isinstance(expr, cst.Name) and expr.value not in ("True", "False", "None"):
        for stmt in doc.tree.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for small in stmt.body:
                    if (
                        isinstance(small, cst.Assign)
                        and len(small.targets) == 1
                        and isinstance(small.targets[0].target, cst.Name)
                        and small.targets[0].target.value == expr.value
                    ):
                        return _literal(doc, small.value)
        return None
    try:
        return ast.literal_eval(doc.code(expr).strip())
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None


def _capability(doc: Doc, expr: cst.BaseExpression) -> Any:
    """``Thinking(effort="high")`` -> ``{"Thinking": {"effort": "high"}}``; ``WebSearch()`` -> ``"WebSearch"``."""
    if not isinstance(expr, cst.Call) or not isinstance(expr.func, cst.Name | cst.Attribute):
        return None
    name = doc.code(expr.func).rsplit(".", 1)[-1]
    positional = [a for a in expr.args if a.keyword is None]
    if any(a.star for a in expr.args):
        return None
    kwargs = {}
    for a in expr.args:
        if a.keyword is not None:
            value = _literal(doc, a.value)
            if value is None:
                return None
            kwargs[a.keyword.value] = value
    if positional:
        if kwargs or len(positional) > 1:
            return None
        value = _literal(doc, positional[0].value)
        return None if value is None else {name: value}
    return {name: kwargs} if kwargs else name


def _dump(spec: dict[str, Any], rel: str) -> str:
    if rel.endswith(".json"):
        import json

        return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
    return yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100)
