"""smolagents (1.x) adapter: CodeAgent/ToolCallingAgent, tools, managed agents and MCP."""

from __future__ import annotations

from collections import Counter

import libcst as cst

from ...facts import Def, Facts, key_of
from ...ir import Diagnostic, NodeAttrs, Project
from ...project import Module
from ..base import (
    arg,
    bool_value,
    call_symbol,
    decorator_parts,
    describe_model,
    docstring,
    elements,
    shorten,
    signature,
    string_value,
    symbol,
    value_of,
)
from . import symbols as S


class SmolagentsAdapter:
    framework = "smolagents"
    markers = (b"smolagents",)
    run_methods = S.RUN_METHODS

    def extract(self, module: Module, facts: Facts) -> None:
        calls = module.calls
        for call in reversed(calls):
            self._register_call(module, facts, call)
        for call in calls:
            key = facts.call_keys.get(call)
            if key and call_symbol(module, call, S.ROOTS) in S.AGENTS:
                agent = facts.defs[key]
                self._relate_many(module, facts, agent.key, "uses", arg(call, "tools", 0))
                self._relate_many(module, facts, agent.key, "manages", arg(call, "managed_agents"))
        self._functions_and_classes(module, facts)
        if any(d.framework == "smolagents" for d in facts.defs.values()):
            facts.frameworks.add("smolagents")

    # ------------------------------------------------------------------ calls

    def _key(self, module: Module, facts: Facts, call: cst.Call, kind: str):
        bound = module.binding_name_for(call)
        if bound:
            qualname, name_node = bound
            return key_of(module.name, qualname), qualname.rsplit(".", 1)[-1], name_node
        return facts.anonymous_key(module.scope_prefix(call), kind), None, None

    def _add(self, module, facts, call, kind, name, short, *, status="resolved", attrs=None) -> Def:
        key, var, name_node = self._key(module, facts, call, short)
        return facts.add(
            Def(
                key=key,
                kind=kind,
                name=name or var or short,
                module=module,
                node=call,
                name_node=name_node,
                framework="smolagents",
                status=status,  # type: ignore[arg-type]
                attrs=attrs or NodeAttrs(),
            ),
            call,
        )

    def _register_call(self, module: Module, facts: Facts, call: cst.Call) -> None:
        sym = call_symbol(module, call, S.ROOTS)
        if sym in S.AGENTS:
            self._agent(module, facts, call, sym)
        elif sym in S.DEFAULT_TOOLS:
            short = sym.split(".", 1)[1]
            self._add(
                module,
                facts,
                call,
                "tool",
                S.DEFAULT_TOOLS[sym],
                short,
                attrs=NodeAttrs(extra={"class": short}, badges=["default"]),
            )
        elif sym in S.MCP_CLIENT:
            url, command = _server_params(module, arg(call, "server_parameters", 0))
            self._add(
                module,
                facts,
                call,
                "mcp_server",
                _mcp_name(url, command),
                "MCPClient",
                attrs=NodeAttrs(url=url, command=command, extra={"class": "MCPClient"}),
            )
        elif sym in S.EXTERNAL_FUNCTIONS:
            repo = string_value(value_of(module, arg(call, "repo_id", 0)))
            self._add(
                module,
                facts,
                call,
                "external_tool_source",
                repo or "load_tool",
                "load_tool",
                status="partial",
                attrs=NodeAttrs(extra={"source": "hub", "repo_id": repo}),
            )
        elif isinstance(call.func, cst.Attribute):
            owner = symbol(module, call.func.value, S.ROOTS)
            method = call.func.attr.value
            if owner in S.COLLECTIONS and method == "from_mcp":
                url, command = _server_params(module, arg(call, "server_parameters", 0))
                self._add(
                    module,
                    facts,
                    call,
                    "mcp_server",
                    _mcp_name(url, command),
                    "ToolCollection",
                    attrs=NodeAttrs(url=url, command=command, extra={"class": "ToolCollection.from_mcp"}),
                )
            elif (owner in S.COLLECTIONS or owner in S.TOOL_BASES) and method in S.EXTERNAL_METHODS | {"from_hub"}:
                first = arg(call, "repo_id", 0) or arg(call, "collection_slug", 0) or arg(call, "space_id", 0)
                label = string_value(value_of(module, first)) or f"{owner.split('.', 1)[1]}.{method}"  # type: ignore[union-attr]
                kind = (
                    "tool"
                    if method in ("from_space", "from_langchain", "from_gradio", "from_code")
                    else "external_tool_source"
                )
                name = string_value(arg(call, "name", 1)) if method == "from_space" else None
                self._add(
                    module,
                    facts,
                    call,
                    kind,
                    name or label,
                    method,
                    status="partial",
                    attrs=NodeAttrs(
                        description=shorten(string_value(arg(call, "description", 2))),
                        extra={"source": method, "ref": label},
                    ),
                )

    def _agent(self, module: Module, facts: Facts, call: cst.Call, sym: str) -> None:
        cls = sym.split(".", 1)[1]
        model = describe_model(module, arg(call, "model", 1))
        for old, new in S.MODEL_ALIASES.items():
            if model and model.startswith(old + "("):
                model = new + model[len(old) :]
        extra = {}
        for k in (
            "planning_interval",
            "max_steps",
            "executor_type",
            "additional_authorized_imports",
            "max_tool_threads",
        ):
            v = arg(call, k)
            if v is not None:
                literal = string_value(v)
                extra[k] = literal if literal is not None else module.code(v)
        extra["explicit_name"] = arg(call, "name") is not None
        if arg(call, "instructions") is not None and string_value(arg(call, "instructions")) is None:
            extra["instructions_code"] = True  # not a literal: edit it in code
        attrs = NodeAttrs(
            agent_class=cls,
            model=model,
            instructions=shorten(string_value(value_of(module, arg(call, "instructions")))),
            description=shorten(string_value(value_of(module, arg(call, "description")))),
            extra=extra,
        )
        status = "partial" if module.enclosing_function(call) else "resolved"
        d = self._add(module, facts, call, "agent", string_value(arg(call, "name")), cls, status=status, attrs=attrs)
        executor = extra.get("executor_type")
        if executor in S.REMOVED_EXECUTOR_TYPES:
            facts.diag(
                "AD204", "error", f"executor_type={executor!r} was {S.REMOVED_EXECUTOR_TYPES[executor]}.", call, None
            )
        if bool_value(arg(call, "add_base_tools")):
            d.attrs.badges.append("add_base_tools")
            for tool_name, tool_cls in S.BASE_TOOLS.items():
                if tool_name == "python_interpreter" and cls != "ToolCallingAgent":
                    continue
                key = key_of(module.name, f"{d.qualname}.<base>.{tool_name}")
                facts.add(
                    Def(
                        key=key,
                        kind="tool",
                        name=tool_name,
                        module=module,
                        node=call,
                        framework="smolagents",
                        attrs=NodeAttrs(extra={"class": tool_cls}, badges=["base"]),
                        show=False,
                    )
                )
                facts.edge(d.key, "uses", module, key, ref_node=arg(call, "add_base_tools"))

    def _relate_many(self, module, facts, source, kind, expr) -> None:
        if expr is None:
            return
        items = elements(expr)
        for el in items if items is not None else [expr]:
            facts.edge(source, kind, module, el, ref_node=el)

    # ------------------------------------------------------------------ @tool and Tool subclasses

    def _functions_and_classes(self, module: Module, facts: Facts) -> None:
        for binding in list(module.bindings.values()):
            node = binding.node
            if binding.kind == "function" and isinstance(node, cst.FunctionDef):
                if any(symbol(module, decorator_parts(d)[0], S.ROOTS) in S.TOOL_DECORATOR for d in node.decorators):
                    self._tool_function(module, facts, binding.qualname, node)
            elif binding.kind == "class" and isinstance(node, cst.ClassDef):
                bases = [b.value for b in node.bases]
                if any(symbol(module, b, S.ROOTS) in S.TOOL_BASES for b in bases):
                    self._tool_class(module, facts, binding.qualname, node)

    def _tool_function(self, module: Module, facts: Facts, qualname: str, fn: cst.FunctionDef) -> None:
        doc = docstring(fn)
        d = facts.add(
            Def(
                key=key_of(module.name, qualname),
                kind="tool",
                name=fn.name.value,
                module=module,
                node=fn,
                name_node=fn.name,
                framework="smolagents",
                attrs=NodeAttrs(docstring=shorten(doc, 400), signature=signature(module, fn), badges=["@tool"]),
                fn=fn,
            )
        )
        params = [p for p in fn.params.params if p.name.value not in ("self", "cls")]
        missing = [p.name.value for p in params if p.annotation is None]
        if missing or (params and fn.returns is None):
            what = f"parameters {', '.join(missing)}" if missing else "return type"
            facts.diag("AD203", "warning", f"@tool `{d.name}` needs type hints ({what} missing).", fn.name)
        if params and (doc is None or "Args:" not in doc):
            facts.diag("AD203", "warning", f"@tool `{d.name}` needs a docstring with an `Args:` section.", fn.name)

    def _tool_class(self, module: Module, facts: Facts, qualname: str, cls: cst.ClassDef) -> None:
        values: dict[str, cst.BaseExpression] = {}
        for stmt in cls.body.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for small in stmt.body:
                    if isinstance(small, cst.Assign) and isinstance(small.targets[0].target, cst.Name):
                        values[small.targets[0].target.value] = small.value
                    elif isinstance(small, cst.AnnAssign) and isinstance(small.target, cst.Name) and small.value:
                        values[small.target.value] = small.value
        forward = next((s for s in cls.body.body if isinstance(s, cst.FunctionDef) and s.name.value == "forward"), None)
        inputs = values.get("inputs")
        facts.add(
            Def(
                key=key_of(module.name, qualname),
                kind="tool",
                name=string_value(values.get("name")) or cls.name.value,
                module=module,
                node=cls,
                name_node=cls.name,
                framework="smolagents",
                attrs=NodeAttrs(
                    description=shorten(string_value(values.get("description"))),
                    docstring=shorten(docstring(cls), 400),
                    signature=signature(module, forward) if forward else None,
                    extra={
                        "class": cls.name.value,
                        "inputs": shorten(module.code(inputs), 400) if inputs is not None else None,
                        "output_type": string_value(values.get("output_type")),
                    },
                    badges=["Tool subclass"],
                ),
                fn=forward,
            )
        )

    # ------------------------------------------------------------------ whole-graph checks

    def check(self, project: Project) -> None:
        nodes = {n.id: n for n in project.nodes}
        for agent in (n for n in project.nodes if n.framework == "smolagents" and n.kind == "agent"):
            names: list[str] = []
            for e in project.edges:
                if e.source != agent.id:
                    continue
                target = nodes.get(e.target)
                if target is None:
                    continue
                if e.kind == "manages":
                    if target.kind == "agent" and (not target.attrs.description or _unnamed(target)):
                        project.diagnostics.append(
                            Diagnostic(
                                code="AD201",
                                severity="error",
                                message=f"Managed agent `{target.name}` needs both `name=` and `description=`.",
                                ref=e.ref,
                                node_id=target.id,
                            )
                        )
                    names.append(target.name)
                elif e.kind == "uses" and target.kind == "tool":
                    names.append(target.name)
            for name, count in Counter(names).items():
                if count > 1:
                    project.diagnostics.append(
                        Diagnostic(
                            code="AD202",
                            severity="warning",
                            message=f"Agent `{agent.name}` has {count} tools/agents named `{name}`.",
                            ref=agent.source,
                            node_id=agent.id,
                        )
                    )


def _unnamed(node) -> bool:
    return node.attrs.extra.get("explicit_name") is False


def _server_params(module: Module, expr: cst.BaseExpression | None) -> tuple[str | None, str | None]:
    expr = value_of(module, expr)
    if isinstance(expr, cst.Dict):
        for el in expr.elements:
            if isinstance(el, cst.DictElement) and string_value(el.key) == "url":
                return string_value(value_of(module, el.value)), None
        return None, None
    if isinstance(expr, cst.Call):
        command = arg(expr, "command", 0)
        args = elements(arg(expr, "args", 1))
        if command is not None:
            parts = [string_value(a) or module.code(a) for a in args or []]
            head = string_value(value_of(module, command)) or module.code(command)
            return None, shorten(" ".join([head, *parts]), 160)
    return None, None


def _mcp_name(url: str | None, command: str | None) -> str:
    if url:
        return "MCP " + url.split("://", 1)[-1].split("/", 1)[0]
    if command:
        return "MCP " + command.split()[0].rsplit("/", 1)[-1]
    return "MCP"
