# PydanticAI adapter

Verified against **pydantic-ai 2.59.0**, **pydantic-ai-harness 0.59.0** and **pydantic-graph 2.59.0**
(October 2026). Symbols: [`adapters/pydantic_ai/symbols.py`](../../src/agentsdiagram/adapters/pydantic_ai/symbols.py).

| Construct | Result |
|---|---|
| `Agent(model, name=, instructions=/system_prompt=, deps_type=, output_type=, description=)` | `agent` node (name from `name=` or the variable) |
| `Agent(...)` inside a function | `partial` agent; `x = factory(...)` gets its own node |
| `Agent.from_file("x.yaml")` (literal path) | agent from the Agent Spec: model, instructions, capabilities, MCP |
| `@agent.tool`, `@agent.tool_plain` (`name=`, `requires_approval=`) | `tool` with docstring, signature, `takes_ctx` |
| `tools=[f, Tool(f, ...), Tool.from_schema(...)]` | `uses` → `tool` |
| `@agent.instructions`, `@agent.system_prompt` | `attrs.dynamic_instructions` |
| `@agent.output_validator`, `@agent.on_event` | badges |
| `@agent.toolset` | `dynamic` toolset |
| `FunctionToolset(tools=[...])`, `@ts.tool`, `@ts.tool_plain`, `ts.add_function(f)` | `toolset` → `provides` → tools |
| `PrefixedToolset`, `FilteredToolset`, `RenamedToolset`, `ApprovalRequiredToolset`… / `CombinedToolset` | `toolset` → `wraps` |
| `.prefixed()`, `.filtered()`, `.renamed()`, `.approval_required()`… | edge `wrappers` |
| `ExternalToolset` | `partial` toolset |
| `MCPToolset("https://…")`, `MCPToolset(StdioTransport(command, args))`, `MCPToolset(Client(...))` | `mcp_server` with url/command |
| `load_mcp_toolsets("mcp.json")` (literal path) | toolset → one `mcp_server` per entry |
| `capabilities=[NativeTool(WebSearchTool())]`, `WebSearch()`, `WebFetch()`… | `native_tool` |
| `capabilities=[MCP(url=...)]` | `mcp_server` |
| `capabilities=[Capability(id=, tools=, toolsets=)]`, `@cap.tool` | `capability` → `provides` |
| `capabilities=[Toolset(ts)]` | `uses` → toolset |
| `SubAgents(agents=[SubAgent(a, name=)])` (harness) | `capability` → `delegates_to` → agent |
| `DynamicWorkflow(agents=[...])` (harness) | `dynamic` capability → `delegates_to` |
| any other capability (`Thinking`, `Caching`, `TemporalDurability`…) | badge on the agent |
| `other.run/run_sync/run_stream/iter(...)` inside a tool | tool → `delegates_to` → agent |
| function running ≥ 2 agents | `workflow` → ordered `runs` |
| `GraphBuilder`: `@g.step`, `g.join(...)`, `edge_from(...).to(...)`, `.map()`, `.label()`, `decision().branch(match(T).label().to())` | `graph` with `graph_step`s and `transitions` |
| `BaseNode` subclasses (`run()` return annotation, `End[T]`) | `graph` with `transitions` |
| v1: `MCPServerStdio/SSE/StreamableHTTP/HTTP`, `mcp_servers=`, `builtin_tools=`, `load_mcp_servers`, `UrlContextTool` | recognised + AD101 |

Not detected (shown as `dynamic` when referenced): toolsets/tools built at runtime, agents
passed as parameters, output functions that hand off (planned).

FastMCP servers (`@server.tool()`) are deliberately **not** treated as agent tools.
