# Changelog

## Unreleased

- Redesigned viewer: light and dark themes (a toggle in the HTML page; VS Code follows the
  editor), line icons per node kind, agents as larger cards with their model, a legend that
  counts and filters node kinds, a Problems drawer with severity markers on the nodes, a minimap,
  and selecting a node highlights its neighbors and frames them. Keyboard: `/` to search, `Enter`
  for the next match, `Esc` to clear.
- Edge labels (wrappers such as `prefixed("crm")`) get room in the layout instead of being drawn
  under a node.
- Diagnostics without a node (e.g. smolagents `@tool` checks, AD203) are attached to the
  innermost node that contains them, so the viewer can mark it.
- `examples/`: a PydanticAI support desk and a smolagents research team, used by the website.
- Website with live demos of the examples at https://alex-roc.github.io/agentsdiagram/
  (`site/`, deployed by `.github/workflows/pages.yml`).
- VS Code: fixed duplicated code lenses when the server was restarted while still starting.
- CLI: hint when `--include` matches nothing (globs are relative to the project root), and the
  `lsp` command suggests `uvx --from 'agentsdiagram[lsp]'`.

## 0.1.2 — 2026-10-22

- First active release on Open VSX (namespace `alex-roc` verified).
- CI: GitHub Actions updated to their Node 24 versions.

## 0.1.1 — 2026-10-22

- Releases are now fully automated: PyPI (trusted publishing), VS Code Marketplace (Microsoft
  Entra ID workload identity, no tokens) and Open VSX, from one tag.

## 0.1.0 — 2026-10-22

First release.

- Static analysis of PydanticAI 2.x (agents, tools, toolsets, MCP, capabilities, SubAgents,
  delegation, hand-off workflows, pydantic-graph, Agent Specs) and smolagents 1.x (CodeAgent,
  ToolCallingAgent, tools, managed agents, MCP).
- CLI: `scan` (Mermaid, JSON, Markdown, self-contained interactive HTML), `check`, `schema`, `lsp`.
- Interactive viewer (React Flow) and VS Code / Open VSX extension with live diagram, code lenses
  and diagnostics.
