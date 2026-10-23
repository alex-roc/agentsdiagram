"""Code the planner and editor write for smolagents (verified against smolagents 1.26.0).

- a new agent is a ``CodeAgent``/``ToolCallingAgent`` with ``tools=[]`` (required) and the model
  the file already uses; managed agents get ``name=`` and ``description=`` (smolagents requires both);
- a planned tool is a ``@tool`` function defined before the agent, with the type hints and the
  ``Args:`` docstring smolagents needs, whose body raises the planned marker;
- an MCP server is an ``MCPClient`` whose tools are spread into ``tools=[...]``;
- connecting two agents adds the second one to ``managed_agents=[...]`` of the first.
"""

from __future__ import annotations

import libcst as cst

from ...edit.codegen import annotation, command_parts, docstring, free, mcp_name, params_of, unique
from ...edit.doc import Doc, EditError, append_to_arg, element, find_arg, set_arg, with_marker
from ...edit.session import AgentSite, Session, humanize, identifier, py_string
from ...ir import AddAgent, AddMcp, AddTool, Connect, ExportSpec
from ...planned import COMMENT_MARKER, RAISE_MARKER

AGENT_CLASSES = {"CodeAgent", "ToolCallingAgent"}
DEFAULT_MODEL_CLASS = "InferenceClientModel"


class SmolagentsEditor:
    framework = "smolagents"
    agent_classes = AGENT_CLASSES | {"MultiStepAgent"}

    # ------------------------------------------------------------------ agents

    def add_agent(self, s: Session, req: AddAgent) -> str:
        manager = s.agent(req.parent, self.agent_classes) if req.parent else None
        if manager is not None:
            manager.require_top("add a managed agent")
            if manager.node.framework != "smolagents":
                raise EditError(f"`{manager.node.name}` is not a smolagents agent.")
        doc = s.doc(req.file, create=True)
        name = free(doc, identifier(req.name, "variable name"))
        cls = req.agent_class or ("ToolCallingAgent" if manager else "CodeAgent")
        before = manager.index if manager is not None and manager.doc is doc else None
        model = self._model_code(s, doc, req.model, before)
        args = ["tools=[]", f"model={model}", f"name={py_string(name)}"]
        description = req.description or (f"{humanize(name)} agent." if manager else None)
        if description:
            args.append(f"description={py_string(description)}")
        if req.instructions:
            args.append(f"instructions={py_string(req.instructions)}")
        code = f"{name} = {cls}(\n    " + ",\n    ".join(args) + ",\n)\n"
        stmts = with_marker(doc.parse_stmts(code), COMMENT_MARKER)
        doc.add_import("smolagents", cls)
        if before is not None:
            doc.insert_before(before, stmts)
        else:
            doc.append(stmts)
        s.focus = s.node_id("smolagents", "agent", doc, name)
        if manager is None:
            return f"Planned agent `{name}` in {doc.rel}."
        s.import_into(manager.doc, doc, name)
        manager.doc.update(manager.call, lambda c: append_to_arg(c, "managed_agents", element(cst.Name(name))))
        return f"Planned agent `{name}` in {doc.rel}, managed by `{manager.node.name}`."

    def _model_code(self, s: Session, doc: Doc, model_id: str | None, before: int | None) -> str:
        """The model expression of another agent of this file (``model=model``), else a new one."""
        existing = self._file_model(s, doc, before)
        if model_id is None and existing is not None:
            return existing[0]
        cls = existing[1] if existing is not None and existing[1] else DEFAULT_MODEL_CLASS
        if cls == DEFAULT_MODEL_CLASS:
            doc.add_import("smolagents", DEFAULT_MODEL_CLASS)
        return f"{cls}(model_id={py_string(model_id)})" if model_id else f"{cls}()"

    def _file_model(self, s: Session, doc: Doc, before: int | None) -> tuple[str, str | None] | None:
        """(code, model class) of the ``model=`` argument of a smolagents agent in ``doc``."""
        if doc.before is None:
            return None
        for n in s.project.nodes:
            if n.kind != "agent" or n.framework != "smolagents" or n.source is None or n.source.file != doc.rel:
                continue
            call = doc.at(n.source.range, cst.Call)
            if not isinstance(call, cst.Call):
                continue
            i = find_arg(call, "model", 1)
            if i is None:
                continue
            value = call.args[i].value
            if isinstance(value, cst.Name):
                definition = _module_value(doc, value.value)
                if definition is None:
                    continue
                index, expr = definition
                if before is not None and index >= before:
                    continue
                cls = doc.code(expr.func) if isinstance(expr, cst.Call) else None
                return value.value, cls
            if isinstance(value, cst.Call):
                return doc.code(value), doc.code(value.func)
        return None

    def connect(self, s: Session, source: AgentSite, target: AgentSite, req: Connect) -> str:
        source.require_top("connect it")
        t_index = target.require_top("connect it")
        assert target.var is not None
        if source.doc is target.doc and source.index is not None and t_index > source.index:
            raise EditError(
                f"`{target.node.name}` is defined after `{source.node.name}` in {source.doc.rel};"
                " move it above, then connect them."
            )
        s.import_into(source.doc, target.doc, target.var)
        var = target.var
        source.doc.update(source.call, lambda c: append_to_arg(c, "managed_agents", element(cst.Name(var))))
        call = target.call
        added = []
        if find_arg(call, "name") is None:
            added.append(("name", py_string(target.node.name if target.node.name.isidentifier() else var)))
        if find_arg(call, "description") is None:
            added.append(("description", py_string(req.description or f"{humanize(target.node.name)} agent.")))
        for key, code in added:
            expr = target.doc.parse_expr(code)
            target.doc.update(call, lambda c, k=key, e=expr: set_arg(c, k, e))
        s.focus = source.node.id
        note = " Added its name and description, which managed agents need." if added else ""
        return f"`{source.node.name}` now manages `{target.node.name}`.{note}"

    def set_model(self, s: Session, site: AgentSite, model: str) -> str:
        doc, call = site.doc, site.call
        i = find_arg(call, "model", 1)
        value = call.args[i].value if i is not None else None
        literal = doc.parse_expr(py_string(model))
        if isinstance(value, cst.Call):
            idx = i

            def change(c: cst.Call) -> cst.Call:
                args = list(c.args)
                inner = args[idx].value  # type: ignore[index]
                if isinstance(inner, cst.Call):
                    args[idx] = args[idx].with_changes(value=set_arg(inner, "model_id", literal, 0))  # type: ignore[index]
                return c.with_changes(args=args)

            doc.update(call, change)
        else:
            definition = _module_value(doc, value.value) if isinstance(value, cst.Name) else None
            cls = (
                doc.code(definition[1].func)
                if definition is not None and isinstance(definition[1], cst.Call)
                else DEFAULT_MODEL_CLASS
            )
            if cls == DEFAULT_MODEL_CLASS:
                doc.add_import("smolagents", DEFAULT_MODEL_CLASS)
            new = doc.parse_expr(f"{cls}(model_id={py_string(model)})")
            doc.update(call, lambda c: set_arg(c, "model", new, 1))
        s.focus = site.node.id
        return f"`{site.node.name}` now uses `{model}`."

    def export_spec(self, s: Session, site: AgentSite, req: ExportSpec) -> str:
        raise EditError("Agent Specs are a PydanticAI feature; smolagents agents are saved with `agent.save()`.")

    # ------------------------------------------------------------------ tools and MCP

    def add_tool(self, s: Session, site: AgentSite, req: AddTool) -> str:
        index = site.require_top("add a tool")
        doc = site.doc
        name = free(doc, identifier(req.name, "function name"))
        params, names, untyped = params_of(req.params)
        if untyped:
            raise EditError(f"smolagents tools need a type hint on every parameter ({', '.join(untyped)}).")
        returns = annotation(req.returns)
        summary = docstring(req.description or f"{humanize(name)}.")
        args = "".join(f"\n        {p}: {humanize(p)}." for p in names)
        body = f"{summary}\n\n    Args:{args}\n    " if names else summary
        code = f'@tool\ndef {name}({params}) -> {returns}:\n    """{body}"""\n    {RAISE_MARKER}\n'
        doc.insert_before(index, doc.parse_stmts(code))
        doc.add_import("smolagents", "tool")
        doc.update(site.call, lambda c: append_to_arg(c, "tools", element(cst.Name(name)), 0))
        s.focus = s.node_id("smolagents", "tool", doc, name)
        return f"Planned tool `{name}` for `{site.node.name}` in {doc.rel}."

    def add_mcp(self, s: Session, site: AgentSite, req: AddMcp) -> str:
        index = site.require_top("add an MCP server")
        doc = site.doc
        if req.name:
            name = free(doc, identifier(req.name, "variable name"))
        else:
            name = unique(doc, mcp_name(req.url, req.command))
        if req.url:
            params = f'{{"url": {py_string(req.url)}, "transport": "streamable-http"}}'
        else:
            command, args = command_parts(req.command or "")
            params = f"StdioServerParameters(command={command}, args={args})"
            doc.add_import("mcp", "StdioServerParameters")
        code = f"{name} = MCPClient({params}, structured_output=True)\n"
        doc.insert_before(index, doc.parse_stmts(code))
        doc.add_import("smolagents", "MCPClient")
        spread = cst.StarredElement(value=doc.parse_expr(f"{name}.get_tools()"))
        doc.update(site.call, lambda c: append_to_arg(c, "tools", spread, 0))
        s.focus = site.node.id
        return (
            f"Connected `{site.node.name}` to the MCP server `{name}`."
            f" Call `{name}.disconnect()` when your program is done with it."
        )


def _module_value(doc: Doc, name: str) -> tuple[int, cst.BaseExpression] | None:
    """``name = <value>`` at module level: (statement index, value)."""
    for i, stmt in enumerate(doc.tree.body):
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if (
                isinstance(small, cst.Assign)
                and len(small.targets) == 1
                and isinstance(small.targets[0].target, cst.Name)
                and small.targets[0].target.value == name
            ):
                return i, small.value
    return None
