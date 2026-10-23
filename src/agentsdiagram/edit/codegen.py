"""Small code-generation helpers shared by the framework editors."""

from __future__ import annotations

import re
import shlex
from urllib.parse import urlparse

import libcst as cst

from .doc import Doc, EditError
from .session import py_string


def params_of(text: str | None, default: str = "query: str") -> tuple[str, list[str], list[str]]:
    """Validate a parameter list; returns (code, names, names without a type hint)."""
    code = (text or "").strip() or default
    try:
        fn = cst.parse_statement(f"def _f({code}): pass\n")
    except cst.ParserSyntaxError as exc:
        raise EditError(f"`{code}` is not a valid parameter list.") from exc
    assert isinstance(fn, cst.FunctionDef)
    params = [*fn.params.posonly_params, *fn.params.params, *fn.params.kwonly_params]
    return code, [p.name.value for p in params], [p.name.value for p in params if p.annotation is None]


def annotation(text: str | None, default: str = "str") -> str:
    code = (text or "").strip() or default
    try:
        cst.parse_expression(code)
    except cst.ParserSyntaxError as exc:
        raise EditError(f"`{code}` is not a valid type.") from exc
    return code


def docstring(text: str) -> str:
    """Body of a triple-quoted docstring."""
    return " ".join(text.split()).replace("\\", "\\\\").replace('"""', '\\"\\"\\"')


def unique(doc: Doc, base: str) -> str:
    taken = doc.top_names()
    name, n = base, 2
    while name in taken:
        name, n = f"{base}_{n}", n + 1
    return name


def free(doc: Doc, name: str) -> str:
    if name in doc.top_names():
        raise EditError(f"`{name}` already exists in {doc.rel}; pick another name.")
    return name


def mcp_name(url: str | None, command: str | None) -> str:
    """``https://docs.example.com/mcp`` -> ``docs_mcp``; ``uvx arxiv-mcp-server`` -> ``arxiv_mcp_server``."""
    word = ""
    if url:
        host = urlparse(url).hostname or url
        labels = [w for w in host.split(".") if w not in ("www", "mcp", "api")]
        word = labels[0] if labels else "server"
    elif command:
        parts = shlex.split(command)
        runners = {"uvx", "npx", "uv", "python", "python3", "node", "deno", "bunx", "-m", "run", "--from", "-y"}
        rest = [p for p in parts if p not in runners and not p.startswith("-")]
        word = (rest[0] if rest else parts[0] if parts else "server").rsplit("/", 1)[-1].split("@", 1)[0]
    name = re.sub(r"\W+", "_", word).strip("_").lower() or "server"
    if name[0].isdigit():
        name = f"mcp_{name}"
    return name if "mcp" in name else f"{name}_mcp"


def command_parts(command: str) -> tuple[str, str]:
    """``uvx arxiv-mcp-server --x`` -> ('"uvx"', '["arxiv-mcp-server", "--x"]')."""
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise EditError(f"cannot parse the command `{command}`: {exc}") from exc
    if not parts:
        raise EditError("The MCP command is empty.")
    return py_string(parts[0]), "[" + ", ".join(py_string(p) for p in parts[1:]) + "]"


def bound_decorator(dec: cst.Decorator, var: str) -> bool:
    """``@var.tool`` / ``@var.tool(...)``: a decorator that registers the function on ``var``."""
    expr = dec.decorator.func if isinstance(dec.decorator, cst.Call) else dec.decorator
    return isinstance(expr, cst.Attribute) and isinstance(expr.value, cst.Name) and expr.value.value == var


def tools_anchor(doc: Doc, index: int, var: str) -> int:
    """Last module-level function registered on ``var`` after its definition (or the definition)."""
    anchor = index
    for i in range(index + 1, len(doc.tree.body)):
        stmt = doc.tree.body[i]
        if isinstance(stmt, cst.FunctionDef) and any(bound_decorator(d, var) for d in stmt.decorators):
            anchor = i
    return anchor
