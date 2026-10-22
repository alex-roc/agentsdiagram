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
<style>{css}</style>
</head>
<body>
<div id="root"></div>
<script type="application/json" id="agentsdiagram-data">{data}</script>
<script type="text/plain" id="agentsdiagram-mermaid">{mermaid}</script>
<script type="module">{js}</script>
</body>
</html>
"""
