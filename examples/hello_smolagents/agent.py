"""One smolagents agent with two tools: the smallest thing agentsdiagram can draw."""

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
