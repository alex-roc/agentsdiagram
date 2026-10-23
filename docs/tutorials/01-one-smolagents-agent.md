# 1. One smolagents agent

The smallest useful diagram: one agent and the tools it can call. You will draw it, read it, and
see how the diagram reacts to a mistake.

## The code

[`examples/hello_smolagents/agent.py`](../../examples/hello_smolagents/agent.py):

```python
from smolagents import CodeAgent, InferenceClientModel, WebSearchTool, tool


@tool
def get_weather(city: str) -> str:
    """Current weather for a city.

    Args:
        city: Name of the city, e.g. "Cochabamba".
    """
    return "sunny, 24 °C"


assistant = CodeAgent(
    tools=[get_weather, WebSearchTool()],
    model=InferenceClientModel(model_id="Qwen/Qwen3-Next-80B-A3B-Thinking"),
    name="assistant",
    instructions="Answer travel questions. Check the weather before suggesting plans.",
)
```

## Draw it

```bash
uvx agentsdiagram scan examples/hello_smolagents -f html -o hello.html
```

[▶ Open the live diagram](https://alex-roc.github.io/agentsdiagram/demo/hello-smolagents.html)

What you see:

- **assistant** is an agent card with its model, `InferenceClientModel('Qwen/…')`.
- **get_weather** is a tool (a `@tool` function). Click it: the panel shows its signature and
  docstring, which is what the model reads.
- **web_search** is a smolagents default tool. It is drawn with the name the model sees
  (`web_search`), not the class name (`WebSearchTool`).

`final_answer`, which smolagents adds to every agent, is left out.

## Let it catch a mistake

smolagents builds a tool's schema from its type hints and its `Args:` docstring. Remove the
`-> str` from `get_weather` and run:

```bash
uvx agentsdiagram check examples/hello_smolagents
```

```
examples/hello_smolagents/agent.py:7:5: warning AD203 @tool `get_weather` needs type hints (return type missing).
```

In the viewer the tool gets a warning marker and the **Problems** drawer lists it. Other checks
catch managed agents without a `description` (AD201) and two tools with the same name (AD202).

## Next

[2. One PydanticAI agent](02-one-pydantic-ai-agent.md): the same agent written with PydanticAI.
