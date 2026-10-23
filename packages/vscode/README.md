# Agents Diagram

See, plan and edit your **smolagents** and **PydanticAI** agents in a live diagram next to your
code: agents, tools, MCP servers, managed agents, delegation, workflows and flows.

The analysis is static: it reads your Python source and never imports or runs it. No API keys, no
dependencies of your project.

![Agents diagram](https://raw.githubusercontent.com/alex-roc/agentsdiagram/main/docs/images/viewer.png)

## See

- An interactive diagram of the workspace or of one file, in your light or dark theme.
- Click a node to see its details and neighbors; **Go to code** jumps to its source. Move the
  cursor in a `.py` file and the diagram selects the node under it.
- It follows your edits as you type, unsaved changes included.
- Search with `/`, filter node kinds from the legend, open **Problems** from the toolbar.
- "Show in diagram" code lenses above agents, and diagnostics in the Problems panel (for
  example a smolagents managed agent without a description, or PydanticAI v1 API).
- Export to Mermaid.

## Plan and edit

The diagram can write code too. Every change is a normal edit: **Undo** works.

- **Plan agent** (toolbar) writes a new agent marked `# agentsdiagram: planned`, optionally managed
  by (smolagents) or delegated from (PydanticAI) another agent.
- On an agent: **Add tool** (a typed stub that raises `NotImplementedError` until you write it),
  **Add MCP server**, **Hand work to…** another agent, **Change model**, **Instructions**,
  **Move to Agent Spec** (PydanticAI) and **Remove**.
- **Connections** lists every relation of a node, with a disconnect button.

The generated code is idiomatic for each framework, imports included, and nothing else in the file
changes. Edits are refused, with a reason, if the file changed since the diagram was drawn or if
the change cannot be made cleanly.

## Requirements

One of:

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed. The extension runs `uvx --from "agentsdiagram[lsp]==<version>" agentsdiagram lsp`; the first start downloads the analyzer.
- Your own server command in `agentsdiagram.server.command`, e.g. `["uv", "run", "agentsdiagram", "lsp"]` (needs the `agentsdiagram[lsp]` extra).

No Python extension is required, so it works in Cursor, Windsurf and Positron too.

## Commands

| Command | What it does |
| --- | --- |
| Agents Diagram: Show Workspace Diagram | Opens the diagram for the whole workspace |
| Agents Diagram: Show Diagram of Current File | Scopes the diagram to the active file |
| Agents Diagram: Export as Mermaid | Opens a Markdown document with a Mermaid block |
| Agents Diagram: Restart Language Server | Restarts the analyzer |
| Agents Diagram: Show Output | Opens the "Agents Diagram" log |

## Settings

| Setting | Description |
| --- | --- |
| `agentsdiagram.server.command` | Command that starts the server, used as is (machine scope, restricted in untrusted workspaces) |
| `agentsdiagram.server.uvPath` | Absolute path to `uvx` if it is not found automatically |
| `agentsdiagram.include` / `agentsdiagram.exclude` | Glob patterns passed to the analyzer |
| `agentsdiagram.codeLens.enabled` | Toggle the "Show in diagram" code lenses |
| `agentsdiagram.edits.save` | Save the files an edit changes (default on; files with unsaved changes are left alone) |

## Privacy

Everything runs locally. The analyzer reads your files without executing them and sends nothing over the network. The only network access is the one-time download of the `agentsdiagram` package by `uvx` (skipped if you use `agentsdiagram.server.command`).

## Links

[Website, tutorials and live demos](https://alex-roc.github.io/agentsdiagram/) ·
[Source and issues](https://github.com/alex-roc/agentsdiagram) · MIT licensed.
