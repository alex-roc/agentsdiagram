"""pydantic-graph: ``GraphBuilder`` steps/edges/decisions and ``BaseNode`` return-type edges."""

from __future__ import annotations

import libcst as cst

from ...facts import Def, Facts, key_of
from ...ir import NodeAttrs
from ...project import Module
from ..base import (
    arg,
    call_symbol,
    decorator_parts,
    docstring,
    shorten,
    signature,
    string_value,
)
from . import symbols as S


def extract(module: Module, facts: Facts) -> None:
    builders = _builders(module, facts)
    if builders:
        _steps(module, facts, builders)
        _edges(module, facts, builders)
    _base_nodes(module, facts)


def _builders(module: Module, facts: Facts) -> dict[str, Def]:
    """Binding qualname of each GraphBuilder -> graph Def."""
    found: dict[str, Def] = {}
    for call in module.calls:
        if call_symbol(module, call, S.ROOTS) not in S.GRAPH_BUILDER:
            continue
        bound = module.binding_name_for(call)
        if not bound:
            continue
        qualname, name_node = bound
        fn = module.enclosing_function(call)
        name = fn.name.value if fn is not None else qualname.rsplit(".", 1)[-1]
        extra = {}
        for k in ("state_type", "input_type", "output_type"):
            v = arg(call, k)
            if v is not None:
                extra[k] = module.code(v)
        d = facts.add(
            Def(
                key=key_of(module.name, qualname),
                kind="graph",
                name=name,
                module=module,
                node=call,
                name_node=name_node,
                framework="pydantic_ai",
                attrs=NodeAttrs(extra=extra),
            ),
            call,
        )
        found[qualname] = d
    return found


def _owner(module: Module, expr: cst.BaseExpression, builders: dict[str, Def]) -> Def | None:
    if isinstance(expr, cst.Name):
        return builders.get(module.qname(expr) or expr.value)
    return None


def _special(module: Module, facts: Facts, graph: Def, which: str) -> str:
    key = key_of(module.name, f"{graph.qualname}.<{which}>")
    if key not in facts.defs:
        facts.add(
            Def(
                key=key,
                kind="graph_step",
                name=which,
                module=module,
                node=graph.node,
                framework="pydantic_ai",
                attrs=NodeAttrs(extra={"role": which}),
            )
        )
        facts.edge(graph.key, "contains", module, key)
    return key


def _steps(module: Module, facts: Facts, builders: dict[str, Def]) -> None:
    for binding in list(module.bindings.values()):
        if binding.kind == "function" and isinstance(binding.node, cst.FunctionDef):
            fn = binding.node
            for dec in fn.decorators:
                func, _ = decorator_parts(dec)
                if isinstance(func, cst.Attribute) and func.attr.value == "step":
                    graph = _owner(module, func.value, builders)
                    if graph is None:
                        continue
                    d = facts.add(
                        Def(
                            key=key_of(module.name, binding.qualname),
                            kind="graph_step",
                            name=fn.name.value,
                            module=module,
                            node=fn,
                            name_node=fn.name,
                            framework="pydantic_ai",
                            attrs=NodeAttrs(docstring=shorten(docstring(fn), 400), signature=signature(module, fn)),
                            fn=fn,
                        )
                    )
                    facts.edge(graph.key, "contains", module, d.key)
        elif binding.kind == "assign" and isinstance(binding.node, cst.Call):
            call = binding.node
            if isinstance(call.func, cst.Attribute) and call.func.attr.value == "join":
                graph = _owner(module, call.func.value, builders)
                if graph is None:
                    continue
                d = facts.add(
                    Def(
                        key=key_of(module.name, binding.qualname),
                        kind="graph_step",
                        name=binding.qualname.rsplit(".", 1)[-1],
                        module=module,
                        node=call,
                        name_node=binding.name_node,
                        framework="pydantic_ai",
                        attrs=NodeAttrs(extra={"role": "join"}),
                    ),
                    call,
                )
                facts.edge(graph.key, "contains", module, d.key)


def _step_key(module: Module, facts: Facts, graph: Def, expr: cst.BaseExpression) -> str | None:
    if isinstance(expr, cst.Attribute) and expr.attr.value in ("start_node", "end_node"):
        return _special(module, facts, graph, "start" if expr.attr.value == "start_node" else "end")
    if isinstance(expr, cst.Name):
        key = key_of(module.name, module.qname(expr) or expr.value)
        if key in facts.defs:
            return key
    return None


def _chain(expr: cst.BaseExpression) -> list[cst.Call]:
    """Flatten ``a(...).b(...).c(...)`` into [a-call, b-call, c-call]."""
    calls: list[cst.Call] = []
    while isinstance(expr, cst.Call) and isinstance(expr.func, cst.Attribute):
        calls.insert(0, expr)
        expr = expr.func.value
    return calls


def _edges(module: Module, facts: Facts, builders: dict[str, Def]) -> None:
    for call in module.calls:
        if not (isinstance(call.func, cst.Attribute) and call.func.attr.value == "to"):
            continue
        chain = _chain(call)
        head = chain[0] if chain else None
        if head is None or not isinstance(head.func, cst.Attribute) or head.func.attr.value != "edge_from":
            continue
        graph = _owner(module, head.func.value, builders)
        if graph is None:
            continue
        label = None
        mapped = False
        for link in chain[1:-1]:
            name = link.func.attr.value  # type: ignore[union-attr]
            if name == "label":
                label = string_value(arg(link, "label", 0))
            elif name == "map":
                mapped = True
        sources = [_step_key(module, facts, graph, a.value) for a in head.args]
        for target_arg in call.args:
            targets = _targets(module, facts, graph, target_arg.value)
            for src in sources:
                if src is None:
                    continue
                for tgt, tgt_label in targets:
                    facts.edge(
                        src,
                        "transitions",
                        module,
                        tgt,
                        ref_node=call,
                        label=tgt_label or label or ("map" if mapped else None),
                    )


def _targets(module: Module, facts: Facts, graph: Def, expr: cst.BaseExpression) -> list[tuple[str, str | None]]:
    key = _step_key(module, facts, graph, expr)
    if key:
        return [(key, None)]
    chain = _chain(expr)
    if chain and isinstance(chain[0].func, cst.Attribute) and chain[0].func.attr.value == "decision":
        decision_key = facts.anonymous_key(graph.qualname, "decision")
        facts.add(
            Def(
                key=decision_key,
                kind="graph_step",
                name="decision",
                module=module,
                node=expr,
                framework="pydantic_ai",
                attrs=NodeAttrs(extra={"role": "decision"}),
            )
        )
        facts.edge(graph.key, "contains", module, decision_key)
        for link in chain[1:]:
            if link.func.attr.value != "branch":  # type: ignore[union-attr]
                continue
            branch = arg(link, "branch", 0)
            parts = _chain(branch) if branch is not None else []
            label = None
            for p in parts:
                name = p.func.attr.value  # type: ignore[union-attr]
                if name == "match":
                    t = arg(p, "source", 0)
                    label = module.code(t) if t is not None else None
                    if arg(p, "matches") is not None:
                        label = f"{label} if …" if label else "if …"
                elif name == "label":
                    label = string_value(arg(p, "label", 0)) or label
            last = parts[-1] if parts else None
            if last is not None and last.func.attr.value == "to":  # type: ignore[union-attr]
                for a in last.args:
                    for tgt, _ in _targets(module, facts, graph, a.value):
                        facts.edge(decision_key, "transitions", module, tgt, ref_node=link, label=label)
        return [(decision_key, None)]
    return []


def _base_nodes(module: Module, facts: Facts) -> None:
    classes: dict[str, cst.ClassDef] = {}
    for binding in module.bindings.values():
        node = binding.node
        if binding.kind != "class" or not isinstance(node, cst.ClassDef):
            continue
        for base in node.bases:
            value = base.value.value if isinstance(base.value, cst.Subscript) else base.value
            if call_symbol(module, cst.Call(func=value), S.ROOTS) in S.GRAPH_BASE_NODE or _is_base_node(module, value):
                classes[binding.qualname] = node
    if not classes:
        return
    graph = facts.add(
        Def(
            key=key_of(module.name, "<graph>"),
            kind="graph",
            name=f"{module.name.rsplit('.', 1)[-1]} graph",
            module=module,
            node=next(iter(classes.values())),
            framework="pydantic_ai",
            attrs=NodeAttrs(extra={"style": "BaseNode"}),
        )
    )
    for qualname, node in classes.items():
        key = key_of(module.name, qualname)
        facts.add(
            Def(
                key=key,
                kind="graph_step",
                name=node.name.value,
                module=module,
                node=node,
                name_node=node.name,
                framework="pydantic_ai",
                attrs=NodeAttrs(docstring=shorten(docstring(node), 400)),
            )
        )
        facts.edge(graph.key, "contains", module, key)
    for qualname, node in classes.items():
        run = next(
            (s for s in node.body.body if isinstance(s, cst.FunctionDef) and s.name.value == "run"),
            None,
        )
        if run is None or run.returns is None:
            continue
        for name in _annotation_names(run.returns.annotation):
            if name == "End":
                tgt = _special(module, facts, graph, "end")
            else:
                tgt = next((key_of(module.name, q) for q in classes if q.rsplit(".", 1)[-1] == name), None)
            if tgt:
                facts.edge(key_of(module.name, qualname), "transitions", module, tgt, ref_node=run.returns)


def _is_base_node(module: Module, expr: cst.BaseExpression) -> bool:
    qn = module.qname(expr)
    return bool(qn) and qn.split(".", 1)[0] == "pydantic_graph" and qn.endswith("BaseNode")


def _annotation_names(expr: cst.BaseExpression) -> list[str]:
    """Top-level names in ``A | B | End[T]`` or ``Union[A, B]``; strings are parsed too."""
    if isinstance(expr, cst.BinaryOperation) and isinstance(expr.operator, cst.BitOr):
        return _annotation_names(expr.left) + _annotation_names(expr.right)
    if isinstance(expr, cst.Subscript):
        head = expr.value
        head_name = head.attr.value if isinstance(head, cst.Attribute) else getattr(head, "value", "")
        if head_name == "Union":
            out: list[str] = []
            for el in expr.slice:
                if isinstance(el.slice, cst.Index):
                    out += _annotation_names(el.slice.value)
            return out
        return [head_name] if isinstance(head_name, str) else []
    if isinstance(expr, cst.Name):
        return [expr.value]
    if isinstance(expr, cst.Attribute):
        return [expr.attr.value]
    if isinstance(expr, cst.SimpleString):
        try:
            return _annotation_names(cst.parse_expression(str(expr.evaluated_value)))
        except cst.ParserSyntaxError:
            return []
    return []
