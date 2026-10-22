"""PydanticAI (2.x) adapter: agents, tools, toolsets, MCP, capabilities and delegation."""

from __future__ import annotations

import json
from pathlib import Path

import libcst as cst
import yaml

from ...facts import Def, Facts, key_of
from ...ir import NodeAttrs, Project
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
    unwrap_chain,
    value_of,
)
from . import graph
from . import symbols as S


class PydanticAIAdapter:
    framework = "pydantic_ai"
    markers = (b"pydantic_ai", b"pydantic_graph")
    run_methods = S.RUN_METHODS

    def extract(self, module: Module, facts: Facts) -> None:
        calls = module.calls
        # Post-order: inner calls (WebSearchTool()) are registered before outer ones (NativeTool(...)).
        for call in reversed(calls):
            self._register_call(module, facts, call)
        for call in calls:
            key = facts.call_keys.get(call)
            if key and facts.defs[key].kind == "agent" and call_symbol(module, call, S.ROOTS) in S.AGENT:
                self._agent_relations(module, facts, call, facts.defs[key])
        self._decorators(module, facts)
        self._add_function_calls(module, facts)
        graph.extract(module, facts)
        if facts.defs:
            facts.frameworks.add("pydantic_ai")

    def check(self, project: Project) -> None:
        return None

    # ------------------------------------------------------------------ registration

    def _key(
        self, module: Module, facts: Facts, call: cst.Call, kind: str
    ) -> tuple[str, str | None, cst.CSTNode | None]:
        bound = module.binding_name_for(call)
        if bound:
            qualname, name_node = bound
            return key_of(module.name, qualname), qualname.rsplit(".", 1)[-1], name_node
        return facts.anonymous_key(module.scope_prefix(call), kind), None, None

    def _register_call(self, module: Module, facts: Facts, call: cst.Call) -> None:
        sym = call_symbol(module, call, S.ROOTS)
        if sym is None:
            return
        short = sym.split(".", 1)[1]

        def add(kind: str, name: str | None, *, status="resolved", attrs: NodeAttrs | None = None, **kw) -> Def:
            key, var, name_node = self._key(module, facts, call, short)
            return facts.add(
                Def(
                    key=key,
                    kind=kind,
                    name=name or var or short,
                    module=module,
                    node=call,
                    name_node=name_node,
                    framework="pydantic_ai",
                    status=status,  # type: ignore[arg-type]
                    attrs=attrs or NodeAttrs(),
                    **kw,
                ),
                call,
            )

        if sym in S.AGENT:
            self._agent(module, facts, call, add)
        elif sym == "pydantic_ai.from_file" or sym == "pydantic_ai.from_spec":
            self._agent_spec(module, facts, call, add)
        elif sym in S.TOOL or sym == "pydantic_ai.from_schema":
            fn = arg(call, "function", 0)
            name = string_value(arg(call, "name"))
            if name is None and isinstance(fn, cst.Name | cst.Attribute):
                name = module.code(fn).rsplit(".", 1)[-1]
            attrs = NodeAttrs(description=shorten(string_value(arg(call, "description"))))
            if bool_value(arg(call, "requires_approval")):
                attrs.badges.append("requires_approval")
            takes_ctx = bool_value(arg(call, "takes_ctx"))
            attrs.takes_ctx = takes_ctx
            add("tool", name, attrs=attrs, impl=fn)
        elif sym in S.FUNCTION_TOOLSET:
            d = add("toolset", string_value(arg(call, "id")), attrs=NodeAttrs(extra={"class": short}))
            tools = arg(call, "tools", 0)
            self._relate_many(module, facts, d.key, "provides", tools)
        elif sym in S.WRAPPER_TOOLSETS or sym in S.COMBINED_TOOLSET:
            d = add("toolset", None, attrs=NodeAttrs(extra={"class": short}))
            inner = arg(call, "toolsets", 0) if sym in S.COMBINED_TOOLSET else arg(call, "wrapped", 0)
            self._relate_many(module, facts, d.key, "wraps", inner)
        elif sym in S.EXTERNAL_TOOLSET:
            add("toolset", string_value(arg(call, "id")), status="partial", attrs=NodeAttrs(extra={"class": short}))
        elif sym in S.MCP_TOOLSET or sym in S.MCP_V1:
            if sym in S.MCP_V1:
                facts.diag("AD101", "warning", f"`{short}` is PydanticAI v1 API; use `MCPToolset` in v2.", call)
            url, command = self._mcp_target(module, arg(call, "client", 0) if sym in S.MCP_TOOLSET else call)
            name = string_value(arg(call, "id")) or string_value(arg(call, "tool_prefix"))
            add("mcp_server", name or _mcp_name(url, command), attrs=NodeAttrs(url=url, command=command))
        elif sym in S.MCP_CONFIG_LOADERS or sym in S.MCP_CONFIG_LOADERS_V1:
            self._mcp_config(module, facts, call, add, v1=sym in S.MCP_CONFIG_LOADERS_V1)
        elif sym in S.NATIVE_TOOLS or sym in S.NATIVE_TOOLS_V1:
            add("native_tool", short, attrs=NodeAttrs(badges=["native"]))
        elif sym in S.CAP_NATIVE_TOOL:
            inner = arg(call, "tool", 0)
            inner_key = facts.call_keys.get(inner) if inner is not None else None
            if inner_key:
                facts.call_keys[call] = inner_key
            else:
                add("native_tool", module.code(inner) if inner else "NativeTool", status="partial")
        elif sym in S.CAP_ADAPTIVE_TOOLS:
            add("native_tool", short, attrs=NodeAttrs(badges=["native-or-local"]))
        elif sym in S.CAP_MCP:
            url = string_value(value_of(module, arg(call, "url", 0)))
            add(
                "mcp_server",
                string_value(arg(call, "id")) or _mcp_name(url, None),
                attrs=NodeAttrs(url=url, badges=["capability"]),
            )
        elif sym in S.CAP_CAPABILITY:
            d = add(
                "capability",
                string_value(arg(call, "id")),
                attrs=NodeAttrs(
                    description=shorten(string_value(arg(call, "description"))),
                    instructions=shorten(string_value(value_of(module, arg(call, "instructions")))),
                ),
            )
            self._relate_many(module, facts, d.key, "provides", arg(call, "tools"))
            self._relate_many(module, facts, d.key, "provides", arg(call, "toolsets"))
        elif sym in S.CAP_SUBAGENTS or sym in S.CAP_DYNAMIC_WORKFLOW:
            dynamic = sym in S.CAP_DYNAMIC_WORKFLOW
            d = add(
                "capability",
                short,
                status="dynamic" if dynamic else "resolved",
                attrs=NodeAttrs(extra={"tool_name": string_value(arg(call, "tool_name")) or "delegate_task"}),
            )
            agents = elements(arg(call, "agents", 0))
            if agents is None:
                self._relate_many(module, facts, d.key, "delegates_to", arg(call, "agents", 0))
                return
            for el in agents:
                label = None
                target = el
                if isinstance(el, cst.Call) and call_symbol(module, el, S.ROOTS) in S.CAP_SUBAGENT:
                    target = arg(el, "agent", 0) or el
                    label = string_value(arg(el, "name", 1))
                facts.edge(d.key, "delegates_to", module, target, ref_node=el, label=label)

    def _agent(self, module: Module, facts: Facts, call: cst.Call, add) -> None:
        attrs = NodeAttrs(agent_class="Agent")
        attrs.model = describe_model(module, arg(call, "model", 0))
        instructions = arg(call, "instructions") or arg(call, "system_prompt")
        text = string_value(value_of(module, instructions))
        attrs.instructions = shorten(
            text if text is not None else (module.code(instructions) if instructions else None)
        )
        attrs.description = shorten(string_value(arg(call, "description")))
        for name, field_name in (("output_type", "output_type"), ("deps_type", "deps_type")):
            value = arg(call, name)
            if value is not None:
                setattr(attrs, field_name, shorten(module.code(value), 120))
        for kwarg, replacement in S.AGENT_KWARGS_V1.items():
            if arg(call, kwarg) is not None:
                facts.diag("AD101", "warning", f"`{kwarg}=` is PydanticAI v1 API; in v2 use {replacement}.", call)
        fn = module.enclosing_function(call)
        status = "partial" if fn else "resolved"
        fallback = f"{fn.name.value}()" if fn and not module.binding_name_for(call) else None
        d = add("agent", string_value(arg(call, "name")) or fallback, status=status, attrs=attrs)
        if status == "partial":
            facts.diag(
                "AD301",
                "info",
                f"Agent `{d.name}` is created inside a function; its arguments may vary at runtime.",
                call,
                None,
            )

    def _agent_relations(self, module: Module, facts: Facts, call: cst.Call, agent: Def) -> None:
        self._relate_many(module, facts, agent.key, "uses", arg(call, "tools"))
        self._relate_many(module, facts, agent.key, "uses", arg(call, "toolsets"))
        self._relate_many(module, facts, agent.key, "uses", arg(call, "builtin_tools"))  # v1
        self._relate_many(module, facts, agent.key, "uses", arg(call, "mcp_servers"))  # v1
        caps = arg(call, "capabilities")
        items = elements(caps)
        if items is None:
            self._relate_many(module, facts, agent.key, "uses", caps)
            return
        for el in items:
            sym = call_symbol(module, el, S.ROOTS) if isinstance(el, cst.Call) else None
            if isinstance(el, cst.Call) and sym in S.CAP_TOOLSET:
                self._relate(module, facts, agent.key, "uses", arg(el, "toolset", 0) or el)
            elif isinstance(el, cst.Call) and sym and el not in facts.call_keys:
                agent.attrs.badges.append(sym.split(".", 1)[1])  # e.g. Thinking, Caching, TemporalDurability
            else:
                self._relate(module, facts, agent.key, "uses", el)

    def _relate_many(self, module: Module, facts: Facts, source: str, kind, expr: cst.BaseExpression | None) -> None:
        if expr is None:
            return
        items = elements(expr)
        if items is None:
            self._relate(module, facts, source, kind, expr)
            return
        for el in items:
            self._relate(module, facts, source, kind, el)

    def _relate(self, module: Module, facts: Facts, source: str, kind, el: cst.BaseExpression) -> None:
        base, wrappers = unwrap_chain(module, el, S.TOOLSET_METHODS)
        facts.edge(source, kind, module, base, ref_node=el, wrappers=wrappers)

    # ------------------------------------------------------------------ decorators

    def _decorators(self, module: Module, facts: Facts) -> None:
        for binding in list(module.bindings.values()):
            fn = binding.node
            if binding.kind != "function" or not isinstance(fn, cst.FunctionDef):
                continue
            for dec in fn.decorators:
                owner, dcall = decorator_parts(dec)
                if not isinstance(owner, cst.Attribute):
                    continue
                attr = owner.attr.value
                target = owner.value
                if attr in S.DECORATOR_TOOL:
                    name = string_value(arg(dcall, "name")) if dcall else None
                    attrs = NodeAttrs(
                        docstring=shorten(docstring(fn), 400),
                        signature=signature(module, fn),
                        takes_ctx=attr == "tool",
                    )
                    if dcall and bool_value(arg(dcall, "requires_approval")):
                        attrs.badges.append("requires_approval")
                    d = facts.add(
                        Def(
                            key=key_of(module.name, binding.qualname),
                            kind="tool",
                            name=name or fn.name.value,
                            module=module,
                            node=fn,
                            name_node=fn.name,
                            framework="pydantic_ai",
                            attrs=attrs,
                            show=False,  # shown once linked to an agent/toolset/capability
                            fn=fn,
                        )
                    )
                    facts.edge(d.key, "uses", module, target, ref_node=dec, reverse=True)
                elif attr in S.DECORATOR_TOOLSET:
                    d = facts.add(
                        Def(
                            key=key_of(module.name, binding.qualname),
                            kind="toolset",
                            name=fn.name.value,
                            module=module,
                            node=fn,
                            name_node=fn.name,
                            framework="pydantic_ai",
                            status="dynamic",
                            attrs=NodeAttrs(docstring=shorten(docstring(fn), 400), extra={"class": "dynamic toolset"}),
                            show=False,
                        )
                    )
                    facts.edge(d.key, "uses", module, target, ref_node=dec, reverse=True)
                else:
                    owner_def = _local_owner(module, facts, target)
                    if owner_def is None:
                        continue
                    if attr in S.DECORATOR_INSTRUCTIONS:
                        owner_def.attrs.dynamic_instructions.append(fn.name.value)
                    elif attr in S.DECORATOR_BADGE and S.DECORATOR_BADGE[attr] not in owner_def.attrs.badges:
                        owner_def.attrs.badges.append(S.DECORATOR_BADGE[attr])

    def _add_function_calls(self, module: Module, facts: Facts) -> None:
        """``toolset.add_function(f)`` / ``toolset.add_tool(Tool(f))`` on a toolset of this module."""
        for call in module.calls:
            if isinstance(call.func, cst.Attribute) and call.func.attr.value in ("add_function", "add_tool"):
                owner = _local_owner(module, facts, call.func.value)
                target = arg(call, "func", 0) or arg(call, "tool", 0)
                if owner is not None and target is not None:
                    facts.edge(owner.key, "provides", module, target, ref_node=call)

    # ------------------------------------------------------------------ MCP

    def _mcp_target(self, module: Module, expr: cst.BaseExpression | None) -> tuple[str | None, str | None]:
        expr = value_of(module, expr)
        for _ in range(4):
            if expr is None:
                return None, None
            text = string_value(expr)
            if text is not None:
                return text, None
            if not isinstance(expr, cst.Call):
                return None, None
            cls = module.code(expr.func).rsplit(".", 1)[-1]
            if cls in ("StdioTransport", "MCPServerStdio"):
                command_expr = arg(expr, "command", 0)
                command = string_value(value_of(module, command_expr))
                command = command or (module.code(command_expr) if command_expr is not None else None)
                args = elements(arg(expr, "args", 1))
                parts = [string_value(a) or module.code(a) for a in args or []]
                return None, shorten(" ".join([command or "?", *parts]), 160)
            url = string_value(value_of(module, arg(expr, "url", 0)))
            if url is not None:
                return url, None
            expr = value_of(module, arg(expr, "transport", 0))  # Client(StdioTransport(...))
        return None, None

    def _mcp_config(self, module: Module, facts: Facts, call: cst.Call, add, *, v1: bool) -> None:
        if v1:
            facts.diag("AD101", "warning", "`load_mcp_servers` is PydanticAI v1 API; use `load_mcp_toolsets`.", call)
        path_text = string_value(value_of(module, arg(call, "config_path", 0)))
        d = add(
            "toolset",
            f"MCP config: {path_text or '?'}",
            status="partial",
            attrs=NodeAttrs(extra={"class": "load_mcp_toolsets"}),
        )
        if not path_text:
            return
        servers = _read_mcp_config(module, path_text)
        if servers is None:
            facts.diag("AD002", "info", f"MCP config `{path_text}` not found or unreadable.", call)
            return
        d.status = "resolved"
        for name, cfg in servers.items():
            server_key = key_of(module.name, f"{d.qualname}.{name}")
            url = cfg.get("url") if isinstance(cfg, dict) else None
            command = (
                " ".join([cfg.get("command", ""), *cfg.get("args", [])]).strip() if isinstance(cfg, dict) else None
            )
            facts.add(
                Def(
                    key=server_key,
                    kind="mcp_server",
                    name=name,
                    module=module,
                    node=call,
                    framework="pydantic_ai",
                    attrs=NodeAttrs(url=url, command=command or None),
                    show=False,
                )
            )
            facts.edge(d.key, "provides", module, server_key, ref_node=call)

    # ------------------------------------------------------------------ agent specs

    def _agent_spec(self, module: Module, facts: Facts, call: cst.Call, add) -> None:
        if not isinstance(call.func, cst.Attribute) or symbol(module, call.func.value, S.ROOTS) not in S.AGENT:
            return
        path_expr = value_of(module, arg(call, "path", 0) if module.code(call.func).endswith("from_file") else None)
        path_text = string_value(path_expr)
        spec: dict = {}
        if path_text:
            spec = _read_spec(module, path_text) or {}
            if not spec:
                facts.diag("AD002", "info", f"Agent spec `{path_text}` not found or unreadable.", call)
        attrs = NodeAttrs(
            agent_class="Agent (spec)",
            model=spec.get("model"),
            instructions=shorten(_join(spec.get("instructions"))),
            description=shorten(spec.get("description")),
            extra={"spec": path_text} if path_text else {},
        )
        d = add("agent", spec.get("name"), status="resolved" if spec else "partial", attrs=attrs)
        for cap in spec.get("capabilities") or []:
            name, value = (cap, None) if isinstance(cap, str) else next(iter(cap.items()))
            if name == "MCP":
                url = value if isinstance(value, str) else (value or {}).get("url")
                mcp_key = key_of(module.name, f"{d.qualname}.<MCP>{url}")
                facts.add(
                    Def(
                        key=mcp_key,
                        kind="mcp_server",
                        name=_mcp_name(url, None),
                        module=module,
                        node=call,
                        framework="pydantic_ai",
                        attrs=NodeAttrs(url=url, badges=["capability"]),
                        show=False,
                    )
                )
                facts.edge(d.key, "uses", module, mcp_key, ref_node=call)
            else:
                d.attrs.badges.append(name)


def _local_owner(module: Module, facts: Facts, expr: cst.BaseExpression) -> Def | None:
    if not isinstance(expr, cst.Name):
        return None
    qn = module.qname(expr) or expr.value
    d = facts.defs.get(key_of(module.name, qn))
    return d


def _join(value) -> str | None:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return value


def _mcp_name(url: str | None, command: str | None) -> str:
    if url:
        host = url.split("://", 1)[-1].split("/", 1)[0]
        return f"MCP {host}"
    if command:
        return f"MCP {command.split()[0].rsplit('/', 1)[-1]}"
    return "MCP"


def _candidate_paths(module: Module, path_text: str) -> list[Path]:
    p = Path(path_text)
    if p.is_absolute():
        return [p]
    root = module.path
    for _ in module.rel.split("/"):
        root = root.parent
    return [module.path.parent / p, root / p]


def _read_mcp_config(module: Module, path_text: str) -> dict | None:
    for candidate in _candidate_paths(module, path_text):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if isinstance(servers, dict):
            return servers
    return None


def _read_spec(module: Module, path_text: str) -> dict | None:
    for candidate in _candidate_paths(module, path_text):
        try:
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict):
            return data
    return None
