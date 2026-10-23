# VS Code extension

**Agents Diagram** keeps a live diagram of your agents next to your code and lets you plan and edit
them from it. It works in VS Code and, from [Open VSX](https://open-vsx.org/extension/alex-roc/agentsdiagram),
in Cursor, Windsurf and Positron.

## Install

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/). The extension runs the
   analyzer with `uvx`, pinned to its own version, so you do not install anything else; the first
   start downloads it.
2. Install **Agents Diagram** from the
   [Marketplace](https://marketplace.visualstudio.com/items?itemName=alex-roc.agentsdiagram) or
   Open VSX.
3. Open a Python file. The analyzer starts, diagnostics appear in the Problems panel and
   "Show … in diagram" code lenses appear above agents.

The Python extension is not needed: the analysis is static and does not depend on your
interpreter. To use your own checkout or environment instead of `uvx`, set
`agentsdiagram.server.command` (for example `["uv", "run", "agentsdiagram", "lsp"]`).

## Use the diagram

- **Agents Diagram: Show Workspace Diagram** (also in the folder context menu), or the icon in
  the editor title for the current file.
- Click a node for its panel: model, instructions, signature, docstring, problems, connections.
  **Go to code** opens its definition. Moving the cursor in the editor selects the node under it.
- The diagram follows unsaved edits; a file with a syntax error keeps its last valid version,
  faded (`stale`).
- `/` searches, the legend filters kinds, **Problems** lists the diagnostics, **Copy Mermaid**
  copies the diagram.

## Plan and edit

With the diagram open:

- **Plan agent** in the toolbar writes a planned agent. Choose a parent to make it a managed agent
  (smolagents) or a specialist with a delegation tool (PydanticAI).
- In an agent's panel: **Add tool**, **Add MCP server**, **Plan managed agent / specialist**,
  **Hand work to…**, **Change model**, **Instructions**, **Move to Agent Spec** (PydanticAI),
  **Remove**.
- In **Connections**, the unlink button removes a relation.

Each action is applied as a workspace edit, so `Ctrl/Cmd+Z` undoes it, and the changed files are
saved unless they already had unsaved changes (setting `agentsdiagram.edits.save`). The diagram
redraws and selects what you just created. What is written for each framework is described in
[Plan and edit](editing.md).

Other extensions and scripts can run the same edits with the command `agentsdiagram.edit`, passing
an `EditParams` object (see [the IR reference](ir.md)).

## Settings

| Setting | Description |
| --- | --- |
| `agentsdiagram.server.command` | Command that starts the server, used as is (machine scope, restricted in untrusted workspaces) |
| `agentsdiagram.server.uvPath` | Absolute path to `uvx` if it is not found automatically |
| `agentsdiagram.include` / `agentsdiagram.exclude` | Glob patterns passed to the analyzer |
| `agentsdiagram.codeLens.enabled` | Toggle the "Show in diagram" code lenses |
| `agentsdiagram.edits.save` | Save the files an edit changes (default on) |

## Troubleshooting

- **"needs uv"**: install uv, or set `agentsdiagram.server.uvPath` if it is installed somewhere
  unusual (apps started from the dock do not see your shell's `PATH`).
- **Nothing appears**: run **Agents Diagram: Show Output** for the server log, and
  **Restart Language Server** after changing settings.
- **Untrusted workspace**: a custom `agentsdiagram.server.command` is ignored until you trust the
  folder.
