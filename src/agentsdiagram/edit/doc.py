"""One Python file being edited: locate CST nodes by IR range, queue changes, render the new text.

Changes are queued against the *original* tree and applied in one pass at the end, so every
position and index computed on the original stays valid while an operation builds up:

- ``update(node, fn)``: ``fn`` rewrites the node structurally (it receives the node with its
  children already updated, so nested updates compose);
- ``remove_element`` / ``remove_decorator``: drop an item of a list literal or a decorator;
- ``insert_before`` / ``insert_after`` / ``append`` / ``delete``: module-level statements, by index;
- ``add_import``: merged into an existing ``from x import ...`` when there is one.

LibCST round-trips source exactly, so everything that is not touched keeps its formatting.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import libcst as cst
from libcst.metadata import CodeRange, MetadataWrapper, ParentNodeProvider, PositionProvider

from ..ir import Range

N = TypeVar("N", bound=cst.CSTNode)


class EditError(Exception):
    """The request cannot be applied; the message is shown to the user as is."""


@dataclass
class _Insert:
    index: int  # original top-level index; -1 means "at the top"
    after: bool
    stmts: list[cst.BaseStatement]


@dataclass
class Doc:
    path: Path
    rel: str
    module: str  # dotted module name
    before: str | None  # None: the file does not exist yet
    tree: cst.Module = field(init=False)
    positions: Any = field(init=False, repr=False)
    parents: Any = field(init=False, repr=False)
    _updates: dict[cst.CSTNode, list[Callable[[Any], Any]]] = field(default_factory=dict, repr=False)
    _removed_elements: dict[cst.CSTNode, set[int]] = field(default_factory=dict, repr=False)
    _removed_decorators: dict[cst.FunctionDef, set[int]] = field(default_factory=dict, repr=False)
    _inserts: list[_Insert] = field(default_factory=list, repr=False)
    _deletes: set[int] = field(default_factory=set, repr=False)
    _imports: list[tuple[str, str]] = field(default_factory=list, repr=False)
    removed: set[cst.CSTNode] = field(default_factory=set, repr=False)  # original subtrees going away

    def __post_init__(self) -> None:
        try:
            tree = cst.parse_module(self.before or "")
        except cst.ParserSyntaxError as exc:
            raise EditError(f"{self.rel} has a syntax error; fix it before editing from the diagram.") from exc
        wrapper = MetadataWrapper(tree, unsafe_skip_copy=True)
        self.tree = tree
        self.positions = wrapper.resolve(PositionProvider)
        self.parents = wrapper.resolve(ParentNodeProvider)

    # ------------------------------------------------------------------ reading

    @property
    def changed(self) -> bool:
        return bool(
            self._updates
            or self._removed_elements
            or self._removed_decorators
            or self._inserts
            or self._deletes
            or self._imports
            or self.before is None
        )

    def code(self, node: cst.CSTNode) -> str:
        return self.tree.code_for_node(node)

    def at(self, rng: Range, types: type | tuple[type, ...] = cst.CSTNode) -> cst.CSTNode | None:
        """The node whose position is exactly ``rng`` (the outermost one, if several share it)."""
        best = None
        for node, pos in self.positions.items():
            if _same(pos, rng) and isinstance(node, types):
                if best is None or _is_ancestor(self, node, best):
                    best = node
        return best

    def parent(self, node: cst.CSTNode) -> cst.CSTNode | None:
        return self.parents.get(node)

    def line(self, node: cst.CSTNode) -> int:
        return self.positions[node].start.line

    def top_index(self, node: cst.CSTNode) -> int | None:
        """Index in ``tree.body`` of the module-level statement that contains ``node``."""
        current: cst.CSTNode | None = node
        while current is not None:
            parent = self.parents.get(current)
            if parent is self.tree:
                return self.tree.body.index(current)  # type: ignore[arg-type]
            current = parent
        return None

    def top_names(self) -> set[str]:
        """Names bound at module level (assignments, defs, classes, imports)."""
        names: set[str] = set()
        for stmt in self.tree.body:
            if isinstance(stmt, cst.FunctionDef | cst.ClassDef):
                names.add(stmt.name.value)
            elif isinstance(stmt, cst.SimpleStatementLine):
                for small in stmt.body:
                    if isinstance(small, cst.Assign):
                        names.update(t.target.value for t in small.targets if isinstance(t.target, cst.Name))
                    elif isinstance(small, cst.AnnAssign) and isinstance(small.target, cst.Name):
                        names.add(small.target.value)
                    elif isinstance(small, cst.Import | cst.ImportFrom) and not isinstance(small.names, cst.ImportStar):
                        for alias in small.names:
                            bound = alias.asname.name if alias.asname else alias.name
                            if isinstance(bound, cst.Name):
                                names.add(bound.value)
                            elif isinstance(bound, cst.Attribute):
                                names.add(self.code(bound).split(".", 1)[0])
            elif isinstance(stmt, cst.With):
                for item in stmt.items:
                    if item.asname is not None and isinstance(item.asname.name, cst.Name):
                        names.add(item.asname.name.value)
        return names

    def name_uses(self, name: str) -> list[cst.Name]:
        """``Name`` nodes reading ``name`` outside the subtrees queued for removal."""
        found: list[cst.Name] = []
        for node in self.positions:
            if not (isinstance(node, cst.Name) and node.value == name):
                continue
            parent = self.parents.get(node)
            # the name being defined is not a use
            if isinstance(parent, cst.FunctionDef | cst.ClassDef) and parent.name is node:
                continue
            if isinstance(parent, cst.AssignTarget) and parent.target is node:
                continue
            if isinstance(parent, cst.Attribute) and parent.attr is node:
                continue
            if isinstance(parent, cst.Arg) and parent.keyword is node:
                continue
            if any(a in self.removed for a in self._ancestors(node)):
                continue
            found.append(node)
        return found

    def _ancestors(self, node: cst.CSTNode):
        current = self.parents.get(node)
        while current is not None:
            yield current
            current = self.parents.get(current)

    def parse_expr(self, code: str) -> cst.BaseExpression:
        return cst.parse_expression(code, config=self.tree.config_for_parsing)

    def parse_stmts(self, code: str) -> list[cst.BaseStatement]:
        return list(cst.parse_module(code, config=self.tree.config_for_parsing).body)

    # ------------------------------------------------------------------ queueing changes

    def update(self, node: N, fn: Callable[[N], N]) -> None:
        self._updates.setdefault(node, []).append(fn)

    def remove_element(self, seq: cst.List | cst.Tuple | cst.Set, index: int) -> None:
        self._removed_elements.setdefault(seq, set()).add(index)
        self.removed.add(seq.elements[index])

    def remove_decorator(self, fn: cst.FunctionDef, index: int) -> None:
        self._removed_decorators.setdefault(fn, set()).add(index)
        self.removed.add(fn.decorators[index])

    def insert_before(self, index: int, stmts: Sequence[cst.BaseStatement]) -> None:
        self._inserts.append(_Insert(index, False, list(stmts)))

    def insert_after(self, index: int, stmts: Sequence[cst.BaseStatement]) -> None:
        self._inserts.append(_Insert(index, True, list(stmts)))

    def append(self, stmts: Sequence[cst.BaseStatement]) -> None:
        """At the end of the module, but before an ``if __name__ == "__main__":`` block."""
        body = self.tree.body
        index = len(body) - 1
        while index >= 0 and _is_main_guard(body[index]):
            index -= 1
        if index < 0:
            self._inserts.append(_Insert(-1, True, list(stmts)))
        else:
            self.insert_after(index, stmts)

    def delete(self, index: int) -> None:
        self._deletes.add(index)
        self.removed.add(self.tree.body[index])

    def add_import(self, module: str, name: str) -> None:
        """``from module import name`` (``module`` may be relative, e.g. ``.tools``)."""
        if (module, name) not in self._imports:
            self._imports.append((module, name))

    # ------------------------------------------------------------------ rendering

    def render(self) -> str:
        for seq, indexes in self._removed_elements.items():
            self.update(seq, lambda s, idx=frozenset(indexes): _without_elements(s, idx))
        for fn, indexes in self._removed_decorators.items():
            self.update(
                fn,
                lambda f, idx=frozenset(indexes): f.with_changes(
                    decorators=[d for i, d in enumerate(f.decorators) if i not in idx]
                ),
            )
        updates = self._updates

        class _Apply(cst.CSTTransformer):
            def on_leave(self, original_node, updated_node):  # type: ignore[override]
                for fn in updates.get(original_node, ()):
                    updated_node = fn(updated_node)
                return updated_node

        tree = self.tree.visit(_Apply()) if updates else self.tree
        body: list[cst.BaseStatement | None] = list(tree.body)  # type: ignore[arg-type]
        for i in self._deletes:  # placeholders keep the original indexes valid for the inserts
            body[i] = None
        top: list[cst.BaseStatement] = []
        order = sorted(enumerate(self._inserts), key=lambda p: (p[1].index, p[1].after, p[0]), reverse=True)
        for _, ins in order:
            if ins.index == -1:
                top = [*ins.stmts, *top]
                continue
            target = body[ins.index]
            if ins.after:
                follower = _next(body, ins.index + 1)
                if follower is not None:
                    i, stmt = follower
                    body[i] = _with_blank_lines(stmt, _gap(ins.stmts[-1], stmt), at_least=True)
                stmts = list(ins.stmts)
                if target is not None:
                    stmts[0] = _with_blank_lines(stmts[0], _gap(target, stmts[0]))
                body[ins.index + 1 : ins.index + 1] = stmts
            elif target is None:
                body[ins.index : ins.index] = list(ins.stmts)
            else:
                blanks, rest = _split_leading(target)
                first = ins.stmts[0].with_changes(leading_lines=[*blanks, *_leading(ins.stmts[0])])
                previous = _previous(body, ins.index - 1)
                if previous is not None:
                    first = _with_blank_lines(first, _gap(previous, first), at_least=True)
                target = target.with_changes(leading_lines=[*[cst.EmptyLine()] * _gap(ins.stmts[-1], target), *rest])
                body[ins.index : ins.index + 1] = [first, *ins.stmts[1:], target]
        new_body = [s for s in body if s is not None]
        if 0 in self._deletes and new_body:
            new_body[0] = new_body[0].with_changes(leading_lines=_leading(new_body[0], keep_blank=False))
        if top:
            if new_body:
                new_body[0] = _with_blank_lines(new_body[0], _gap(top[-1], new_body[0]))
            new_body = [top[0].with_changes(leading_lines=_leading(top[0], keep_blank=False)), *top[1:], *new_body]
        tree = tree.with_changes(body=new_body)
        for module, name in self._imports:
            tree = _ensure_import(tree, module, name)
        tree = _prune_imports(self.tree, tree)
        code = tree.code
        if code and not code.endswith(tree.default_newline):
            code += tree.default_newline
        return code


# ---------------------------------------------------------------------- sequences


def _same(pos: CodeRange, rng: Range) -> bool:
    return (pos.start.line, pos.start.column, pos.end.line, pos.end.column) == (
        rng.start.line,
        rng.start.column,
        rng.end.line,
        rng.end.column,
    )


def _is_ancestor(doc: Doc, a: cst.CSTNode, b: cst.CSTNode) -> bool:
    return a in set(doc._ancestors(b))


def _move_trailing_ws(src: Any, dst: Any) -> tuple[Any, Any]:
    """For call arguments: whitespace between the last argument and ``)`` lives on the argument."""
    if isinstance(src, cst.Arg) and isinstance(dst, cst.Arg):
        return src.with_changes(whitespace_after_arg=cst.SimpleWhitespace("")), dst.with_changes(
            whitespace_after_arg=src.whitespace_after_arg
        )
    return src, dst


def append_item(items: Sequence[Any], new: Any, opening: Any) -> list[Any]:
    """Append ``new`` to list elements or call arguments, copying the separator style.

    ``opening`` is the whitespace after the opening bracket: on a multi-line literal the new
    item goes on its own line with the same indentation.
    """
    if not items:
        return [new.with_changes(comma=cst.MaybeSentinel.DEFAULT)]
    last = items[-1]
    if len(items) >= 2 and isinstance(items[-2].comma, cst.Comma):
        sep = items[-2].comma
    elif isinstance(opening, cst.ParenthesizedWhitespace):
        sep = cst.Comma(whitespace_after=opening)
    else:
        sep = cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
    last, new = _move_trailing_ws(last, new)
    return [*items[:-1], last.with_changes(comma=sep), new.with_changes(comma=last.comma)]


def prepend_item(items: Sequence[Any], new: Any) -> list[Any]:
    if not items:
        return [new]
    first = items[0]
    sep = first.comma if isinstance(first.comma, cst.Comma) else cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
    return [new.with_changes(comma=sep), *items]


def remove_items(items: Sequence[Any], indexes: frozenset[int] | set[int]) -> list[Any]:
    kept = [it for i, it in enumerate(items) if i not in indexes]
    if not kept or len(kept) == len(items):
        return kept
    last_index = len(items) - 1
    if last_index in indexes:  # the new last item inherits the removed last one's comma/whitespace
        old_last = items[last_index]
        new_last = kept[-1]
        old_last, new_last = _move_trailing_ws(old_last, new_last)
        kept[-1] = new_last.with_changes(comma=old_last.comma)
    return kept


def _without_elements(seq: Any, indexes: frozenset[int]) -> Any:
    elements = remove_items(seq.elements, indexes)
    if not elements:
        if isinstance(seq, cst.List):
            return cst.List([])
        if isinstance(seq, cst.Tuple):
            return cst.Tuple([])
        return cst.Call(func=cst.Name("set"))
    return seq.with_changes(elements=elements)


def opening_ws(node: cst.List | cst.Tuple | cst.Set | cst.Call) -> Any:
    if isinstance(node, cst.Call):
        return node.whitespace_before_args
    if isinstance(node, cst.List):
        return node.lbracket.whitespace_after
    if isinstance(node, cst.Set):
        return node.lbrace.whitespace_after
    return node.lpar[0].whitespace_after if node.lpar else cst.SimpleWhitespace("")


# ---------------------------------------------------------------------- call arguments


def find_arg(call: cst.Call, keyword: str, position: int | None = None) -> int | None:
    """Index in ``call.args`` of the argument passed as ``keyword=`` or at ``position``."""
    for i, a in enumerate(call.args):
        if a.keyword is not None and a.keyword.value == keyword:
            return i
    if position is not None:
        positional = [i for i, a in enumerate(call.args) if a.keyword is None and not a.star]
        if len(positional) > position:
            return positional[position]
    return None


def kwarg(name: str, value: cst.BaseExpression) -> cst.Arg:
    return cst.Arg(
        value=value,
        keyword=cst.Name(name),
        equal=cst.AssignEqual(cst.SimpleWhitespace(""), cst.SimpleWhitespace("")),
    )


def set_arg(call: cst.Call, keyword: str, value: cst.BaseExpression, position: int | None = None) -> cst.Call:
    i = find_arg(call, keyword, position)
    if i is not None:
        args = list(call.args)
        args[i] = args[i].with_changes(value=value)
        return call.with_changes(args=args)
    return call.with_changes(args=append_item(call.args, kwarg(keyword, value), call.whitespace_before_args))


def remove_arg(call: cst.Call, keyword: str) -> cst.Call:
    i = find_arg(call, keyword)
    if i is None:
        return call
    args = remove_items(call.args, {i})
    if not args:
        return call.with_changes(args=[], whitespace_before_args=cst.SimpleWhitespace(""))
    return call.with_changes(args=args)


def append_to_arg(call: cst.Call, keyword: str, element: cst.BaseElement, position: int | None = None) -> cst.Call:
    """``keyword=[..., element]``: extend a list literal, wrap another expression, or add the argument."""
    i = find_arg(call, keyword, position)
    if i is None:
        return call.with_changes(
            args=append_item(call.args, kwarg(keyword, cst.List([element])), call.whitespace_before_args)
        )
    value = call.args[i].value
    if isinstance(value, cst.List | cst.Tuple):
        new_value = value.with_changes(elements=append_item(value.elements, element, opening_ws(value)))
        if isinstance(value, cst.Tuple) and not value.lpar:
            new_value = new_value.with_changes(lpar=[cst.LeftParen()], rpar=[cst.RightParen()])
    else:
        new_value = cst.List([cst.StarredElement(value=value), element])
    args = list(call.args)
    args[i] = args[i].with_changes(value=new_value)
    return call.with_changes(args=args)


def element(code_or_expr: cst.BaseExpression) -> cst.Element:
    return cst.Element(value=code_or_expr)


# ---------------------------------------------------------------------- statements and blank lines


def _is_def(stmt: cst.CSTNode) -> bool:
    return isinstance(stmt, cst.FunctionDef | cst.ClassDef)


def _gap(a: cst.CSTNode, b: cst.CSTNode) -> int:
    """Blank lines between two module-level statements (PEP 8: two around definitions)."""
    return 2 if _is_def(a) or _is_def(b) else 1


def _leading(stmt: cst.BaseStatement, keep_blank: bool = True) -> list[cst.EmptyLine]:
    lines = list(getattr(stmt, "leading_lines", []))
    if keep_blank:
        return lines
    while lines and lines[0].comment is None:
        lines.pop(0)
    return lines


def _split_leading(stmt: cst.BaseStatement) -> tuple[list[cst.EmptyLine], list[cst.EmptyLine]]:
    lines = list(getattr(stmt, "leading_lines", []))
    i = 0
    while i < len(lines) and lines[i].comment is None:
        i += 1
    return lines[:i], lines[i:]


def _with_blank_lines(stmt: Any, n: int, at_least: bool = False) -> Any:
    blanks, rest = _split_leading(stmt)
    count = max(n, len(blanks)) if at_least else n
    return stmt.with_changes(leading_lines=[*[cst.EmptyLine()] * count, *rest])


def _next(body: list[Any], start: int) -> tuple[int, Any] | None:
    for i in range(start, len(body)):
        if body[i] is not None:
            return i, body[i]
    return None


def _previous(body: list[Any], start: int) -> Any:
    for i in range(start, -1, -1):
        if body[i] is not None:
            return body[i]
    return None


def _is_main_guard(stmt: cst.CSTNode) -> bool:
    return isinstance(stmt, cst.If) and "__name__" in cst.Module([]).code_for_node(stmt.test)


def with_marker(stmts: list[cst.BaseStatement], comment: str) -> list[cst.BaseStatement]:
    first = stmts[0]
    lines = [*_leading(first), cst.EmptyLine(comment=cst.Comment(comment))]
    return [first.with_changes(leading_lines=lines), *stmts[1:]]


# ---------------------------------------------------------------------- imports


def _alias_name(alias: cst.ImportAlias) -> str:
    bound = alias.asname.name if alias.asname else alias.name
    return cst.Module([]).code_for_node(bound)


def _from_module(node: cst.ImportFrom) -> str:
    dots = "." * len(node.relative)
    return dots + (cst.Module([]).code_for_node(node.module) if node.module else "")


def _sort_key(name: str) -> tuple[int, str]:
    """isort/ruff ``order-by-type``: CONSTANTS, then Classes, then functions."""
    if name.isupper() and len(name) > 1:
        return (0, name)
    if name[:1].isupper():
        return (1, name)
    return (2, name)


def _section(module: str) -> int:
    """isort sections: __future__, standard library, third party, local (relative)."""
    if module.startswith("."):
        return 3
    head = module.split(".", 1)[0]
    if head == "__future__":
        return 0
    return 1 if head in sys.stdlib_module_names else 2


def _merge_names(stmt: cst.SimpleStatementLine, small: cst.ImportFrom, name: str) -> cst.SimpleStatementLine | None:
    names = list(small.names)  # type: ignore[arg-type]
    if any(_alias_name(a) == name for a in names):
        return None
    new_alias = cst.ImportAlias(name=cst.Name(name))
    keys = [_sort_key(_alias_name(a)) for a in names]
    position = len(names)
    if keys == sorted(keys):
        position = next((j for j, k in enumerate(keys) if k > _sort_key(name)), len(names))
    if position == len(names):
        opening = small.lpar.whitespace_after if small.lpar else cst.SimpleWhitespace("")
        new_names = append_item(names, new_alias, opening)
    else:
        sep = names[position].comma if position < len(names) - 1 else None
        if not isinstance(sep, cst.Comma):
            sep = names[0].comma if isinstance(names[0].comma, cst.Comma) and len(names) > 1 else None
        sep = sep or cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
        new_names = [*names[:position], new_alias.with_changes(comma=sep), *names[position:]]
    return stmt.with_changes(body=[small.with_changes(names=new_names), *stmt.body[1:]])


def _ensure_import(tree: cst.Module, module: str, name: str) -> cst.Module:
    body = list(tree.body)
    imports: list[tuple[int, int, bool, str]] = []  # (index, section, is_from, module)
    start = 0
    while start < len(body) and _is_docstring(body[start]):
        start += 1
    for i in range(start, len(body)):
        stmt = body[i]
        small = stmt.body[0] if isinstance(stmt, cst.SimpleStatementLine) and stmt.body else None
        if isinstance(small, cst.ImportFrom):
            mod = _from_module(small)
            if mod == module and not isinstance(small.names, cst.ImportStar):
                merged = _merge_names(stmt, small, name)  # type: ignore[arg-type]
                if merged is None:
                    return tree
                body[i] = merged
                return tree.with_changes(body=body)
            imports.append((i, _section(mod), True, mod))
        elif isinstance(small, cst.Import):
            mod = cst.Module([]).code_for_node(small.names[0].name)
            imports.append((i, _section(mod), False, mod))
        else:
            break
    new = cst.parse_statement(f"from {module} import {name}\n", config=tree.config_for_parsing)
    section = _section(module)
    same = [imp for imp in imports if imp[1] == section]
    if same:  # inside its group, sorted by module among the `from` imports
        later = [imp for imp in same if imp[2] and imp[3].lower() > module.lower()]
        if later:
            index = later[0][0]
            blanks, rest = _split_leading(body[index])
            body[index] = body[index].with_changes(leading_lines=rest)
            body.insert(index, new.with_changes(leading_lines=blanks))
        else:
            body.insert(same[-1][0] + 1, new)
        return tree.with_changes(body=body)
    after = [imp for imp in imports if imp[1] > section]
    if after:  # a new group before the next one
        index = after[0][0]
        target = body[index]
        blanks, rest = _split_leading(target)
        body[index] = target.with_changes(leading_lines=[cst.EmptyLine(), *rest])
        body.insert(index, new.with_changes(leading_lines=blanks))
    elif imports:  # a new group after the last one
        body.insert(imports[-1][0] + 1, new.with_changes(leading_lines=[cst.EmptyLine()]))
    else:
        if start:
            new = new.with_changes(leading_lines=[cst.EmptyLine()])
        if start < len(body):
            body[start] = _with_blank_lines(body[start], 2 if _is_def(body[start]) else 1, at_least=True)
        body.insert(start, new)
    return tree.with_changes(body=body)


class _Uses(cst.CSTVisitor):
    """Names read outside import statements."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Import(self, node: cst.Import) -> bool:
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        return False

    def visit_Name(self, node: cst.Name) -> None:
        self.names.add(node.value)


def _uses(tree: cst.Module) -> set[str]:
    v = _Uses()
    tree.visit(v)
    return v.names


def _prune_imports(before: cst.Module, after: cst.Module) -> cst.Module:
    """Drop imports that the edit made unused (an import that was already unused stays)."""
    gone = _uses(before) - _uses(after)
    if not gone:
        return after
    body = list(after.body)
    changed = False
    for i, stmt in enumerate(body):
        if not isinstance(stmt, cst.SimpleStatementLine) or len(stmt.body) != 1:
            continue
        small = stmt.body[0]
        if not isinstance(small, cst.Import | cst.ImportFrom) or isinstance(small.names, cst.ImportStar):
            continue
        names = list(small.names)
        drop = {j for j, a in enumerate(names) if _alias_name(a).split(".", 1)[0] in gone}
        if not drop:
            continue
        changed = True
        kept = remove_items(names, drop)
        if kept:
            body[i] = stmt.with_changes(body=[small.with_changes(names=kept)])
            continue
        body[i] = None  # type: ignore[call-overload]
        follower = _next(body, i + 1)
        if follower is not None:
            j, nxt = follower
            blanks, _ = _split_leading(stmt)
            own, rest = _split_leading(nxt)
            if not own and blanks:
                body[j] = nxt.with_changes(leading_lines=[*blanks, *rest])
    if not changed:
        return after
    return after.with_changes(body=[s for s in body if s is not None])


def _is_docstring(stmt: cst.CSTNode) -> bool:
    return (
        isinstance(stmt, cst.SimpleStatementLine)
        and len(stmt.body) == 1
        and isinstance(stmt.body[0], cst.Expr)
        and isinstance(stmt.body[0].value, cst.SimpleString | cst.ConcatenatedString)
    )
