# smolagents adapter

Verified against **smolagents 1.26.0** (October 2026). Symbols:
[`adapters/smolagents/symbols.py`](../../src/agentsdiagram/adapters/smolagents/symbols.py).

| Construct | Result |
|---|---|
| `CodeAgent(...)`, `ToolCallingAgent(...)` | `agent`: `name`, `description`, `instructions`, model (`Class('model_id')`, aliases like `OpenAIServerModel` → `OpenAIModel`), `planning_interval`, `max_steps`, `executor_type`, `additional_authorized_imports` |
| `tools=[...]` | `uses` → tool / MCP / external source |
| `managed_agents=[...]` | `manages` → agent |
| `add_base_tools=True` | implicit `web_search`, `visit_webpage` (+ `python_interpreter` on `ToolCallingAgent`), as in `agents.py::_setup_tools` |
| `@tool` functions | `tool` with docstring and signature |
| `class X(Tool)` with `name`, `description`, `inputs`, `output_type`, `forward` | `tool` |
| default tools (`WebSearchTool()`, `DuckDuckGoSearchTool()`, `VisitWebpageTool()`…) | `tool` with the name the library exposes |
| `Tool.from_space/from_langchain/from_gradio/from_code` | `partial` tool |
| `Tool.from_hub`, `load_tool`, `ToolCollection.from_hub` | `external_tool_source` |
| `with ToolCollection.from_mcp(params) as tc: ... tools=[*tc.tools]` | `mcp_server` (command or URL) |
| `with MCPClient(params) as tools: ... tools=tools` | `mcp_server` |
| `managed.run(...)` inside a `@tool` | `delegates_to` |

Diagnostics: AD201 (managed agent without `name`/`description`), AD202 (two tools/agents with the
same name — several default tools are all called `web_search`), AD203 (`@tool` without type hints
or `Args:`), AD204 (`executor_type="wasm"`, removed in 1.26).

`final_answer` is added by smolagents to every agent and is not drawn.

Note: in 1.26 `agent.to_dict()` returns `tools` and `managed_agents` as lists of dicts (with
code), not names; the oracle tests use it as ground truth.

## Editing

What `agentsdiagram edit` and the diagram write for smolagents (see [Plan and edit](../editing.md)):
a planned agent is a `CodeAgent`/`ToolCallingAgent` with `tools=[]` and the file's model; a planned
tool is a `@tool` function with type hints and an `Args:` docstring, defined above the agent; an
MCP server is an `MCPClient(..., structured_output=True)` spread into `tools=`; connecting adds to
`managed_agents=` (and the `name`/`description` it requires); changing the model sets this agent's
`model_id`. Agents must be module-level variables; the manager must come after the managed agent
in the same file (or import it).
