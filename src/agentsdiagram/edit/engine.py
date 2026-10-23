"""Edit operations: from an ``EditRequest`` (ids from the diagram) to file changes.

Framework-neutral operations (disconnect, remove, instructions) live here; what is written
for a new agent, tool, MCP server or connection is framework-specific and lives in
``adapters/<framework>/edit.py`` (see ``EDITORS``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import libcst as cst

from ..analyze import Cache
from ..ir import (
    AddAgent,
    AddMcp,
    AddTool,
    Connect,
    Disconnect,
    EditRequest,
    ExportSpec,
    Framework,
    Range,
    Remove,
    SetInstructions,
    SetModel,
)
from .codegen import bound_decorator
from .doc import Doc, EditError, remove_arg, set_arg
from .session import AgentSite, Change, Session, py_string


class FrameworkEditor(Protocol):
    framework: Framework
    #: constructor names that create an agent (``Agent``, ``CodeAgent``…)
    agent_classes: set[str]

    def add_agent(self, s: Session, req: AddAgent) -> str: ...
    def add_tool(self, s: Session, site: AgentSite, req: AddTool) -> str: ...
    def add_mcp(self, s: Session, site: AgentSite, req: AddMcp) -> str: ...
    def connect(self, s: Session, source: AgentSite, target: AgentSite, req: Connect) -> str: ...
    def set_model(self, s: Session, site: AgentSite, model: str) -> str: ...
    def export_spec(self, s: Session, site: AgentSite, req: ExportSpec) -> str: ...


def _editors() -> dict[str, FrameworkEditor]:
    from ..adapters.pydantic_ai.edit import PydanticAIEditor
    from ..adapters.smolagents.edit import SmolagentsEditor

    return {"pydantic_ai": PydanticAIEditor(), "smolagents": SmolagentsEditor()}  # type: ignore[dict-item]


EDITORS: dict[str, FrameworkEditor] = _editors()


@dataclass
class Outcome:
    changes: list[Change]
    message: str
    focus: str | None = None

    @property
    def files(self) -> list[str]:
        return [c.rel for c in self.changes]

    def write(self) -> None:
        for c in self.changes:
            c.path.parent.mkdir(parents=True, exist_ok=True)
            c.path.write_text(c.after, encoding="utf-8")


def plan_edit(
    root: Path | str,
    request: EditRequest,
    *,
    overrides: dict[Path, str] | None = None,
    expect: dict[str, str] | None = None,
    cache: Cache | None = None,
) -> Outcome:
    """Compute the changes for ``request`` without writing anything. Raises ``EditError``."""
    s = Session.open(Path(root), overrides=overrides, cache=cache)
    if expect:
        s.check_expect(expect)
    message = _dispatch(s, request)
    changes = s.changes()
    if not changes:
        raise EditError("Nothing to change.")
    if s.notes:
        message = " ".join([message, *s.notes])
    return Outcome(changes=changes, message=message, focus=s.focus)


def _editor(framework: str) -> FrameworkEditor:
    editor = EDITORS.get(framework)
    if editor is None:
        raise EditError(f"editing {framework} code is not supported yet.")
    return editor


def _site(s: Session, node_id: str) -> tuple[FrameworkEditor, AgentSite]:
    node = s.node(node_id, "agent")
    editor = _editor(node.framework)
    return editor, s.agent(node_id, editor.agent_classes)


def _dispatch(s: Session, req: EditRequest) -> str:
    if isinstance(req, AddAgent):
        return _editor(req.framework).add_agent(s, req)
    if isinstance(req, AddTool):
        editor, site = _site(s, req.agent)
        return editor.add_tool(s, site, req)
    if isinstance(req, AddMcp):
        if bool(req.url) == bool(req.command):
            raise EditError("Give either a URL or a command for the MCP server.")
        editor, site = _site(s, req.agent)
        return editor.add_mcp(s, site, req)
    if isinstance(req, Connect):
        return _connect(s, req)
    if isinstance(req, Disconnect):
        return _disconnect(s, req)
    if isinstance(req, Remove):
        return _remove(s, req)
    if isinstance(req, SetModel):
        if not req.model.strip():
            raise EditError("The model cannot be empty.")
        editor, site = _site(s, req.agent)
        return editor.set_model(s, site, req.model.strip())
    if isinstance(req, SetInstructions):
        return _set_instructions(s, req)
    if isinstance(req, ExportSpec):
        editor, site = _site(s, req.agent)
        return editor.export_spec(s, site, req)
    raise EditError(f"unknown operation {req!r}")


# ---------------------------------------------------------------------- connect


def _connect(s: Session, req: Connect) -> str:
    source = s.node(req.source, "agent")
    target = s.node(req.target, "agent")
    if source.id == target.id:
        raise EditError("An agent cannot hand work to itself.")
    if source.framework != target.framework:
        raise EditError(f"`{source.name}` and `{target.name}` use different frameworks.")
    tools = {e.target for e in s.project.edges if e.source == source.id and e.kind == "uses"}
    for e in s.project.edges:
        if e.target == target.id and (e.source == source.id or (e.source in tools and e.kind == "delegates_to")):
            raise EditError(f"`{source.name}` already hands work to `{target.name}`.")
    editor = _editor(source.framework)
    return editor.connect(s, s.agent(source.id, editor.agent_classes), s.agent(target.id, editor.agent_classes), req)


# ---------------------------------------------------------------------- disconnect and remove


def _contains(outer: Range, inner: Range) -> bool:
    return (outer.start.line, outer.start.column) <= (inner.start.line, inner.start.column) and (
        inner.end.line,
        inner.end.column,
    ) <= (outer.end.line, outer.end.column)


def remove_reference(doc: Doc, rng: Range) -> bool:
    """Remove the code that writes a relation: a list element, a decorator, or a statement that
    exists only for it (``crm.add_function(f)``). False if it is something else (a call inside a
    function body, a keyword flag…)."""
    candidates = [n for n, pos in doc.positions.items() if _same_range(pos, rng)]
    for node in candidates:
        if isinstance(node, cst.Decorator):
            fn = doc.parent(node)
            if isinstance(fn, cst.FunctionDef):
                doc.remove_decorator(fn, list(fn.decorators).index(node))
                return True
    for node in candidates:
        found = _list_element(doc, node)
        if found is not None:
            seq, index = found
            doc.remove_element(seq, index)
            return True
    for node in candidates:
        if isinstance(node, cst.Call):
            expr = doc.parent(node)
            line = doc.parent(expr) if isinstance(expr, cst.Expr) else None
            if isinstance(line, cst.SimpleStatementLine) and len(line.body) == 1 and doc.parent(line) is doc.tree:
                doc.delete(doc.tree.body.index(line))
                return True
    return False


def _same_range(pos, rng: Range) -> bool:
    return (pos.start.line, pos.start.column, pos.end.line, pos.end.column) == (
        rng.start.line,
        rng.start.column,
        rng.end.line,
        rng.end.column,
    )


def _list_element(doc: Doc, node: cst.CSTNode) -> tuple[cst.List | cst.Tuple | cst.Set, int] | None:
    """The list literal item that ``node`` is (or that wraps it as ``Toolset(node)``)."""
    current = node
    for _ in range(6):
        if isinstance(current, cst.Element | cst.StarredElement):
            seq = doc.parent(current)
            if isinstance(seq, cst.List | cst.Tuple | cst.Set):
                return seq, list(seq.elements).index(current)
            return None
        parent = doc.parent(current)
        if isinstance(parent, cst.Element | cst.StarredElement):
            current = parent
            continue
        if isinstance(parent, cst.Arg) or (isinstance(parent, cst.Call) and isinstance(current, cst.Arg)):
            current = parent
            continue
        return None
    return None


def _disconnect(s: Session, req: Disconnect) -> str:
    edge = s.edge(req.edge)
    src, tgt = s.name_of(edge.source), s.name_of(edge.target)
    if edge.kind in ("contains", "transitions"):
        raise EditError("pydantic-graph flows are edited in code: change the step's return type or the builder.")
    if edge.ref is None:
        raise EditError(f"`{src}` → `{tgt}` is not written anywhere that can be edited.")
    source = s.project.node(edge.source)
    if (
        source is not None
        and source.status == "partial"
        and source.source is not None
        and not (source.source.file == edge.ref.file and _contains(source.source.range, edge.ref.range))
    ):
        raise EditError(f"`{src}` gets `{tgt}` from the function that builds it; edit that function.")
    doc = s.doc(edge.ref.file)
    if not remove_reference(doc, edge.ref.range):
        if edge.kind in ("delegates_to", "runs"):
            raise EditError(
                f"`{src}` runs `{tgt}` inside its code ({edge.ref.file}:{edge.ref.range.start.line});"
                f" remove `{src}` or edit its body."
            )
        raise EditError(f"`{src}` → `{tgt}` is not a list item or decorator; edit {edge.ref.file} by hand.")
    return f"Disconnected `{src}` from `{tgt}` in {edge.ref.file}."


def _top_def(doc: Doc, node: cst.CSTNode) -> int | None:
    index = doc.top_index(node)
    return index if index is not None and doc.tree.body[index] is node else None


def _registered(fn: cst.FunctionDef | cst.ClassDef) -> bool:
    """Decorated as ``@x.tool``: the function exists to be registered on ``x``."""
    for d in fn.decorators:
        expr = d.decorator.func if isinstance(d.decorator, cst.Call) else d.decorator
        if isinstance(expr, cst.Attribute):
            return True
    return False


def _remove(s: Session, req: Remove) -> str:
    node = s.node(req.node)
    if node.kind in ("graph", "graph_step", "workflow"):
        raise EditError(f"{node.kind.replace('_', ' ').capitalize()}s are edited in code.")
    if node.kind == "agent":
        return _remove_agent(s, node.id)
    removed = False
    for e in s.project.edges:
        if e.target == node.id and e.ref is not None:
            removed = remove_reference(s.doc(e.ref.file), e.ref.range) or removed
    if node.source is not None and node.kind != "dynamic":
        doc = s.doc(node.source.file)
        definition = doc.at(node.source.range, (cst.FunctionDef, cst.ClassDef, cst.Call))
        if isinstance(definition, cst.FunctionDef | cst.ClassDef):
            index = _top_def(doc, definition)
            name = definition.name.value
            bound = _registered(definition)
            if index is not None:
                doc.removed.add(definition)
                used = doc.name_uses(name) or s.other_modules_importing(doc, name)
                if bound or node.status == "planned" or not used:
                    doc.delete(index)
                    removed = True
                else:
                    doc.removed.discard(definition)
                    s.notes.append(f"`{name}` is still used elsewhere, so its definition was kept.")
        elif isinstance(definition, cst.Call):
            parent = doc.parent(definition)
            line = doc.parent(parent) if isinstance(parent, cst.Assign) else None
            if (
                isinstance(parent, cst.Assign)
                and len(parent.targets) == 1
                and isinstance(parent.targets[0].target, cst.Name)
                and isinstance(line, cst.SimpleStatementLine)
                and doc.parent(line) is doc.tree
            ):
                var = parent.targets[0].target.value
                if not doc.name_uses(var) and not s.other_modules_importing(doc, var):
                    doc.delete(doc.tree.body.index(line))
                    removed = True
                elif not removed:
                    raise EditError(f"`{var}` is used in {doc.rel} in ways the diagram cannot edit.")
            elif not removed:
                removed = remove_reference(doc, node.source.range)
    if not removed:
        raise EditError(f"`{node.name}` cannot be removed from the diagram; edit the code by hand.")
    return f"Removed `{node.name}`."


def _remove_agent(s: Session, node_id: str) -> str:
    _, site = _site(s, node_id)
    index = site.require_top("remove it")
    doc, var = site.doc, site.var
    assert var is not None
    stmt = doc.tree.body[index]
    if not isinstance(stmt, cst.SimpleStatementLine):
        raise EditError(f"`{site.node.name}` is defined inside a block; remove it by hand.")
    blockers: dict[str, str] = {}  # where -> why
    for e in s.project.edges:
        if e.target != node_id:
            continue
        if e.ref is None or not remove_reference(s.doc(e.ref.file), e.ref.range):
            where = f"{e.ref.file}:{e.ref.range.start.line}" if e.ref else "?"
            blockers[where] = f"`{s.name_of(e.source)}` runs it ({where})"
    helpers = []
    for i, top in enumerate(doc.tree.body):
        if isinstance(top, cst.FunctionDef) and any(bound_decorator(d, var) for d in top.decorators):
            doc.delete(i)
            helpers.append(top.name.value)
    doc.delete(index)
    for use in doc.name_uses(var):
        where = f"{doc.rel}:{doc.line(use)}"
        blockers.setdefault(where, f"it is used at {where}")
    for rel in s.other_modules_importing(doc, var):
        blockers.setdefault(rel, f"{rel} imports it")
    if blockers:
        reasons = "; ".join(list(blockers.values())[:4])
        raise EditError(f"`{site.node.name}` is still needed: {reasons}. Remove those first.")
    extra = f" and its functions {', '.join(f'`{h}`' for h in helpers)}" if helpers else ""
    return f"Removed `{site.node.name}`{extra}."


# ---------------------------------------------------------------------- instructions


def _set_instructions(s: Session, req: SetInstructions) -> str:
    _, site = _site(s, req.agent)
    text = req.instructions.strip()
    doc = site.doc
    if text:
        value = doc.parse_expr(py_string(text))
        doc.update(site.call, lambda c: set_arg(c, "instructions", value))
        s.focus = site.node.id
        return f"Updated the instructions of `{site.node.name}`."
    doc.update(site.call, lambda c: remove_arg(c, "instructions"))
    s.focus = site.node.id
    return f"Removed the instructions of `{site.node.name}`."
