"""Adapter protocol and CST helpers shared by framework adapters."""

from __future__ import annotations

from typing import Protocol

import libcst as cst

from ..facts import Facts
from ..ir import Framework, Project
from ..project import Module


class Adapter(Protocol):
    framework: Framework
    #: byte markers for a cheap prefilter: a module is only parsed for this adapter if it contains one
    markers: tuple[bytes, ...]
    #: method names that run an agent (``agent.run(...)``); used for delegation and workflows
    run_methods: frozenset[str]

    def extract(self, module: Module, facts: Facts) -> None: ...

    def check(self, project: Project) -> None:
        """Post-link checks that need the whole graph (e.g. name collisions)."""
        ...


def symbol(module: Module, expr: cst.CSTNode, roots: tuple[str, ...]) -> str | None:
    """Return ``root.LastName`` if ``expr`` refers to a symbol of one of ``roots``.

    Libraries re-export their API from internal modules (``pydantic_ai.agent.Agent`` is
    ``pydantic_ai.Agent``), so matching is by root package and final component.
    """
    qn = module.qname(expr)
    if not qn:
        return None
    head = qn.split(".", 1)[0]
    if head not in roots:
        return None
    return f"{head}.{qn.rsplit('.', 1)[-1]}"


def call_symbol(module: Module, call: cst.Call, roots: tuple[str, ...]) -> str | None:
    return symbol(module, call.func, roots)


def arg(call: cst.Call, name: str, position: int | None = None) -> cst.BaseExpression | None:
    for a in call.args:
        if a.keyword is not None and a.keyword.value == name:
            return a.value
    if position is not None:
        positional = [a for a in call.args if a.keyword is None and not a.star]
        if len(positional) > position:
            return positional[position].value
    return None


def string_value(expr: cst.BaseExpression | None) -> str | None:
    if isinstance(expr, cst.SimpleString | cst.ConcatenatedString):
        value = expr.evaluated_value
        return value if isinstance(value, str) else None
    return None


def bool_value(expr: cst.BaseExpression | None) -> bool | None:
    if isinstance(expr, cst.Name) and expr.value in ("True", "False"):
        return expr.value == "True"
    return None


def shorten(text: str | None, limit: int = 280) -> str | None:
    if text is None:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def docstring(node: cst.FunctionDef | cst.ClassDef) -> str | None:
    return node.get_docstring(clean=True)


def signature(module: Module, fn: cst.FunctionDef) -> str:
    params = module.code(fn.params)
    returns = f" -> {module.code(fn.returns.annotation)}" if fn.returns else ""
    prefix = "async def" if fn.asynchronous else "def"
    return f"{prefix} {fn.name.value}({params}){returns}"


def decorator_parts(dec: cst.Decorator) -> tuple[cst.BaseExpression, cst.Call | None]:
    """``@x.tool`` -> (x.tool, None); ``@x.tool(retries=2)`` -> (x.tool, call)."""
    if isinstance(dec.decorator, cst.Call):
        return dec.decorator.func, dec.decorator
    return dec.decorator, None


def iter_calls(node: cst.CSTNode) -> list[cst.Call]:
    found: list[cst.Call] = []

    class _V(cst.CSTVisitor):
        def visit_Call(self, n: cst.Call) -> None:
            found.append(n)

        # nested definitions have their own bodies
        def visit_FunctionDef(self, n: cst.FunctionDef) -> bool:
            return n is node

        def visit_ClassDef(self, n: cst.ClassDef) -> bool:
            return n is node

    node.visit(_V())
    return found


def elements(expr: cst.BaseExpression | None) -> list[cst.BaseExpression] | None:
    """Elements of a literal list/tuple/set (starred elements included), else None."""
    if isinstance(expr, cst.List | cst.Tuple | cst.Set):
        out: list[cst.BaseExpression] = []
        for el in expr.elements:
            out.append(el.value)
        return out
    return None


def value_of(module: Module, expr: cst.BaseExpression | None, depth: int = 4) -> cst.BaseExpression | None:
    """Follow simple local assignments (``x = <value>``) inside the same module."""
    while depth and isinstance(expr, cst.Name):
        qn = module.qname(expr) or expr.value
        b = module.bindings.get(qn)
        if b is None or b.kind not in ("assign", "with"):
            break
        expr = b.node  # type: ignore[assignment]
        depth -= 1
    return expr


def describe_model(module: Module, expr: cst.BaseExpression | None) -> str | None:
    """Human label for a model argument: a string id, or ``Class(model_id)``."""
    expr = value_of(module, expr)
    if expr is None:
        return None
    text = string_value(expr)
    if text is not None:
        return text
    if isinstance(expr, cst.Call):
        cls = module.code(expr.func).rsplit(".", 1)[-1]
        first = arg(expr, "model_id", 0) or arg(expr, "model_name", 0)
        first_text = string_value(value_of(module, first))
        return f"{cls}({first_text!r})" if first_text else f"{cls}(…)"
    return shorten(module.code(expr), 80)


def unwrap_chain(module: Module, expr: cst.BaseExpression, methods: set[str]) -> tuple[cst.BaseExpression, list[str]]:
    """``ts.prefixed('a').filtered(f)`` -> (ts, ["prefixed('a')", "filtered(f)"])."""
    wrappers: list[str] = []
    while isinstance(expr, cst.Call) and isinstance(expr.func, cst.Attribute) and expr.func.attr.value in methods:
        args = ", ".join(module.code(a).rstrip(", ") for a in expr.args)
        wrappers.insert(0, f"{expr.func.attr.value}({shorten(args, 40) or ''})")
        expr = expr.func.value
    return expr, wrappers


def path_value(module: Module, expr: cst.BaseExpression | None) -> tuple[str, str] | None:
    """A file path written in code: ``"spec.yaml"`` or ``Path(__file__).parent / "spec.yaml"``
    (also ``.with_name("spec.yaml")``). Returns (path to look up, text to show)."""
    expr = value_of(module, expr)
    text = string_value(expr)
    if text is not None:
        return text, text
    parts: list[str] = []
    while isinstance(expr, cst.BinaryOperation) and isinstance(expr.operator, cst.Divide):
        right = string_value(expr.right)
        if right is None:
            return None
        parts.insert(0, right)
        expr = expr.left
    here = module.code(expr).replace(" ", "") if expr is not None else ""
    if isinstance(expr, cst.Call) and isinstance(expr.func, cst.Attribute) and expr.func.attr.value == "with_name":
        name = string_value(arg(expr, "name", 0))
        if name is None or module.code(expr.func.value).replace(" ", "") not in _HERE:
            return None
        return str(module.path.parent / name), name
    if parts and here in {f"{h}.parent" for h in _HERE}:
        shown = "/".join(parts)
        return str(module.path.parent.joinpath(*parts)), shown
    return None


_HERE = {"Path(__file__)", "pathlib.Path(__file__)", "Path(__file__).resolve()", "Path(__file__).absolute()"}
