"""An agent with decorated tools, a Tool(...) and dynamic instructions."""

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext, Tool


@dataclass
class Deps:
    city: str


def convert_currency(amount: float, to: str) -> float:
    """Convert an amount of USD to another currency."""
    return amount


assistant = Agent(
    "openai:gpt-5",
    name="assistant",
    instructions="You are a helpful travel assistant.",
    deps_type=Deps,
    output_type=str,
    tools=[Tool(convert_currency, takes_ctx=False, requires_approval=True)],
)


@assistant.tool
async def weather(ctx: RunContext[Deps], day: str) -> str:
    """Weather forecast for the user's city."""
    return f"sunny in {ctx.deps.city} on {day}"


@assistant.tool_plain(name="roll")
def roll_dice() -> int:
    """Roll a six-sided die."""
    return 4


@assistant.instructions
def add_city(ctx: RunContext[Deps]) -> str:
    return f"The user lives in {ctx.deps.city}."


@assistant.output_validator
def not_empty(output: str) -> str:
    return output
