# Plan and edit

agentsdiagram can change your code as well as draw it. You can plan agents and tools that do not
exist yet, connect agents, swap a model or remove a tool, from the diagram (VS Code or
`agentsdiagram serve`) or from the command line (`agentsdiagram edit`).

The rule behind all of it: **the code is the only source of truth.** An edit is a change to your
Python files, made with [LibCST](https://libcst.readthedocs.io) so everything it does not touch
keeps its formatting and comments. The diagram is then drawn again from the new code. There is no
project file, no hidden state and nothing to keep in sync.

## Where you can edit

| Front end | How the change is applied |
|---|---|
| VS Code / Cursor / Windsurf / Positron | as a normal workspace edit: **Undo** (`Ctrl/Cmd+Z`) works, and files that had no unsaved changes are saved (setting `agentsdiagram.edits.save`) |
| `agentsdiagram serve` | the server writes the files; use git to review or revert |
| `agentsdiagram edit <operation>` | writes the files and prints the diff; `--dry-run` only prints it |

A static page made with `agentsdiagram scan -f html` (and the website demos) is read only.

## Planned code

A planned agent or tool is real code that says it is not finished. agentsdiagram recognises two
markers and draws those nodes with a dashed outline and a **planned** badge:

```python
# agentsdiagram: planned
researcher = ToolCallingAgent(  # any statement under this comment
    tools=[],
    model=model,
    name="researcher",
    description="Finds sources for a question.",
)


@tool
def fetch_paper(arxiv_id: str) -> str:
    """Download a paper from arXiv.

    Args:
        arxiv_id: Arxiv id.
    """
    raise NotImplementedError("agentsdiagram: planned")  # a tool whose body raises this
```

Implement the tool (replace the `raise`) or delete the comment, and the node is no longer
planned. `agentsdiagram check` lists every planned node as `AD401` (info), so the plan doubles as a
to-do list; it never fails a build.

Planned code runs: a planned agent is a normal agent, and a planned tool raises a clear error if
the model calls it before you write it.

## Operations

| Operation | smolagents | PydanticAI |
|---|---|---|
| **Plan an agent** (`add_agent`) | `CodeAgent`/`ToolCallingAgent` with `tools=[]` and the model the file already uses; with a parent, added to its `managed_agents=[...]` (with the `name` and `description` smolagents requires) | `Agent("<model>", name=...)`; with a parent, the parent gets a delegation tool (see *connect*) |
| **Plan a tool** (`add_tool`) | `@tool` function defined above the agent, with type hints and the `Args:` docstring smolagents needs, added to `tools=[...]` | `@agent.tool_plain` function after the agent |
| **Add an MCP server** (`add_mcp`) | `MCPClient({"url": ..., "transport": "streamable-http"}, structured_output=True)` or `MCPClient(StdioServerParameters(...))`, spread into `tools=[*client.get_tools()]` | `MCPToolset("https://…")` or `MCPToolset(StdioTransport(command, args))` in `toolsets=[...]` |
| **Hand work to** (`connect`) | adds the agent to `managed_agents=[...]` | writes `@a.tool async def ask_b(ctx, task) -> str` that runs `b` with the same usage (and the same deps when both agents have the same `deps_type`) |
| **Disconnect** (`disconnect`) | removes the item from `tools=`, `managed_agents=`… | removes the list item, or the `@agent.tool` decorator |
| **Remove** (`remove`) | removes the references, then the definition if nothing else uses it | same; an agent also takes its `@agent.tool`/`@agent.instructions` functions with it |
| **Change the model** (`set_model`) | sets `model_id` of this agent's model (other agents sharing a `model` variable are not touched) | replaces the model string |
| **Instructions** (`set_instructions`) | `instructions="..."`; empty removes it | same |
| **Move to an Agent Spec** (`export_spec`) | — | moves the literal settings (model, name, description, instructions and literal capabilities such as `Thinking(effort="high")`) to `<agent>.agent.yaml` and loads it with `Agent.from_file(Path(__file__).parent / "…")`; tools, toolsets and `deps_type` stay in Python |

Imports are added where isort/ruff would put them (merged into an existing `from x import (...)`
when there is one), and an import that an edit leaves unused is removed. Cross-file connections
add the import too (relative inside a package).

## Safety

- **Nothing is executed.** Edits are computed from the parsed source, like the diagram.
- **Edits are anchored.** A request names nodes by id, and also sends the hash of every file the
  diagram was drawn from. If one of those files changed in the meantime, the edit is refused with
  "changed since the diagram was drawn"; refresh and try again. In VS Code the edit also carries
  the document version.
- **Refusals are explicit.** agentsdiagram does not guess. It refuses, with a reason, when the
  change is not a list item or a decorator it can rewrite cleanly. For example: removing an agent
  that a tool still runs (`ask_billing runs it (agents.py:43); remove that first`), disconnecting
  a delegation written as a call inside a function body, or editing an agent built by a factory.
- **Every result is valid Python.** Each changed file is parsed again before anything is written.

## Limits

- Agents must be assigned to a variable at module level (`x = Agent(...)`, also inside a
  module-level `with` block for smolagents). Agents built inside functions are drawn but edited
  by hand.
- Long or computed instructions (a constant, an f-string, `system_prompt=`) are shown but not
  edited from the diagram, so nothing is lost.
- pydantic-graph flows and hand-off workflows are read only.

## The protocol

Every front end sends the same request (`EditParams` in the [IR schema](ir.md)):

```json
{
  "request": { "op": "add_tool", "agent": "smolagents:agent:app.team.analyst", "name": "fetch_dataset",
               "params": "url: str, limit: int = 100", "description": "Download a CSV dataset." },
  "expect": [{ "file": "app/team.py", "sha256": "…" }]
}
```

and gets an `EditResult` back: `ok`, a `message`, the `files` changed and the id of the node to
`focus`. Over LSP (`agentsdiagram/edit`) the result also carries the `WorkspaceEdit` the editor
applies. In Python: `agentsdiagram.edit.plan_edit(root, request)` returns the new text of every
file without writing anything.
