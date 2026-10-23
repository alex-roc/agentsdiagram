"""The ``planned`` marker: how code written by the planner says "not implemented yet".

There is no hidden state: a planned tool is a function whose body raises
``NotImplementedError("agentsdiagram: planned")``, and any other planned construct (an agent,
an MCP server) is a statement preceded by the comment ``# agentsdiagram: planned``.
Implement the function, or delete the comment, and the node is no longer planned.
"""

from __future__ import annotations

import libcst as cst

from .ir import PLANNED_MARKER
from .project import Module

RAISE_MARKER = f'raise NotImplementedError("{PLANNED_MARKER}")'
COMMENT_MARKER = f"# {PLANNED_MARKER}"


def raises_marker(fn: cst.FunctionDef | None) -> bool:
    """``raise NotImplementedError("agentsdiagram: planned…")`` directly in the function body."""
    if fn is None or not isinstance(fn.body, cst.IndentedBlock):
        return False
    for stmt in fn.body.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            exc = small.exc if isinstance(small, cst.Raise) else None
            if (
                isinstance(exc, cst.Call)
                and isinstance(exc.func, cst.Name)
                and exc.func.value == "NotImplementedError"
                and exc.args
                and isinstance(exc.args[0].value, cst.SimpleString)
                and str(exc.args[0].value.evaluated_value).startswith(PLANNED_MARKER)
            ):
                return True
    return False


def statement_of(module: Module, node: cst.CSTNode) -> cst.CSTNode | None:
    """The statement (simple line or compound) that contains ``node``."""
    current: cst.CSTNode | None = node
    while current is not None:
        if isinstance(current, cst.SimpleStatementLine | cst.BaseCompoundStatement):
            return current
        current = module.parents.get(current)
    return None


def has_marker_comment(module: Module, node: cst.CSTNode) -> bool:
    stmt = statement_of(module, node)
    if stmt is None:
        return False
    comments = [line.comment for line in getattr(stmt, "leading_lines", ()) if line.comment is not None]
    if isinstance(stmt, cst.SimpleStatementLine) and stmt.trailing_whitespace.comment is not None:
        comments.append(stmt.trailing_whitespace.comment)
    return any(c.value.lstrip("#").strip().startswith(PLANNED_MARKER) for c in comments)


def is_planned(module: Module, node: cst.CSTNode, fn: cst.FunctionDef | None) -> bool:
    return raises_marker(fn) or has_marker_comment(module, node)
