# 2. One PydanticAI agent

The same travel assistant, written with PydanticAI. The diagram looks the same, because it shows
what the agent can do, not how the library spells it.

## The code

[`examples/hello_pydantic_ai/agent.py`](../../examples/hello_pydantic_ai/agent.py):

```python
from pydantic_ai import Agent, RunContext

assistant = Agent(
    "openai:gpt-5-mini",
    name="assistant",
    instructions="Answer travel questions. Check the weather before suggesting plans.",
    deps_type=str,
)


@assistant.tool_plain
def get_weather(city: str) -> str:
    """Current weather for a city."""
    return "sunny, 24 °C"


@assistant.tool
def home_city(ctx: RunContext[str]) -> str:
    """The city the user lives in."""
    return ctx.deps
```

## Draw it

```bash
uvx agentsdiagram scan examples/hello_pydantic_ai -f html -o hello.html
```

[▶ Open the live diagram](https://alex-roc.github.io/agentsdiagram/demo/hello-pydantic-ai.html)

- Tools registered with `@assistant.tool` and `@assistant.tool_plain` are linked to the agent
  even though they are written after it. Click **home_city**: *Takes context: Yes*, because its
  first parameter is a `RunContext`.
- The agent panel shows the model, the instructions and the `deps_type`.

## What else it reads

PydanticAI has more ways to give an agent tools, and the diagram follows them all:
`tools=[f, Tool(f)]`, toolsets (`FunctionToolset`, `.prefixed("crm")`, `.filtered(...)`),
`MCPToolset` servers, capabilities (`WebSearch()`, `NativeTool(...)`, `Thinking()` as a badge),
Agent Specs loaded with `Agent.from_file("agent.yaml")`, and pydantic-graph flows. The
[coverage page](../adapters/pydantic_ai.md) lists every construct.

If your code still uses the v1 API (`mcp_servers=`, `MCPServerStdio`), `agentsdiagram check`
reports it as AD101 with the v2 replacement.

## Next

[3. Teams of agents](03-teams-of-agents.md): managers, specialists and delegation.
