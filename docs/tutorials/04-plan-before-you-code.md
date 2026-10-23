# 4. Plan before you code

Before writing a multi-agent system you usually sketch it: who does what, which tools each agent
needs, who calls whom. With agentsdiagram the sketch *is* code. Every box you add is written to
your files as a planned stub, so the plan cannot drift away from the implementation.

We will grow the travel assistant from [tutorial 1](01-one-smolagents-agent.md) into a small team:
the assistant keeps answering questions and hands bookings to a new `booker` agent, which needs a
flight search tool and a maps MCP server.

## In the browser or in VS Code

Work on a copy of the example, so the planner writes to your own folder:

```bash
cp -r examples/hello_smolagents ~/travel && cd ~/travel
uvx agentsdiagram serve
```

(or open `~/travel` in VS Code with the Agents Diagram extension and run **Show Workspace
Diagram**). Then:

1. Click **assistant**, then **Plan managed agent**. Name it `booker`, describe it ("Finds and
   books flights and hotels.") and **Write planned agent**.
2. With **booker** selected, **Add tool**: `search_flights`, parameters
   `origin: str, destination: str, date: str`, returns `list[dict]`.
3. **Add MCP server** with the URL `https://maps.example.com/mcp`.

After each step the diagram is redrawn from the code, and the new node is selected.

## Or from the command line

The same three steps, each printing its diff:

```bash
agentsdiagram edit add-agent booker --parent assistant \
    --description "Finds and books flights and hotels."   # written next to its parent
agentsdiagram edit add-tool booker search_flights \
    --params "origin: str, destination: str, date: str" --returns "list[dict]" \
    --description "Flights between two cities on a date."
agentsdiagram edit add-mcp booker --url https://maps.example.com/mcp
```

[▶ Open the live diagram](https://alex-roc.github.io/agentsdiagram/demo/planning.html)

## What was written

```python
@tool
def search_flights(origin: str, destination: str, date: str) -> list[dict]:
    """Flights between two cities on a date.

    Args:
        origin: Origin.
        destination: Destination.
        date: Date.
    """
    raise NotImplementedError("agentsdiagram: planned")


maps_mcp = MCPClient({"url": "https://maps.example.com/mcp", "transport": "streamable-http"}, structured_output=True)

# agentsdiagram: planned
booker = ToolCallingAgent(
    tools=[search_flights, *maps_mcp.get_tools()],
    model=InferenceClientModel(model_id="Qwen/Qwen3-Next-80B-A3B-Thinking"),
    name="booker",
    description="Finds and books flights and hotels.",
)

assistant = CodeAgent(
    tools=[get_weather, WebSearchTool()],
    model=InferenceClientModel(model_id="Qwen/Qwen3-Next-80B-A3B-Thinking"),
    name="assistant",
    instructions="Answer travel questions. Check the weather before suggesting plans.",
    managed_agents=[booker],
)
```

Things to notice:

- It is idiomatic smolagents: the tool has the type hints and the `Args:` docstring smolagents
  requires, the managed agent has a `name` and a `description`, the tool is defined before the
  agent that uses it, and `ToolCallingAgent`/`MCPClient` were added to the existing imports.
- `booker` reuses the model the file already uses.
- Nothing else in the file changed, not even blank lines.
- The planned marks are ordinary Python: the comment `# agentsdiagram: planned` and the
  `raise NotImplementedError("agentsdiagram: planned")` body. The program still imports and runs.

## The plan is your to-do list

```bash
agentsdiagram check
```

```
agent.py:17:5: info AD401 `search_flights` is planned: implement it.
agent.py:31:1: info AD401 `booker` is planned: remove the `# agentsdiagram: planned` comment when it is ready.
```

Write the body of `search_flights` and its node loses the dashed outline. Delete the comment above
`booker` when the agent is ready. AD401 is informational: it never fails `check`.

## The same plan in PydanticAI

Planning works the same way with PydanticAI, written the PydanticAI way: a planned agent is an
`Agent(...)`, a planned tool is an `@agent.tool_plain` stub, an MCP server is an `MCPToolset` in
`toolsets=[...]`, and **Plan specialist** on an agent writes a delegation tool:

```python
@triage.tool
async def ask_sales(ctx: RunContext[Deps], task: str) -> str:
    """Pricing, plans and upgrades."""
    result = await sales.run(task, usage=ctx.usage)
    return result.output
```

## Next

[5. Edit from the diagram](05-edit-from-the-diagram.md): connect, rewire, change models and remove.
