"""Mermaid ``flowchart`` renderer.

Plain flowchart syntax only (no stateDiagram or newer diagram types) so it renders in
GitHub, the VS Code Markdown preview (built in since 1.121) and Cursor's older Mermaid.
"""

from __future__ import annotations

from ..ir import Node, Project

# Mermaid's defaults: maxEdges 500, maxTextSize 50 000.
MAX_EDGES = 500

SHAPES = {
    "agent": ('["', '"]'),
    "tool": ("[[", "]]"),
    "toolset": ("[/", "/]"),
    "mcp_server": ("[(", ")]"),
    "native_tool": ("{{", "}}"),
    "capability": (">", "]"),
    "workflow": ("[\\", "/]"),
    "external_tool_source": ("[(", ")]"),
    "graph_step": ("(", ")"),
    "dynamic": ('["', '"]'),
}

ARROWS = {
    "uses": "-->",
    "provides": "-->",
    "wraps": "-.->",
    "delegates_to": "==>",
    "manages": "==>",
    "runs": "-->",
    "transitions": "-->",
}

CLASSES = """\
    classDef agent fill:#e8f0fe,stroke:#1a73e8,stroke-width:2px,color:#0b3d91
    classDef tool fill:#e6f4ea,stroke:#188038,color:#0d4a1f
    classDef toolset fill:#f1f8e9,stroke:#558b2f,color:#33691e
    classDef mcp_server fill:#fff4e5,stroke:#e8710a,color:#7a3b00
    classDef native_tool fill:#f3e8fd,stroke:#8430ce,color:#4a148c
    classDef capability fill:#fce8f3,stroke:#c2185b,color:#880e4f
    classDef workflow fill:#fffde7,stroke:#f9a825,color:#5d4300
    classDef external_tool_source fill:#eceff1,stroke:#546e7a,color:#263238
    classDef graph_step fill:#e0f7fa,stroke:#00838f,color:#004d55
    classDef dynamic fill:#fafafa,stroke:#9e9e9e,stroke-dasharray:4 3,color:#616161
    classDef stale opacity:0.55,stroke-dasharray:2 2
    classDef planned stroke-dasharray:6 4"""


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace('"', "#quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "#124;")
        .replace("\n", " ")
    )


def _label(n: Node) -> str:
    if n.kind == "graph_step" and n.attrs.extra.get("role") in ("start", "end"):
        return n.attrs.extra["role"]
    lines = [f"<b>{_esc(n.name)}</b>"]
    if n.kind == "agent":
        sub = n.attrs.model or n.attrs.agent_class
        if sub:
            lines.append(f"<small>{_esc(sub)}</small>")
    elif n.kind == "mcp_server":
        target = n.attrs.url or n.attrs.command
        if target:
            lines.append(f"<small>{_esc(target[:48])}</small>")
    if n.status in ("dynamic", "partial", "stale"):
        lines.append(f"<i>{n.status}</i>")
    return "<br/>".join(lines)


def render(project: Project, *, title: str | None = None) -> str:
    ids = {n.id: f"n{i}" for i, n in enumerate(project.nodes, start=1)}
    contained: dict[str, list[str]] = {}
    for e in project.edges:
        if e.kind == "contains":
            contained.setdefault(e.source, []).append(e.target)
    inside = {t for targets in contained.values() for t in targets}
    by_id = {n.id: n for n in project.nodes}

    out: list[str] = []
    if title:
        out += ["---", f"title: {title}", "---"]
    out.append("flowchart LR")

    def node_line(n: Node, indent: str) -> str:
        if n.kind == "graph_step" and n.attrs.extra.get("role") in ("start", "end"):
            return f'{indent}{ids[n.id]}(("{_label(n)}"))'
        if n.kind == "graph_step" and n.attrs.extra.get("role") == "decision":
            return f'{indent}{ids[n.id]}{{"{_esc(n.name)}"}}'
        left, right = SHAPES.get(n.kind, ('["', '"]'))
        quoted = left.endswith('"')
        label = _label(n)
        body = label if quoted else f'"{label}"'
        return f"{indent}{ids[n.id]}{left}{body}{right}"

    for n in project.nodes:
        if n.kind == "graph":
            out.append(f'    subgraph {ids[n.id]}["{_esc(n.name)}"]')
            out.append("    direction TB")
            for child in contained.get(n.id, []):
                if child in by_id:
                    out.append(node_line(by_id[child], "        "))
            out.append("    end")
        elif n.id not in inside:
            out.append(node_line(n, "    "))

    for e in project.edges:
        if e.kind == "contains" or e.source not in ids or e.target not in ids:
            continue
        label_parts = []
        if e.kind in ("delegates_to", "manages"):
            label_parts.append("delegates" if e.kind == "delegates_to" else "manages")
        if e.order is not None:
            label_parts.append(str(e.order))
        if e.label:
            label_parts.append(e.label)
        label_parts.extend(e.wrappers)
        arrow = ARROWS.get(e.kind, "-->")
        label = f'|"{_esc(" · ".join(label_parts))}"|' if label_parts else ""
        out.append(f"    {ids[e.source]} {arrow}{label} {ids[e.target]}")

    out.append(CLASSES)
    groups: dict[str, list[str]] = {}
    for n in project.nodes:
        if n.kind == "graph":
            continue
        groups.setdefault(n.kind, []).append(ids[n.id])
        if n.status in ("stale", "planned"):
            groups.setdefault(n.status, []).append(ids[n.id])
    for cls, members in groups.items():
        out.append(f"    class {','.join(members)} {cls}")
    return "\n".join(out) + "\n"


def too_large(project: Project) -> bool:
    return len(project.edges) > MAX_EDGES
