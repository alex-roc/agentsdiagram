"""State shared by the operations of one edit: the analysed project and the files being changed."""

from __future__ import annotations

import hashlib
import json
import keyword
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst

from ..analyze import Cache, analyze
from ..ir import Edge, Node, Project
from ..project import collect, module_name
from .doc import Doc, EditError


@dataclass
class Change:
    path: Path
    rel: str
    before: str | None  # None: new file
    after: str


def py_string(text: str) -> str:
    """A double-quoted Python string literal (JSON escapes are valid Python escapes)."""
    return json.dumps(text, ensure_ascii=False)


def identifier(name: str, what: str = "name") -> str:
    name = name.strip()
    if not name.isidentifier() or keyword.iskeyword(name):
        raise EditError(f"`{name}` is not a valid Python {what}.")
    return name


def humanize(name: str) -> str:
    words = name.replace("_", " ").strip()
    return (words[:1].upper() + words[1:]) if words else name


@dataclass
class AgentSite:
    """Where an agent is written: its file, its constructor call and module-level statement."""

    node: Node
    doc: Doc
    call: cst.Call
    index: int | None  # module-level statement index (None if not at module level)
    var: str | None  # variable bound to the agent

    def require_top(self, action: str) -> int:
        if self.index is None or self.var is None:
            raise EditError(f"`{self.node.name}` is not assigned to a variable at module level; {action} by hand.")
        return self.index


@dataclass
class Session:
    root: Path
    project: Project
    overrides: dict[Path, str] = field(default_factory=dict)
    docs: dict[str, Doc] = field(default_factory=dict)
    focus: str | None = None
    notes: list[str] = field(default_factory=list)
    extra_files: dict[str, str] = field(default_factory=dict)  # non-Python files to write (Agent Specs)

    @classmethod
    def open(cls, root: Path, *, overrides: dict[Path, str] | None = None, cache: Cache | None = None) -> Session:
        overrides = {p.resolve(): t for p, t in (overrides or {}).items()}
        project = analyze(root, overrides=overrides, cache=cache)
        return cls(root=Path(project.root), project=project, overrides=overrides)

    # ------------------------------------------------------------------ files

    def read(self, rel: str) -> str | None:
        path = (self.root / rel).resolve()
        if path in self.overrides:
            return self.overrides[path]
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise EditError(f"cannot read {rel}: {exc}") from exc

    def sha(self, rel: str) -> str | None:
        text = self.read(rel)
        return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None

    def check_expect(self, expect: dict[str, str]) -> None:
        changed = [rel for rel, sha in expect.items() if self.sha(rel) != sha]
        if changed:
            raise EditError(
                f"{', '.join(changed)} changed since the diagram was drawn; nothing was written. Try again."
            )

    def doc(self, rel: str, *, create: bool = False) -> Doc:
        rel = Path(rel).as_posix()
        if rel in self.docs:
            return self.docs[rel]
        path = (self.root / rel).resolve()
        if not path.is_relative_to(self.root):
            raise EditError(f"{rel} is outside the project ({self.root}).")
        if path.suffix != ".py":
            raise EditError(f"{rel} is not a Python file.")
        text = self.read(rel)
        if text is None and not create:
            raise EditError(f"{rel} does not exist.")
        doc = Doc(path=path, rel=rel, module=module_name(self.root, path), before=text)
        self.docs[rel] = doc
        return doc

    def changes(self) -> list[Change]:
        out: list[Change] = []
        for rel, doc in self.docs.items():
            if not doc.changed:
                continue
            after = doc.render()
            try:
                cst.parse_module(after)
            except cst.ParserSyntaxError as exc:  # a bug in an operation, never the user's fault
                raise EditError(f"internal error: the edit of {rel} would not parse ({exc.message}).") from exc
            if after != doc.before:
                out.append(Change(doc.path, rel, doc.before, after))
        for rel, text in self.extra_files.items():
            path = (self.root / rel).resolve()
            before = self.read(rel)
            if before != text:
                out.append(Change(path, rel, before, text))
        return out

    # ------------------------------------------------------------------ graph

    def node(self, node_id: str, kind: str | None = None) -> Node:
        node = self.project.node(node_id)
        if node is None:
            raise EditError(f"`{node_id}` is not in the diagram (any more); refresh and try again.")
        if kind is not None and node.kind != kind:
            raise EditError(f"`{node.name}` is a {node.kind.replace('_', ' ')}, not an {kind}.")
        return node

    def edge(self, edge_id: str) -> Edge:
        found = next((e for e in self.project.edges if e.id == edge_id), None)
        if found is None:
            raise EditError(f"`{edge_id}` is not in the diagram (any more); refresh and try again.")
        return found

    def name_of(self, node_id: str) -> str:
        n = self.project.node(node_id)
        return n.name if n else node_id

    def agent(self, node_id: str, classes: set[str]) -> AgentSite:
        node = self.node(node_id, "agent")
        if node.status == "stale":
            raise EditError(f"{node.source.file if node.source else 'the file'} has a syntax error; fix it first.")
        if node.source is None:
            raise EditError(f"`{node.name}` has no source location.")
        doc = self.doc(node.source.file)
        call = doc.at(node.source.range, cst.Call)
        if not isinstance(call, cst.Call):
            raise EditError(f"cannot find `{node.name}` in {node.source.file}; refresh and try again.")
        func = doc.code(call.func).rsplit(".", 1)[-1]
        if func not in classes:
            raise EditError(
                f"`{node.name}` is built by `{doc.code(call.func)}(...)`, not by `{'/'.join(sorted(classes))}`;"
                " edit that function instead."
            )
        index = doc.top_index(call)
        var = None
        parent = doc.parent(call)
        if isinstance(parent, cst.Assign) and len(parent.targets) == 1:
            target = parent.targets[0].target
            var = target.value if isinstance(target, cst.Name) else None
        elif isinstance(parent, cst.AnnAssign) and isinstance(parent.target, cst.Name):
            var = parent.target.value
        if index is not None and not isinstance(doc.tree.body[index], cst.SimpleStatementLine | cst.With):
            index = None  # inside a function, class or other block
        return AgentSite(node=node, doc=doc, call=call, index=index, var=var)

    def node_id(self, framework: str, kind: str, doc: Doc, qualname: str) -> str:
        return f"{framework}:{kind}:{doc.module}.{qualname}"

    def import_into(self, doc: Doc, other: Doc, name: str) -> None:
        """Make ``name`` (bound at module level in ``other``) importable in ``doc``."""
        if other.rel == doc.rel:
            return
        if name in doc.top_names():
            raise EditError(f"`{name}` already means something else in {doc.rel}.")
        same_dir = other.path.parent == doc.path.parent
        package = same_dir and (doc.path.parent / "__init__.py").exists()
        if package:
            module = "." + (other.module.rsplit(".", 1)[-1] if other.path.name != "__init__.py" else "")
        else:
            module = other.module
        doc.add_import(module, name)

    def other_modules_importing(self, doc: Doc, name: str) -> list[str]:
        """Project files (other than ``doc``) that import ``name`` from ``doc``'s module."""
        from ..project import parse_module

        files = collect(self.root)
        target = f"{doc.module}.{name}"
        found: list[str] = []
        needle = name.encode()
        for path in files.index.values():
            path = path.resolve()
            if path == doc.path:
                continue
            text = self.overrides.get(path)
            try:
                raw = text.encode() if text is not None else path.read_bytes()
            except OSError:
                continue
            if needle not in raw:
                continue
            try:
                module = parse_module(files.root, path, raw.decode("utf-8", errors="replace"))
            except cst.ParserSyntaxError:
                continue
            if any(b.kind == "import" and b.target == target for b in module.bindings.values()):
                found.append(module.rel)
        return found
