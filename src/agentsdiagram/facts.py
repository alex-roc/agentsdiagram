"""Per-module facts recorded by adapters before linking (internal, not part of the IR)."""

from __future__ import annotations

from dataclasses import dataclass, field

import libcst as cst

from .ir import Diagnostic, EdgeKind, Framework, NodeAttrs, Status
from .project import Module


def key_of(module: str, qualname: str) -> str:
    return f"{module}:{qualname}"


@dataclass
class Def:
    """Something that may become an IR node.

    ``kind`` is an IR ``NodeKind`` or ``"function"``/``"class"``: plain definitions the core
    registers so the linker can turn them into tools when something uses them.
    """

    key: str
    kind: str
    name: str
    module: Module
    node: cst.CSTNode
    framework: Framework | None = None
    name_node: cst.CSTNode | None = None
    status: Status = "resolved"
    attrs: NodeAttrs = field(default_factory=NodeAttrs)
    show: bool = True  # shown even if nothing references it
    fn: cst.FunctionDef | None = None  # implementation, scanned for delegation (agent.run in a tool)
    impl: cst.BaseExpression | None = None  # expression naming the implementation, e.g. Tool(func)

    @property
    def qualname(self) -> str:
        return self.key.split(":", 1)[1]


@dataclass
class PendingEdge:
    source: str  # Def key
    kind: EdgeKind
    module: Module  # where ``target`` must be resolved
    target: cst.BaseExpression | str  # expression to resolve, or a Def key
    ref_node: cst.CSTNode | None = None
    label: str | None = None
    order: int | None = None
    wrappers: list[str] = field(default_factory=list)
    #: when True the edge goes from the resolved ``target`` to ``source`` (``@agent.tool`` style)
    reverse: bool = False


@dataclass
class Facts:
    module: Module
    defs: dict[str, Def] = field(default_factory=dict)
    call_keys: dict[cst.CSTNode, str] = field(default_factory=dict)
    edges: list[PendingEdge] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    frameworks: set[Framework] = field(default_factory=set)
    _ordinals: dict[str, int] = field(default_factory=dict)

    def add(self, d: Def, call: cst.CSTNode | None = None) -> Def:
        self.defs[d.key] = d
        if call is not None:
            self.call_keys[call] = d.key
        return d

    def anonymous_key(self, scope: str, kind: str) -> str:
        """Deterministic key for an unnamed construct: ordinal within its scope, never a line number."""
        base = f"{scope + '.' if scope else ''}<{kind}>"
        n = self._ordinals.get(base, 0) + 1
        self._ordinals[base] = n
        return key_of(self.module.name, f"{base}#{n}")

    def edge(self, *args, **kwargs) -> PendingEdge:
        e = PendingEdge(*args, **kwargs)
        self.edges.append(e)
        return e

    def diag(
        self,
        code: str,
        severity: str,
        message: str,
        node: cst.CSTNode | None = None,
        node_id: str | None = None,
    ) -> None:
        self.diagnostics.append(
            Diagnostic(
                code=code,
                severity=severity,  # type: ignore[arg-type]
                message=message,
                ref=self.module.ref(node) if node is not None else None,
                node_id=node_id,
            )
        )
