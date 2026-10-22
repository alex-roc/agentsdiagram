"""Analysis pipeline: parse modules lazily, run adapters, resolve references and link the IR."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

import libcst as cst

from . import __version__
from .adapters import ADAPTERS, Adapter
from .adapters.base import iter_calls, shorten, signature
from .facts import Def, Facts, PendingEdge, key_of
from .ir import (
    Diagnostic,
    Edge,
    FileInfo,
    Framework,
    Node,
    NodeAttrs,
    Position,
    Project,
    Range,
    SourceRef,
)
from .project import FileSet, Module, collect, module_name, parse_module

INSTANCE_KINDS = {"agent", "toolset", "mcp_server", "capability"}
LIB_ROOTS = {"pydantic_ai", "pydantic_ai_harness", "pydantic_graph", "smolagents"}
OWNER_KINDS = {"agent", "toolset", "capability", "mcp_server"}
PROVIDER_KINDS = {"toolset", "capability", "mcp_server"}


@dataclass
class Cache:
    """Reusable across runs (the LSP keeps one): parsed modules and facts by content hash,
    plus the last module that parsed, used while a file is temporarily invalid."""

    by_hash: dict[tuple[str, str], tuple[Module, Facts]] = field(default_factory=dict)
    last_good: dict[str, tuple[Module, Facts]] = field(default_factory=dict)


@dataclass
class Target:
    key: str | None = None
    module: Module | None = None
    node: cst.CSTNode | None = None  # unresolved expression (becomes a `dynamic` node)
    wrappers: tuple[str, ...] = ()  # method calls applied on the way: `ts.prefixed('x')`


class Analyzer:
    def __init__(
        self,
        files: FileSet,
        *,
        frameworks: Iterable[str] | None = None,
        cache: Cache | None = None,
        overrides: dict[Path, str] | None = None,
    ) -> None:
        self.files = files
        self.adapters: list[Adapter] = [
            a for name, a in ADAPTERS.items() if frameworks is None or name in set(frameworks)
        ]
        self.cache = cache or Cache()
        self.overrides = {p.resolve(): t for p, t in (overrides or {}).items()}
        self.modules: dict[str, Module | None] = {}
        self.facts: dict[str, Facts] = {}
        self.file_status: dict[str, str] = {}
        self.diagnostics: list[Diagnostic] = []
        self.instance_of: dict[str, str] = {}  # instance key -> factory product key
        self.templates: set[str] = set()  # factory products that have instances
        self.run_methods = frozenset().union(*(a.run_methods for a in self.adapters)) if self.adapters else frozenset()

    # ------------------------------------------------------------------ loading

    def facts_for(self, name: str) -> Facts | None:
        if name in self.facts:
            return self.facts[name]
        if name in self.modules:  # failed before
            return None
        path = self.files.index.get(name)
        if path is None:
            self.modules[name] = None
            return None
        path = path.resolve()
        rel = path.relative_to(self.files.root).as_posix()
        try:
            text = self.overrides.get(path)
            if text is None:
                text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            self.modules[name] = None
            return None
        import hashlib

        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = self.cache.by_hash.get((rel, sha))
        if cached:
            module, facts = cached
            self.file_status[rel] = "ok"
        else:
            try:
                module = parse_module(self.files.root, path, text)
                facts = self._extract(module)
                self.cache.by_hash[(rel, sha)] = (module, facts)
                self.cache.last_good[rel] = (module, facts)
                self.file_status[rel] = "ok"
            except cst.ParserSyntaxError as exc:
                where = SourceRef(
                    file=rel,
                    range=Range(
                        start=Position(line=exc.raw_line, column=exc.raw_column),
                        end=Position(line=exc.raw_line, column=exc.raw_column),
                    ),
                )
                previous = self.cache.last_good.get(rel)
                if previous is None:
                    self.file_status[rel] = "error"
                    self.diagnostics.append(
                        Diagnostic(
                            code="AD000",
                            severity="error",
                            message=f"Syntax error: {shorten(exc.message, 120)}",
                            ref=where,
                        )
                    )
                    self.modules[name] = None
                    return None
                module, facts = previous
                self.file_status[rel] = "stale"
                self.diagnostics.append(
                    Diagnostic(
                        code="AD000",
                        severity="warning",
                        message=f"Syntax error ({shorten(exc.message, 120)}); showing the last valid version.",
                        ref=where,
                    )
                )
        self.modules[name] = module
        self.facts[name] = facts
        return facts

    def worth_parsing(self, path: Path) -> bool:
        """Cheap byte prefilter for seed files: framework imports, or agent runs (workflows)."""
        path = path.resolve()
        text = self.overrides.get(path)
        try:
            raw = text.encode("utf-8") if text is not None else path.read_bytes()
        except OSError:
            return False
        if any(m in raw for a in self.adapters for m in a.markers):
            return True
        return any(f".{m}(".encode() in raw for m in self.run_methods)

    def _extract(self, module: Module) -> Facts:
        facts = Facts(module=module)
        for b in module.bindings.values():
            if b.kind in ("function", "class"):
                facts.add(
                    Def(
                        key=key_of(module.name, b.qualname),
                        kind=b.kind,
                        name=b.qualname.rsplit(".", 1)[-1],
                        module=module,
                        node=b.node,
                        name_node=b.name_node,
                        show=False,
                        fn=b.node if isinstance(b.node, cst.FunctionDef) else None,
                    )
                )
        raw = module.text.encode("utf-8", errors="ignore")
        for adapter in self.adapters:
            if not any(m in raw for m in adapter.markers):
                continue
            try:
                adapter.extract(module, facts)
            except Exception as exc:  # an adapter bug must not take the whole diagram down
                facts.diag("AD900", "error", f"{adapter.framework} adapter failed on this file: {exc!r}")
        return facts

    def def_(self, key: str) -> Def | None:
        module = key.split(":", 1)[0]
        facts = self.facts_for(module)
        return facts.defs.get(key) if facts else None

    # ------------------------------------------------------------------ resolution

    def resolve(self, module: Module, expr: cst.BaseExpression | str, depth: int = 0) -> list[Target]:
        if isinstance(expr, str):
            return [Target(key=expr)] if self.def_(expr) else []
        if depth > 10:
            return [Target(module=module, node=expr)]
        if isinstance(expr, cst.List | cst.Tuple | cst.Set):
            return [t for el in expr.elements for t in self.resolve(module, el.value, depth + 1)]
        if isinstance(expr, cst.BinaryOperation) and isinstance(expr.operator, cst.Add):
            return self.resolve(module, expr.left, depth + 1) + self.resolve(module, expr.right, depth + 1)
        if isinstance(expr, cst.Await):
            return self.resolve(module, expr.expression, depth + 1)
        if isinstance(expr, cst.Call):
            facts = self.facts_for(module.name)
            key = facts.call_keys.get(expr) if facts else None
            if key:
                return [Target(key=key)]
            func_targets = [t for t in self.resolve(module, expr.func, depth + 1) if t.key]
            for t in func_targets:
                d = self.def_(t.key)  # type: ignore[arg-type]
                if d is None:
                    continue
                if d.kind == "function" and d.fn is not None:  # factory: follow its return value
                    returned = _return_value(d.fn)
                    if returned is not None:
                        return self.resolve(d.module, returned, depth + 1)
                elif d.kind != "function":  # MyTool() -> the Tool subclass, client.get_tools() -> client
                    if isinstance(expr.func, cst.Attribute) and d.kind != "class":
                        args = ", ".join(module.code(a).rstrip(", ") for a in expr.args)
                        return [
                            replace(t, wrappers=(*t.wrappers, f"{expr.func.attr.value}({shorten(args, 40) or ''})"))
                        ]
                    return [t]
            return [Target(module=module, node=expr)]
        if isinstance(expr, cst.Name | cst.Attribute):
            qn = module.qname(expr) or module.code(expr)
            found = self.lookup(module, qn, depth + 1)
            return found or [Target(module=module, node=expr)]
        return [Target(module=module, node=expr)]

    def lookup(self, module: Module, qn: str, depth: int) -> list[Target]:
        if depth > 10:
            return []
        facts = self.facts_for(module.name)
        if facts is None:
            return []
        key = key_of(module.name, qn)
        if key in facts.defs:
            return [Target(key=key)]
        b = module.bindings.get(qn)
        if b is not None:
            if b.kind in ("assign", "with"):
                found = self.resolve(module, b.node, depth + 1)  # type: ignore[arg-type]
                return self._instance(module, facts, b, found)
            if b.kind == "import" and b.target:
                return self.lookup_absolute(b.target, depth + 1)
            return []
        parts = qn.split(".")
        for i in range(len(parts) - 1, 0, -1):  # attribute on a known binding: `tc.tools`
            if parts[i] == "<locals>":  # `f.<locals>.x` is a local of f, not an attribute of f
                continue
            prefix = ".".join(parts[:i])
            pb = module.bindings.get(prefix)
            if pb is not None and pb.kind == "import" and pb.target:
                return self.lookup_absolute(".".join([pb.target, *parts[i:]]), depth + 1)
            if pb is not None or key_of(module.name, prefix) in facts.defs:
                return self.lookup(module, prefix, depth + 1)
        return self.lookup_absolute(qn, depth + 1)

    def _instance(self, module: Module, facts: Facts, b, found: list[Target]) -> list[Target]:
        """``planner = make_agent("planner", ...)``: a factory call becomes its own node.

        Without this, every agent built by the same factory would collapse into one node.
        The instance copies the product's attributes and relations; the factory's template
        is hidden from the diagram (see ``Analyzer.templates``).
        """
        if not (isinstance(b.node, cst.Call) and len(found) == 1 and found[0].key):
            return found
        product = self.def_(found[0].key)
        if product is None or product.node is b.node or product.kind not in INSTANCE_KINDS:
            return found
        key = key_of(module.name, b.qualname)
        if key not in facts.defs:
            facts.add(
                replace(
                    product,
                    key=key,
                    name=b.qualname.rsplit(".", 1)[-1],
                    module=module,
                    node=b.node,
                    name_node=b.name_node,
                    status="partial",
                    attrs=product.attrs.model_copy(deep=True),
                    show=True,
                )
            )
            product_facts = self.facts_for(product.module.name)
            for e in list(product_facts.edges if product_facts else []):
                if e.source == product.key and not e.reverse:
                    facts.edges.append(replace(e, source=key))
            self.instance_of[key] = product.key
            self.templates.add(product.key)
        return [Target(key=key)]

    def lookup_absolute(self, dotted: str, depth: int) -> list[Target]:
        parts = dotted.split(".")
        for i in range(len(parts), 0, -1):
            name = ".".join(parts[:i])
            if name in self.files.index:
                rest = ".".join(parts[i:])
                if not rest:
                    return []
                self.facts_for(name)
                target = self.modules.get(name)
                return self.lookup(target, rest, depth + 1) if target else []
        return []


def _return_value(fn: cst.FunctionDef) -> cst.BaseExpression | None:
    found: list[cst.BaseExpression] = []

    class _V(cst.CSTVisitor):
        def visit_FunctionDef(self, n: cst.FunctionDef) -> bool:
            return n is fn

        def visit_Lambda(self, n: cst.Lambda) -> bool:
            return False

        def visit_Return(self, n: cst.Return) -> None:
            if n.value is not None:
                found.append(n.value)

    fn.visit(_V())
    return found[-1] if found else None


# ---------------------------------------------------------------------- linking


def analyze(
    path: Path | str,
    *,
    frameworks: Iterable[str] | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    cache: Cache | None = None,
    overrides: dict[Path, str] | None = None,
) -> Project:
    files = collect(Path(path), include=include, exclude=exclude)
    return link(Analyzer(files, frameworks=frameworks, cache=cache, overrides=overrides))


def link(an: Analyzer) -> Project:
    root = an.files.root
    seed_names = [module_name(root, p.resolve()) for p in an.files.seeds if an.worth_parsing(p)]
    for name in seed_names:
        an.facts_for(name)
    seeds = [n for n in seed_names if n in an.facts]

    # 0. `x = factory(...)` in seed modules: materialise factory products as their own nodes
    for name in seeds:
        module = an.modules[name]
        for b in list(module.bindings.values()):  # type: ignore[union-attr]
            if b.kind == "assign" and isinstance(b.node, cst.Call) and b.node not in an.facts[name].call_keys:
                an.lookup(module, b.qualname, 0)  # type: ignore[arg-type]

    # 1. resolve every pending edge, loading further modules as needed (fixpoint)
    resolved: dict[int, tuple[PendingEdge, list[Target]]] = {}
    while True:
        pending = [e for f in list(an.facts.values()) for e in f.edges if id(e) not in resolved]
        if not pending:
            break
        for e in pending:
            resolved[id(e)] = (e, an.resolve(e.module, e.target))

    edges: list[_Link] = []
    for e, targets in resolved.values():
        for t in targets:
            if e.reverse:
                owner = an.def_(t.key) if t.key else None
                if owner is None or owner.kind not in OWNER_KINDS:
                    continue  # e.g. `@server.tool()` of a FastMCP server: not an agent tool
                edges.append(_Link(owner.key, e.kind, e.source, e))
                for inst, product in an.instance_of.items():
                    if product == owner.key:
                        edges.append(_Link(inst, e.kind, e.source, e))
            elif t.key:
                edges.append(_Link(e.source, e.kind, t.key, e, wrappers=list(t.wrappers)))
            else:
                edges.append(_Link(e.source, e.kind, None, e, dynamic=t))

    # 2. visibility: explicit defs of seed modules, then everything reachable from them
    visible: set[str] = {
        d.key
        for name in seeds
        for d in an.facts[name].defs.values()
        if d.show and d.kind not in ("function", "class") and d.key not in an.templates
    }

    def expand() -> None:
        changed = True
        while changed:
            changed = False
            for link_ in edges:
                if link_.source in visible and link_.target and link_.target not in visible:
                    visible.add(link_.target)
                    changed = True

    expand()

    # 3. implicit relations found in function bodies: delegation (agent.run inside a tool/step) and workflows
    scanned: set[str] = set()
    while True:
        todo = [k for k in sorted(visible) if k not in scanned]
        if not todo:
            break
        for key in todo:
            scanned.add(key)
            d = an.def_(key)
            if d is None:
                continue
            fn = _implementation(an, d)
            if fn is None:
                continue
            kind = "runs" if d.kind == "graph_step" else "delegates_to"
            for agent_key, call in _agent_runs(an, d.module if d.fn is fn else _fn_module(an, d), fn):
                edges.append(_Link(key, kind, agent_key, None, call=call, module=d.module))
        _workflows(an, seeds, visible, edges)
        expand()

    return _build(an, seeds, visible, edges)


@dataclass
class _Link:
    source: str
    kind: str
    target: str | None
    pending: PendingEdge | None
    dynamic: Target | None = None
    call: cst.CSTNode | None = None
    module: Module | None = None
    order: int | None = None
    wrappers: list[str] = field(default_factory=list)


def _implementation(an: Analyzer, d: Def) -> cst.FunctionDef | None:
    if d.kind not in ("tool", "function", "graph_step"):
        return None
    if d.fn is not None:
        return d.fn
    if d.impl is not None:
        for t in an.resolve(d.module, d.impl):
            target = an.def_(t.key) if t.key else None
            if target is not None and target.fn is not None:
                if d.attrs.docstring is None:
                    d.attrs.docstring = shorten(target.fn.get_docstring(clean=True), 400)
                    d.attrs.signature = signature(target.module, target.fn)
                if d.attrs.takes_ctx is None:
                    d.attrs.takes_ctx = _takes_ctx(target.module, target.fn)
                d._impl_module = target.module  # type: ignore[attr-defined]
                return target.fn
    return None


def _fn_module(an: Analyzer, d: Def) -> Module:
    return getattr(d, "_impl_module", d.module)


def _agent_runs(an: Analyzer, module: Module, fn: cst.FunctionDef) -> list[tuple[str, cst.Call]]:
    found: list[tuple[str, cst.Call]] = []
    for call in iter_calls(fn):
        if not (isinstance(call.func, cst.Attribute) and call.func.attr.value in an.run_methods):
            continue
        for t in an.resolve(module, call.func.value):
            d = an.def_(t.key) if t.key else None
            if d is not None and d.kind == "agent":
                found.append((d.key, call))
    return found


def _workflows(an: Analyzer, seeds: list[str], visible: set[str], edges: list[_Link]) -> None:
    for name in seeds:
        facts = an.facts[name]
        for d in list(facts.defs.values()):
            if d.kind != "function" or d.fn is None or d.key in visible:
                continue
            runs = _agent_runs(an, d.module, d.fn)
            if len(runs) < 2:
                continue
            d.kind = "workflow"
            d.framework = an.def_(runs[0][0]).framework  # type: ignore[union-attr]
            d.attrs = NodeAttrs(
                docstring=shorten(d.fn.get_docstring(clean=True), 400), signature=signature(d.module, d.fn)
            )
            visible.add(d.key)
            for order, (agent_key, call) in enumerate(runs, start=1):
                edges.append(_Link(d.key, "runs", agent_key, None, call=call, module=d.module, order=order))


def _library_class(module: Module, node: cst.CSTNode) -> str | None:
    """``Hooks(...)`` from pydantic_ai -> "Hooks": unknown library objects become badges, not dynamic nodes."""
    if not isinstance(node, cst.Call):
        return None
    qn = module.qname(node.func)
    if qn and qn.split(".", 1)[0] in LIB_ROOTS:
        return qn.rsplit(".", 1)[-1]
    return None


def node_attrs_badges(nodes: list[Node], node_id: str) -> list[str]:
    return next((n.attrs.badges for n in nodes if n.id == node_id), [])


def _takes_ctx(module: Module, fn: cst.FunctionDef) -> bool:
    params = fn.params.params
    if not params or params[0].annotation is None:
        return False
    return "RunContext" in module.code(params[0].annotation.annotation)


def _node_id(d: Def, framework: str) -> str:
    return f"{framework}:{d.kind}:{d.module.name}.{d.qualname}"


def _build(an: Analyzer, seeds: list[str], visible: set[str], links: list[_Link]) -> Project:
    defs = {k: an.def_(k) for k in visible}
    defs = {k: d for k, d in defs.items() if d is not None}

    # framework for plain functions/classes comes from whoever uses them
    for link_ in links:
        if link_.target in defs and link_.source in defs:
            tgt = defs[link_.target]
            src = defs[link_.source]
            if tgt.framework is None and src.framework is not None:
                tgt.framework = src.framework
    for d in defs.values():
        if d.kind == "function":
            d.kind = "tool"
            if d.fn is not None:
                d.attrs = NodeAttrs(
                    docstring=shorten(d.fn.get_docstring(clean=True), 400),
                    signature=signature(d.module, d.fn),
                    takes_ctx=_takes_ctx(d.module, d.fn),
                )
        elif d.kind == "class":
            d.kind = "tool"
            d.status = "partial"
        if d.framework is None:
            d.framework = "pydantic_ai"

    stale = {rel for rel, status in an.file_status.items() if status == "stale"}
    ids = {k: _node_id(d, d.framework) for k, d in defs.items()}  # type: ignore[arg-type]
    nodes: list[Node] = []
    for k, d in sorted(defs.items(), key=lambda kv: ids[kv[0]]):
        status = "stale" if d.module.rel in stale else d.status
        nodes.append(
            Node(
                id=ids[k],
                kind=d.kind,  # type: ignore[arg-type]
                framework=d.framework,  # type: ignore[arg-type]
                name=d.name,
                status=status,  # type: ignore[arg-type]
                source=d.module.ref(d.node, d.name_node),
                attrs=d.attrs,
            )
        )

    edges: list[Edge] = []
    diagnostics: list[Diagnostic] = list(an.diagnostics)
    seen: set[tuple] = set()
    dynamic_count: dict[str, int] = {}
    node_by_id = {n.id: n for n in nodes}
    for link_ in links:
        if link_.source not in defs:
            continue
        src_def = defs[link_.source]
        src_id = ids[link_.source]
        kind = link_.kind
        if kind == "uses" and src_def.kind in PROVIDER_KINDS:
            kind = "provides"
        p = link_.pending
        ref_module = p.module if p else link_.module
        ref_node = p.ref_node if p else link_.call
        ref = ref_module.ref(ref_node) if ref_module is not None and ref_node is not None else None
        if link_.target is None:
            if link_.dynamic is None or link_.dynamic.node is None or link_.dynamic.module is None:
                continue
            lib = _library_class(link_.dynamic.module, link_.dynamic.node)
            if lib is not None and kind == "uses":
                if lib not in node_attrs_badges(nodes, src_id):
                    next(n for n in nodes if n.id == src_id).attrs.badges.append(lib)
                continue
            text = shorten(link_.dynamic.module.code(link_.dynamic.node), 60) or "?"
            n = dynamic_count.get(src_id, 0) + 1
            dynamic_count[src_id] = n
            dyn_id = f"{src_id}~dynamic#{n}"
            node_by_id[dyn_id] = Node(
                id=dyn_id,
                kind="dynamic",
                framework=src_def.framework,  # type: ignore[arg-type]
                name=text,
                status="dynamic",
                source=link_.dynamic.module.ref(link_.dynamic.node),
            )
            nodes.append(node_by_id[dyn_id])
            target_id = dyn_id
            diagnostics.append(
                Diagnostic(
                    code="AD001",
                    severity="info",
                    message=f"`{text}` cannot be resolved statically; shown as a dynamic node.",
                    ref=node_by_id[dyn_id].source,
                    node_id=dyn_id,
                )
            )
        elif link_.target in defs:
            target_id = ids[link_.target]
        else:
            continue
        label = p.label if p else None
        wrappers = [*(p.wrappers if p else []), *link_.wrappers]
        dedupe = (kind, src_id, target_id, label, tuple(wrappers), link_.order)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        edges.append(
            Edge(
                id=f"{kind}:{src_id}->{target_id}" + (f"#{link_.order}" if link_.order else ""),
                kind=kind,  # type: ignore[arg-type]
                source=src_id,
                target=target_id,
                label=label,
                order=link_.order,
                wrappers=wrappers,
                ref=ref,
            )
        )
    # disambiguate duplicate edge ids (same pair, different labels/wrappers)
    counts: dict[str, int] = {}
    for e in edges:
        counts[e.id] = counts.get(e.id, 0) + 1
        if counts[e.id] > 1:
            e.id = f"{e.id}~{counts[e.id]}"

    for name in seeds:
        diagnostics.extend(an.facts[name].diagnostics)
    for d in diagnostics:
        if d.node_id is None and d.ref is not None:
            match = next(
                (n for n in nodes if n.source and n.source.file == d.ref.file and n.source.range == d.ref.range), None
            )
            if match:
                d.node_id = match.id

    frameworks: list[Framework] = sorted({n.framework for n in nodes})  # type: ignore[assignment]
    project = Project(
        tool_version=__version__,
        root=str(an.files.root),
        frameworks=frameworks,
        files=[
            FileInfo(
                path=an.facts[name].module.rel,
                module=name,
                frameworks=sorted(an.facts[name].frameworks),  # type: ignore[arg-type]
                status=an.file_status.get(an.facts[name].module.rel, "ok"),  # type: ignore[arg-type]
                sha256=an.facts[name].module.sha256,
            )
            for name in seeds
            if an.facts[name].frameworks
        ],
        nodes=nodes,
        edges=edges,
        diagnostics=diagnostics,
    )
    for adapter in an.adapters:
        adapter.check(project)
    project.diagnostics.sort(
        key=lambda d: (d.ref.file if d.ref else "", d.ref.range.start.line if d.ref else 0, d.code)
    )
    return project
