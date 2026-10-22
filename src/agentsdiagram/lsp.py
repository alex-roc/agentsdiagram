"""Language server (pygls 2) used by the VS Code extension.

Standard LSP: diagnostics (publishDiagnostics) and code lenses ("Show in diagram").
Custom methods (see packages/protocol/src/messages.ts):
  request      agentsdiagram/graph    {scope} -> {protocolVersion, version, scope, project}
  request      agentsdiagram/mermaid  {scope} -> {text}
  notification agentsdiagram/graphChanged {version}   (server -> client, debounced)

Analysis runs in a worker thread on the open documents' unsaved text, reusing a
content-hash cache, so only edited files are parsed again.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from lsprotocol import types
from pygls.capabilities import ServerCapabilitiesBuilder
from pygls.lsp.server import LanguageServer
from pygls.protocol import language_server as _ls_protocol

from . import __version__
from .analyze import Cache, analyze
from .ir import Project
from .render.mermaid import render as render_mermaid

PROTOCOL_VERSION = "1"
DEBOUNCE_SECONDS = 0.3
LENS_KINDS = {"agent", "workflow", "graph"}
SEVERITY = {
    "error": types.DiagnosticSeverity.Error,
    "warning": types.DiagnosticSeverity.Warning,
    "info": types.DiagnosticSeverity.Information,
}

log = logging.getLogger(__name__)


class _Capabilities(ServerCapabilitiesBuilder):
    """Advertise the protocol version in ``capabilities.experimental`` (pygls has no hook for it)."""

    def build(self) -> types.ServerCapabilities:
        caps = super().build()
        caps.experimental = {"agentsdiagram": {"protocolVersion": PROTOCOL_VERSION}}
        return caps


_ls_protocol.ServerCapabilitiesBuilder = _Capabilities  # type: ignore[attr-defined,misc]


def uri_to_path(uri: str) -> Path:
    return Path(unquote(urlparse(uri).path))


class AgentsDiagramServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__("agentsdiagram", __version__)
        self.cache = Cache()
        self.project: Project | None = None
        self.version = 0
        self.root: Path | None = None
        self.include: list[str] = []
        self.exclude: list[str] = []
        self.code_lens = True
        self._pending: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._published: set[str] = set()

    # ---------------------------------------------------------------- analysis

    def overrides(self) -> dict[Path, str]:
        out: dict[Path, str] = {}
        for uri, doc in self.workspace.text_documents.items():
            if uri.startswith("file:") and uri.endswith(".py"):
                out[uri_to_path(uri)] = doc.source
        return out

    def _analyze(self, path: Path) -> Project:
        return analyze(path, include=self.include, exclude=self.exclude, cache=self.cache, overrides=self.overrides())

    async def refresh(self) -> None:
        if self.root is None:
            return
        async with self._lock:
            try:
                project = await asyncio.to_thread(self._analyze, self.root)
            except Exception:  # never crash the server on an analysis bug
                log.exception("analysis failed")
                return
            self.project = project
            self.version += 1
        self.publish_diagnostics(project)
        self.protocol.notify("agentsdiagram/graphChanged", {"version": self.version})

    def schedule_refresh(self) -> None:
        if self._pending is not None and not self._pending.done():
            self._pending.cancel()

        async def later() -> None:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            await self.refresh()

        self._pending = asyncio.ensure_future(later())

    async def project_for(self, scope: dict[str, Any]) -> Project:
        if scope.get("kind") == "file" and scope.get("uri"):
            path = uri_to_path(scope["uri"])
            async with self._lock:
                return await asyncio.to_thread(self._analyze, path)
        if self.project is None:
            await self.refresh()
        return self.project or Project(tool_version=__version__, root=str(self.root or ""))

    # ---------------------------------------------------------------- positions

    def _lines(self, path: Path) -> list[str]:
        uri = path.as_uri()
        doc = self.workspace.text_documents.get(uri)
        if doc is not None:
            return list(doc.lines)
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            return []

    def to_lsp_range(self, path: Path, ir_range) -> types.Range:
        """IR ranges are 1-based lines and code-point columns; LSP is 0-based and UTF-16 by default."""
        lines = self._lines(path)
        codec = self.workspace.position_codec

        def pos(p) -> types.Position:
            server_pos = types.Position(line=max(p.line - 1, 0), character=p.column)
            if not lines:
                return server_pos
            return codec.position_to_client_units(lines, server_pos)

        return types.Range(start=pos(ir_range.start), end=pos(ir_range.end))

    # ---------------------------------------------------------------- diagnostics

    def publish_diagnostics(self, project: Project) -> None:
        root = Path(project.root)
        by_file: dict[str, list[types.Diagnostic]] = {}
        for d in project.diagnostics:
            if d.ref is None:
                continue
            path = root / d.ref.file
            by_file.setdefault(path.as_uri(), []).append(
                types.Diagnostic(
                    range=self.to_lsp_range(path, d.ref.range),
                    message=d.message,
                    severity=SEVERITY[d.severity],
                    code=d.code,
                    source="agentsdiagram",
                )
            )
        for uri in self._published - set(by_file):
            self.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=[]))
        for uri, diags in by_file.items():
            self.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=diags))
        self._published = set(by_file)


server = AgentsDiagramServer()


@server.feature(types.INITIALIZE)
def initialize(ls: AgentsDiagramServer, params: types.InitializeParams) -> None:
    folders = params.workspace_folders or []
    if folders:
        ls.root = uri_to_path(folders[0].uri)
    elif params.root_uri:
        ls.root = uri_to_path(params.root_uri)
    options = params.initialization_options or {}
    if isinstance(options, dict):
        ls.include = list(options.get("include") or [])
        ls.exclude = list(options.get("exclude") or [])
        ls.code_lens = bool((options.get("codeLens") or {}).get("enabled", True))


@server.feature(types.INITIALIZED)
async def initialized(ls: AgentsDiagramServer, params: types.InitializedParams) -> None:
    await ls.refresh()


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: AgentsDiagramServer, params: types.DidOpenTextDocumentParams) -> None:
    ls.schedule_refresh()


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: AgentsDiagramServer, params: types.DidChangeTextDocumentParams) -> None:
    ls.schedule_refresh()


@server.feature(types.TEXT_DOCUMENT_DID_SAVE)
def did_save(ls: AgentsDiagramServer, params: types.DidSaveTextDocumentParams) -> None:
    ls.schedule_refresh()


@server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls: AgentsDiagramServer, params: types.DidCloseTextDocumentParams) -> None:
    ls.schedule_refresh()


@server.feature(types.WORKSPACE_DID_CHANGE_WATCHED_FILES)
def did_change_watched(ls: AgentsDiagramServer, params: types.DidChangeWatchedFilesParams) -> None:
    ls.schedule_refresh()


@server.feature(types.TEXT_DOCUMENT_CODE_LENS)
def code_lens(ls: AgentsDiagramServer, params: types.CodeLensParams) -> list[types.CodeLens]:
    project = ls.project
    if project is None or not ls.code_lens:
        return []
    path = uri_to_path(params.text_document.uri)
    try:
        rel = path.relative_to(Path(project.root)).as_posix()
    except ValueError:
        return []
    lenses = []
    for n in project.nodes:
        if n.kind not in LENS_KINDS or n.source is None or n.source.file != rel:
            continue
        anchor = n.source.name_range or n.source.range
        rng = ls.to_lsp_range(path, anchor)
        lenses.append(
            types.CodeLens(
                range=types.Range(start=rng.start, end=rng.start),
                command=types.Command(
                    title=f"$(type-hierarchy) Show {n.name} in diagram",
                    command="agentsdiagram.showNode",
                    arguments=[n.id],
                ),
            )
        )
    return lenses


@server.feature("agentsdiagram/graph")
async def graph(ls: AgentsDiagramServer, params: Any) -> dict[str, Any]:
    scope = _scope(params)
    project = await ls.project_for(scope)
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "version": ls.version,
        "scope": scope,
        "project": project.model_dump(mode="json"),
    }


@server.feature("agentsdiagram/mermaid")
async def mermaid(ls: AgentsDiagramServer, params: Any) -> dict[str, str]:
    project = await ls.project_for(_scope(params))
    return {"text": render_mermaid(project, title=Path(project.root).name)}


def _scope(params: Any) -> dict[str, Any]:
    """Params arrive as a dict or as pygls' attribute object, depending on the transport."""
    scope = getattr(params, "scope", None)
    if scope is None and isinstance(params, dict):
        scope = params.get("scope")
    if scope is None:
        return {"kind": "workspace"}
    if not isinstance(scope, dict):
        scope = {k: getattr(scope, k) for k in ("kind", "uri") if hasattr(scope, k)}
    return scope


def serve() -> None:
    logging.basicConfig(level=logging.WARNING)
    server.start_io()
