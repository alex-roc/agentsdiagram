# Changelog

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
