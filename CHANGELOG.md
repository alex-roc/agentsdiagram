# Changelog

## 0.4.1 — 2026-10-23

- Viewer: in a narrow side panel (VS Code with a split editor) the plan and edit actions are
  shown one per row, so their labels are never cut.

## 0.4.0 — 2026-10-23

Plan and edit: the roadmap's v0.3 (Plan) and v0.4 (Edit), released together. The code stays the
only source of truth: every change is written to your files with LibCST.

- **Plan.** Planned agents (`# agentsdiagram: planned`) and planned tools (a typed stub that raises
  `NotImplementedError("agentsdiagram: planned")`) are drawn dashed with a *planned* badge and
  listed by `check` as AD401 (info).
- **Edit operations:** plan an agent (optionally managed by / delegated from another), plan a tool,
  add an MCP server, connect two agents (smolagents `managed_agents`, PydanticAI delegation tool),
  disconnect, remove, change the model or the instructions, and move a PydanticAI agent's settings
  to an Agent Spec. Idiomatic code per framework; imports merged isort-style; imports an edit
  leaves unused are removed. Edits are refused, with a reason, when the code changed since the
  diagram was drawn or when they cannot be made cleanly.
- **CLI:** `agentsdiagram edit <operation>` (prints the diff; `--dry-run`, `--json`) and
  `agentsdiagram serve`, a live diagram in the browser that redraws on file changes and can edit.
- **Viewer:** *Plan agent* button, *Plan and edit* actions and a *Connections* list (with
  disconnect) in the node panel, success notices, and the new node selected after an edit.
  Informational diagnostics get their own neutral counter.
- **VS Code:** edits are applied as workspace edits (undo works) and saved
  (`agentsdiagram.edits.save`); command `agentsdiagram.edit` for scripts and other extensions.
- **LSP:** `agentsdiagram/edit` returns a versioned `WorkspaceEdit`; protocol version 2.
- **Analyzer:** `Agent.from_file(...)` keeps the tools and toolsets passed in code, and spec paths
  written as `Path(__file__).parent / "x.yaml"` are followed.
- Fixed diagnostics and code lenses missing when the workspace path goes through a symlink (for
  example `/var` → `/private/var` on macOS).
- Docs: getting started, seven tutorials (from one agent to planning a team, CI and coding
  agents), command line, plan and edit, VS Code guides; smolagents is presented first throughout.
- Website: documentation pages rendered from `docs/`, five live demos (one made by the planner
  itself), a *Plan and edit* section with a video, social preview image, `llms.txt` and sitemap.
- Examples: `hello_smolagents` and `hello_pydantic_ai`, one agent each.

## 0.1.3 — 2026-10-22

- Releases: Open VSX now publishes with trusted publishing (OIDC, no token).
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
- CLI: `scan -o` creates missing folders; hint when `--include` matches nothing (globs are relative to the project root), and the
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
