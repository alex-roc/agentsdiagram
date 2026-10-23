# Changelog

## 0.4.1 — 2026-10-23

- The plan and edit buttons fit a narrow diagram panel: one per row, labels in full.

## 0.4.0 — 2026-10-23

- Plan and edit from the diagram: **Plan agent**, and in an agent's panel **Add tool**, **Add MCP
  server**, **Plan managed agent / specialist**, **Hand work to…**, **Change model**,
  **Instructions**, **Move to Agent Spec** (PydanticAI) and **Remove**. A **Connections** list with
  disconnect buttons.
- Changes are applied as workspace edits, so Undo works; changed files are saved unless they had
  unsaved changes (setting `agentsdiagram.edits.save`).
- Planned agents and tools are drawn dashed with a *planned* badge.
- Fixed diagnostics and code lenses missing on symlinked workspace paths.

## 0.1.3 — 2026-10-22

- Redesigned diagram: follows your light or dark theme, icons per node kind, a legend that
  filters node kinds, a Problems drawer, a minimap, and selecting a node highlights its neighbors.
- Fixed duplicated "Show in diagram" code lenses after restarting the server during startup.

## 0.1.1

- No functional changes: first release published automatically from CI.

## 0.1.0

- First release: diagram panel, code lenses, diagnostics, Mermaid export.
