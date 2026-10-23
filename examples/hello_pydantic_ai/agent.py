"""One PydanticAI agent with two tools: the smallest thing agentsdiagram can draw."""

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
