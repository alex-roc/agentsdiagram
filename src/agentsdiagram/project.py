"""Project loading: file discovery, module index, parsing and name resolution.

Everything here is framework-agnostic. Adapters (``agentsdiagram.adapters``) read a
parsed ``Module`` and record ``Facts``; ``agentsdiagram.link`` turns facts into the IR.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import subprocess
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from .ir import Position, Range, SourceRef

SKIP_DIRS = {
    ".git",
    ".hg",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "site-packages",
    "__pycache__",
    "build",
    "dist",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}


@dataclass
class Config:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, root: Path) -> Config:
        pyproject = root / "pyproject.toml"
        if not pyproject.is_file():
            return cls()
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return cls()
        section = data.get("tool", {}).get("agentsdiagram", {})
        return cls(include=list(section.get("include", [])), exclude=list(section.get("exclude", [])))


def find_root(path: Path) -> Path:
    """Nearest ancestor with a pyproject.toml or .git; falls back to the path itself."""
    start = path if path.is_dir() else path.parent
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() or (candidate / ".git").exists():
            return candidate
    return start


def list_python_files(root: Path) -> list[Path]:
    """Python files under ``root``, honouring .gitignore when ``root`` is inside a git work tree."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "--", "*.py"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout
        files = [root / line for line in out.splitlines() if line]
        files = [f for f in files if f.is_file() and not (set(f.relative_to(root).parts) & SKIP_DIRS)]
        if files:
            return sorted(files)
    except (OSError, subprocess.SubprocessError):
        pass
    result: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        result.extend(Path(dirpath) / f for f in sorted(filenames) if f.endswith(".py"))
    return result


def module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] == "src" and len(parts) > 1:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) or rel.stem


def _matches(rel: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p.rstrip("/") + "/**") for p in patterns)


# --------------------------------------------------------------------------- bindings


@dataclass
class Binding:
    """A name defined in a module scope (``qualname`` uses LibCST's ``f.<locals>.x`` form)."""

    qualname: str
    kind: str  # "function" | "class" | "assign" | "with" | "import"
    node: cst.CSTNode  # FunctionDef | ClassDef | assigned value expr | with item expr
    name_node: cst.CSTNode | None = None
    target: str | None = None  # absolute dotted path for imports


@dataclass
class Module:
    name: str
    path: Path
    rel: str
    text: str
    sha256: str
    tree: cst.Module
    bindings: dict[str, Binding]
    qnames: dict[cst.CSTNode, str]
    parents: dict[cst.CSTNode, cst.CSTNode]
    calls: list[cst.Call]  # every call, in source order
    is_package: bool
    _positions: dict | None = None

    # ---- helpers used by adapters and the linker

    def code(self, node: cst.CSTNode) -> str:
        return self.tree.code_for_node(node)

    def range(self, node: cst.CSTNode) -> Range:
        if self._positions is None:
            self._positions = dict(MetadataWrapper(self.tree, unsafe_skip_copy=True).resolve(PositionProvider))
        pos = self._positions[node]
        return Range(
            start=Position(line=pos.start.line, column=pos.start.column),  # type: ignore[attr-defined]
            end=Position(line=pos.end.line, column=pos.end.column),  # type: ignore[attr-defined]
        )

    def ref(self, node: cst.CSTNode, name_node: cst.CSTNode | None = None) -> SourceRef:
        return SourceRef(
            file=self.rel,
            range=self.range(node),
            name_range=self.range(name_node) if name_node is not None else None,
        )

    def qname(self, node: cst.CSTNode) -> str | None:
        """Absolute qualified name for a Name/Attribute (imports made absolute)."""
        return self.qnames.get(node)

    def enclosing_function(self, node: cst.CSTNode) -> cst.FunctionDef | None:
        current = self.parents.get(node)
        while current is not None:
            if isinstance(current, cst.FunctionDef):
                return current
            current = self.parents.get(current)
        return None

    def scope_prefix(self, node: cst.CSTNode) -> str:
        """``f.<locals>.`` style prefix of the scope containing ``node``."""
        names: list[str] = []
        current = self.parents.get(node)
        while current is not None:
            if isinstance(current, cst.FunctionDef):
                names.append(current.name.value + ".<locals>")
            elif isinstance(current, cst.ClassDef):
                names.append(current.name.value)
            current = self.parents.get(current)
        return ".".join(reversed(names))

    def binding_name_for(self, value: cst.CSTNode) -> tuple[str, cst.CSTNode] | None:
        """If ``value`` is directly assigned to a single name (``x = value``), return (qualname, Name)."""
        parent = self.parents.get(value)
        if isinstance(parent, cst.Assign) and len(parent.targets) == 1:
            target = parent.targets[0].target
        elif isinstance(parent, cst.AnnAssign):
            target = parent.target
        elif isinstance(parent, cst.WithItem) and parent.asname is not None:
            target = parent.asname.name
        else:
            return None
        if isinstance(target, cst.Name):
            qn = self.qnames.get(target)
            return (qn or target.value), target
        return None


def _absolute(qn: str, module: str, is_package: bool) -> str:
    if not qn.startswith("."):
        return qn
    level = len(qn) - len(qn.lstrip("."))
    rest = qn[level:]
    package = module.split(".") if is_package else module.split(".")[:-1]
    if level > 1:
        package = package[: len(package) - (level - 1)]
    return ".".join([*package, rest] if rest else package)


class _Scope:
    __slots__ = ("kind", "prefix", "names", "parent")

    def __init__(self, kind: str, prefix: str, parent: _Scope | None) -> None:
        self.kind = kind  # "module" | "function" | "class"
        self.prefix = prefix  # qualname prefix for names bound here ("" | "f.<locals>." | "C.")
        self.names: dict[str, str | None] = {}  # local name -> absolute import target (None if local)
        self.parent = parent


class _Collector(cst.CSTVisitor):
    """One pass over the tree: parents, bindings, scopes, calls.

    A deliberately small replacement for LibCST's Scope/QualifiedName providers (3-4x
    faster). It follows Python's LEGB lookup for module, function and class scopes and
    ignores rarer constructs (``global``/``nonlocal``, comprehension scopes).
    """

    def __init__(self, module: str, is_package: bool) -> None:
        self.module = module
        self.is_package = is_package
        self.parents: dict[cst.CSTNode, cst.CSTNode] = {}
        self.bindings: dict[str, Binding] = {}
        self.calls: list[cst.Call] = []
        self.uses: list[tuple[cst.Name, _Scope]] = []
        self.attributes: list[cst.Attribute] = []
        self._stack: list[cst.CSTNode] = []
        self.scope = _Scope("module", "", None)

    # generic hooks keep the parent map
    def on_visit(self, node: cst.CSTNode) -> bool:
        if self._stack:
            self.parents[node] = self._stack[-1]
        self._stack.append(node)
        return super().on_visit(node)

    def on_leave(self, original_node: cst.CSTNode) -> None:
        super().on_leave(original_node)
        self._stack.pop()

    # ---- scopes
    def _bind(
        self, name: str, kind: str, node: cst.CSTNode, name_node: cst.CSTNode | None, target: str | None = None
    ) -> None:
        qn = self.scope.prefix + name
        self.scope.names[name] = target
        self.bindings[qn] = Binding(qn, kind, node, name_node, target)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        self._bind(node.name.value, "function", node, node.name)
        self.scope = _Scope("function", f"{self.scope.prefix}{node.name.value}.<locals>.", self.scope)
        for param in [*node.params.params, *node.params.kwonly_params, *node.params.posonly_params]:
            self.scope.names[param.name.value] = None
        for star in (node.params.star_arg, node.params.star_kwarg):
            if isinstance(star, cst.Param):
                self.scope.names[star.name.value] = None

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        self.scope = self.scope.parent  # type: ignore[assignment]

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self._bind(node.name.value, "class", node, node.name)
        self.scope = _Scope("class", f"{self.scope.prefix}{node.name.value}.", self.scope)

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self.scope = self.scope.parent  # type: ignore[assignment]

    def _bind_target(self, target: cst.BaseExpression, kind: str, value: cst.CSTNode | None) -> None:
        if isinstance(target, cst.Name):
            self._bind(target.value, kind if value is not None else "local", value or target, target)
        elif isinstance(target, cst.Tuple | cst.List):
            for el in target.elements:
                self._bind_target(el.value, kind, None)
        elif isinstance(target, cst.StarredElement):
            self._bind_target(target.value, kind, None)

    def visit_Assign(self, node: cst.Assign) -> None:
        for t in node.targets:
            self._bind_target(t.target, "assign", node.value)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        self._bind_target(node.target, "assign", node.value)

    def visit_NamedExpr(self, node: cst.NamedExpr) -> None:
        self._bind_target(node.target, "assign", node.value)

    def visit_For(self, node: cst.For) -> None:
        self._bind_target(node.target, "loop", None)

    def visit_WithItem(self, node: cst.WithItem) -> None:
        if node.asname is not None:
            self._bind_target(node.asname.name, "with", node.item)  # type: ignore[arg-type]

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if isinstance(node.names, cst.ImportStar):
            return
        dots = "." * len(node.relative)
        base = dots + (_code(node.module) if node.module else "")
        for alias in node.names:
            name = _code(alias.name)
            local = alias.asname.name.value if alias.asname else name  # type: ignore[union-attr]
            full = f"{base}.{name}" if not base.endswith(".") else f"{base}{name}"
            self._bind(local, "import", alias, alias, _absolute(full, self.module, self.is_package))

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = _code(alias.name)
            local = alias.asname.name.value if alias.asname else name.split(".")[0]  # type: ignore[union-attr]
            target = name if alias.asname else name.split(".")[0]
            self._bind(local, "import", alias, alias, target)

    # ---- uses
    def visit_Name(self, node: cst.Name) -> None:
        self.uses.append((node, self.scope))

    def visit_Attribute(self, node: cst.Attribute) -> None:
        self.attributes.append(node)

    def visit_Call(self, node: cst.Call) -> None:
        self.calls.append(node)

    # ---- resolution (after the pass, so later module-level definitions are visible)
    def resolve(self) -> dict[cst.CSTNode, str]:
        qnames: dict[cst.CSTNode, str] = {}
        for node, scope in self.uses:
            qn = self._lookup(node.value, scope)
            if qn:
                qnames[node] = qn
        for node in self.attributes:
            base = self._attr_base(node, qnames)
            if base:
                qnames[node] = base
        return qnames

    def _attr_base(self, node: cst.BaseExpression, qnames: dict[cst.CSTNode, str]) -> str | None:
        if node in qnames:
            return qnames[node]
        if isinstance(node, cst.Name):
            return qnames.get(node)
        if isinstance(node, cst.Attribute):
            base = self._attr_base(node.value, qnames)
            if base:
                qn = f"{base}.{node.attr.value}"
                qnames[node] = qn
                return qn
        return None

    def _lookup(self, name: str, scope: _Scope) -> str | None:
        current: _Scope | None = scope
        first = True
        while current is not None:
            # class bodies are not visible from nested functions
            if (first or current.kind != "class") and name in current.names:
                target = current.names[name]
                if target is not None:
                    return target
                return current.prefix + name
            first = False
            current = current.parent
        return None


def _code(node: cst.CSTNode) -> str:
    return cst.Module([]).code_for_node(node)


def parse_module(root: Path, path: Path, text: str | None = None) -> Module:
    """Parse one file. Raises ``libcst.ParserSyntaxError`` on invalid syntax."""
    if text is None:
        text = path.read_text(encoding="utf-8", errors="replace")
    name = module_name(root, path)
    is_package = path.name == "__init__.py"
    tree = cst.parse_module(text)
    collector = _Collector(name, is_package)
    tree.visit(collector)
    return Module(
        name=name,
        path=path,
        rel=path.relative_to(root).as_posix(),
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        tree=tree,
        bindings=collector.bindings,
        qnames=collector.resolve(),
        parents=collector.parents,
        calls=collector.calls,
        is_package=is_package,
    )


@dataclass
class FileSet:
    root: Path
    seeds: list[Path]  # files to extract
    index: dict[str, Path]  # module name -> path, for lazy cross-module resolution


def collect(path: Path, include: list[str] | None = None, exclude: list[str] | None = None) -> FileSet:
    path = path.resolve()
    root = find_root(path)
    config = Config.load(root)
    include = [*config.include, *(include or [])]
    exclude = [*config.exclude, *(exclude or [])]
    all_files = list_python_files(root)
    index = {module_name(root, f): f for f in all_files}
    if path.is_file():
        seeds = [path]
    else:
        seeds = []
        for f in all_files:
            if not f.is_relative_to(path):
                continue
            rel = f.relative_to(root).as_posix()
            if include and not _matches(rel, include):
                continue
            if exclude and _matches(rel, exclude):
                continue
            seeds.append(f)
    return FileSet(root=root, seeds=seeds, index=index)
