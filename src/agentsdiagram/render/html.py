"""Self-contained HTML: the interactive viewer bundle with the graph embedded.

The viewer (packages/viewer) is built by pnpm into ``agentsdiagram/_static`` and shipped in
the wheel. The page needs no server and no network: open it in any browser.
"""

from __future__ import annotations

import html
import json
from importlib import resources

from .. import __version__
from ..ir import Project
from .mermaid import render as render_mermaid

PROTOCOL_VERSION = "1"
# the viewer's brand mark: connected nodes on the accent color
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
    "%3Crect width='16' height='16' rx='4' fill='%235b5bd6'/%3E"
    "%3Cpath d='M5 4.5l6 3.5M5 11.5l6-3.5' stroke='white' stroke-width='1.4'/%3E"
    "%3Ccircle cx='4.5' cy='4.5' r='1.6' fill='white'/%3E%3Ccircle cx='11.5' cy='8' r='1.6' fill='white'/%3E"
    "%3Ccircle cx='4.5' cy='11.5' r='1.6' fill='white'/%3E%3C/svg%3E"
)


class ViewerBundleMissing(RuntimeError):
    pass


def _asset(name: str) -> str:
    try:
        return resources.files("agentsdiagram").joinpath("_static", name).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise ViewerBundleMissing(
            f"viewer bundle `_static/{name}` not found; build it with `pnpm --filter @agentsdiagram/viewer build`"
        ) from exc


def _script_safe(text: str) -> str:
    """Make text safe inside a <script> element."""
    return text.replace("</", "<\\/").replace("<!--", "<\\!--")


def render(project: Project, *, title: str = "agentsdiagram") -> str:
    js = _asset("viewer.js")
    css = _asset("viewer.css")
    result = {
        "protocolVersion": PROTOCOL_VERSION,
        "version": 1,
        "scope": {"kind": "workspace"},
        "project": project.model_dump(mode="json"),
    }
    data = _script_safe(json.dumps(result, ensure_ascii=False))
    mermaid = _script_safe(render_mermaid(project, title=title))
    js = js.replace("</script", "<\\/script")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="agentsdiagram {__version__}">
<title>{html.escape(title)} · agentsdiagram</title>
<link rel="icon" href="{FAVICON}">
<style>{css}</style>
</head>
<body>
<div id="root" data-title="{html.escape(title)}"></div>
<script type="application/json" id="agentsdiagram-data">{data}</script>
<script type="text/plain" id="agentsdiagram-mermaid">{mermaid}</script>
<script type="module">{js}</script>
</body>
</html>
"""
