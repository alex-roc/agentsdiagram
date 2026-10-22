"""smolagents: a manager CodeAgent with managed agents, default tools and @tool."""

from smolagents import CodeAgent, InferenceClientModel, ToolCallingAgent, VisitWebpageTool, WebSearchTool, tool

model = InferenceClientModel(model_id="Qwen/Qwen3-Next-80B-A3B-Thinking")


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city.

    Args:
        city: The city name.
    """
    return "sunny"


web_agent = ToolCallingAgent(
    tools=[WebSearchTool(), VisitWebpageTool()],
    model=model,
    name="web_agent",
    description="Browses the web for you.",
    max_steps=10,
)

manager = CodeAgent(
    tools=[get_weather],
    model=model,
    managed_agents=[web_agent],
    additional_authorized_imports=["time", "json"],
    planning_interval=3,
)
