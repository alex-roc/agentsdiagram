# The IR (intermediate representation)

JSON produced by `agentsdiagram scan -f json` and by the language server (`agentsdiagram/graph`).
Schema: `agentsdiagram schema` / [`packages/protocol/ir.schema.json`](../packages/protocol/ir.schema.json).
Current version: `ir_version: "1"`.

```jsonc
{
  "ir_version": "1", "tool_version": "0.1.0", "root": "/abs/project",
  "frameworks": ["pydantic_ai"],
  "files":  [{ "path": "app/agents.py", "module": "app.agents", "frameworks": ["pydantic_ai"], "status": "ok", "sha256": "…" }],
  "nodes":  [{ "id": "pydantic_ai:agent:app.agents.lead", "kind": "agent", "framework": "pydantic_ai",
               "name": "lead", "status": "resolved", "source": { "file": "app/agents.py", "range": {…}, "name_range": {…} },
               "attrs": { "model": "openai:gpt-5", "instructions": "…", "badges": ["Thinking"], "extra": {} } }],
  "edges":  [{ "id": "uses:…->…", "kind": "uses", "source": "…", "target": "…", "label": null, "order": null,
               "wrappers": ["prefixed(\"math\")"], "ref": { … } }],
  "diagnostics": [{ "code": "AD201", "severity": "error", "message": "…", "ref": { … }, "node_id": "…" }]
}
```

Positions: `line` is 1-based, `column` is 0-based and counted in code points.

## Node kinds

| kind | meaning |
|---|---|
| `agent` | an agent (`Agent`, `CodeAgent`, `ToolCallingAgent`, an Agent Spec) |
| `tool` | a function or `Tool` the model can call |
| `toolset` | a group of tools (`FunctionToolset`, wrappers, MCP config files, dynamic toolsets) |
| `mcp_server` | an MCP server (stdio command or URL) |
| `native_tool` | a provider-side tool (`WebSearchTool`, `WebFetch`…) |
| `capability` | a PydanticAI capability with structure (`Capability`, `SubAgents`, `DynamicWorkflow`) |
| `workflow` | a plain function that runs several agents in sequence (hand-off) |
| `external_tool_source` | tools loaded from the Hub, a Space, LangChain… |
| `graph` / `graph_step` | pydantic-graph graphs and their steps (incl. `start`, `end`, `decision`, joins) |
| `dynamic` | an expression that cannot be resolved statically |

## Edge kinds

`uses` (agent → tool/toolset/mcp/native/capability) · `provides` (toolset/capability → tool) ·
`wraps` (wrapper toolset → inner) · `delegates_to` (tool/capability → agent) ·
`manages` (smolagents manager → managed agent) · `runs` (workflow/graph step → agent, ordered) ·
`contains` (graph → step) · `transitions` (step → step).

## Status

`resolved` · `partial` (built in a function / factory, arguments may vary) · `dynamic` ·
`planned` (roadmap: stubs written by the planner) · `stale` (file has a syntax error; last valid version).

## Diagnostic codes

| code | severity | meaning |
|---|---|---|
| AD000 | error / warning | syntax error (warning when a previous valid version is shown) |
| AD001 | info | expression cannot be resolved statically (dynamic node) |
| AD002 | info | referenced config/spec file not found |
| AD101 | warning | PydanticAI v1 API (`MCPServerStdio`, `mcp_servers=`, `builtin_tools=`…) |
| AD201 | error | smolagents managed agent without `name` and `description` |
| AD202 | warning | smolagents agent with two tools/agents of the same name |
| AD203 | warning | smolagents `@tool` without type hints or `Args:` docstring |
| AD204 | error | smolagents `executor_type` that no longer exists |
| AD301 | info | agent created inside a function |
| AD900 | error | an adapter crashed on a file (please report it) |
