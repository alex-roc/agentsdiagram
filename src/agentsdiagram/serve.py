"""``agentsdiagram serve``: the viewer in a browser, redrawn when files change, with editing.

A small stdlib HTTP server bound to localhost:

    GET  /                 the viewer page (graph embedded, plus the live config)
    GET  /api/graph        GraphResult JSON
    GET  /api/mermaid      Mermaid text
    GET  /api/events       server-sent events: ``graph`` with the new version after each change
    POST /api/edit         EditParams JSON -> EditResult JSON (writes the files)

Edits need the per-run token embedded in the page (``X-Agentsdiagram-Token``) and requests
must name this server in ``Host``, so other web pages cannot drive it.
"""

from __future__ import annotations

import json
import secrets
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .analyze import Cache, analyze
from .edit import EditError, plan_edit
from .ir import EditParams, EditResult, Project
from .project import collect
from .render.html import PROTOCOL_VERSION
from .render.html import render as render_html
from .render.mermaid import render as render_mermaid

POLL_SECONDS = 1.0
KEEPALIVE_SECONDS = 15.0


class LiveProject:
    """The analysed project, kept up to date by a polling watcher."""

    def __init__(self, path: Path, *, include: list[str] | None = None, exclude: list[str] | None = None) -> None:
        self.path = path
        self.include = include or []
        self.exclude = exclude or []
        self.cache = Cache()
        self.changed = threading.Condition()
        self.version = 0
        self.project: Project = self._analyze()
        self.root = Path(self.project.root)
        self._signature = self._files_signature()
        self._stop = threading.Event()

    def _analyze(self) -> Project:
        return analyze(self.path, include=self.include, exclude=self.exclude, cache=self.cache)

    def _files_signature(self) -> tuple:
        files = collect(self.path).index.values()
        out = []
        for f in files:
            try:
                st = f.stat()
            except OSError:
                continue
            out.append((str(f), st.st_mtime_ns, st.st_size))
        return tuple(sorted(out))

    def refresh(self, force: bool = False) -> bool:
        signature = self._files_signature()
        if not force and signature == self._signature:
            return False
        self._signature = signature
        project = self._analyze()
        with self.changed:
            self.project = project
            self.version += 1
            self.changed.notify_all()
        return True

    def watch(self) -> None:
        while not self._stop.wait(POLL_SECONDS):
            try:
                self.refresh()
            except Exception as exc:  # keep serving the last good graph
                print(f"agentsdiagram: analysis failed: {exc!r}", file=sys.stderr)

    def stop(self) -> None:
        self._stop.set()
        with self.changed:
            self.changed.notify_all()

    def graph(self) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "version": self.version,
            "scope": {"kind": "workspace"},
            "project": self.project.model_dump(mode="json"),
        }

    def edit(self, params: EditParams) -> EditResult:
        try:
            outcome = plan_edit(self.root, params.request, expect=params.expected(), cache=self.cache)
        except EditError as exc:
            return EditResult(ok=False, message=str(exc))
        outcome.write()
        self.refresh(force=True)
        return EditResult(ok=True, message=outcome.message, files=outcome.files, focus=outcome.focus)


def make_server(
    live: LiveProject, *, host: str = "127.0.0.1", port: int = 8765, editable: bool = True, title: str | None = None
) -> ThreadingHTTPServer:
    token = secrets.token_urlsafe(24)
    page_title = title or live.root.name

    class Handler(BaseHTTPRequestHandler):
        server_version = "agentsdiagram"

        def log_message(self, format: str, *args: Any) -> None:  # quiet by default
            return

        def _host_ok(self) -> bool:
            host_header = (self.headers.get("Host") or "").lower()
            port_ = self.server.server_port  # type: ignore[attr-defined]
            return host_header in {f"127.0.0.1:{port_}", f"localhost:{port_}", f"[::1]:{port_}"}

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: Any, status: int = 200) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if not self._host_ok():
                return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
            route = self.path.split("?", 1)[0]
            if route == "/":
                html = render_html(
                    live.project, title=page_title, live={"token": token if editable else None, "editable": editable}
                )
                return self._send(200, html.encode(), "text/html; charset=utf-8")
            if route == "/api/graph":
                return self._json(live.graph())
            if route == "/api/mermaid":
                text = render_mermaid(live.project, title=page_title)
                return self._send(200, text.encode(), "text/plain; charset=utf-8")
            if route == "/api/events":
                return self._events()
            return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

        def _events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            seen = live.version
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while not live._stop.is_set():
                    with live.changed:
                        live.changed.wait_for(
                            lambda last=seen: live.version != last or live._stop.is_set(), KEEPALIVE_SECONDS
                        )
                        version = live.version
                    if version != seen:
                        seen = version
                        self.wfile.write(f"event: graph\ndata: {json.dumps({'version': version})}\n\n".encode())
                    else:
                        self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_POST(self) -> None:
            if not self._host_ok() or self.path != "/api/edit":
                return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
            if not editable or not secrets.compare_digest(self.headers.get("X-Agentsdiagram-Token") or "", token):
                return self._json({"ok": False, "message": "Editing is not allowed on this server."}, 403)
            length = int(self.headers.get("Content-Length") or 0)
            try:
                params = EditParams.model_validate_json(self.rfile.read(length))
            except ValidationError as exc:
                return self._json({"ok": False, "message": f"Bad request: {exc.errors()[0]['msg']}"}, 400)
            result = live.edit(params)
            self._json(result.model_dump(mode="json"))

    last_error: OSError | None = None
    for candidate in [port, *range(port + 1, port + 20)] if port else [0]:
        try:
            server = ThreadingHTTPServer((host, candidate), Handler)
            server.daemon_threads = True
            server.token = token  # type: ignore[attr-defined]  # for tests and embedding
            return server
        except OSError as exc:
            last_error = exc
    raise OSError(f"no free port from {port}: {last_error}")


def serve(
    path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    editable: bool = True,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    title: str | None = None,
) -> None:
    live = LiveProject(path, include=include, exclude=exclude)
    server = make_server(live, host=host, port=port, editable=editable, title=title)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{server.server_address[1]}/"
    watcher = threading.Thread(target=live.watch, daemon=True)
    watcher.start()
    mode = "editable" if editable else "read only"
    print(f"agentsdiagram: serving {live.root} at {url} ({mode}); Ctrl+C to stop", file=sys.stderr)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        live.stop()
        server.server_close()
