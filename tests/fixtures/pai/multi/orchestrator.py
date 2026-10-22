"""Delegation (agent inside a tool), a factory, and a programmatic hand-off workflow."""

from pydantic_ai import Agent, RunContext
from pydantic_ai_harness import SubAgent, SubAgents

from .agents import researcher, writer


def make_reviewer(model: str) -> Agent:
    return Agent(model, instructions="Review the report critically.")


reviewer = make_reviewer("openai:gpt-5")

lead = Agent(
    "openai:gpt-5",
    name="lead",
    capabilities=[SubAgents(agents=[SubAgent(reviewer, name="reviewer")])],
)


@lead.tool
async def research(ctx: RunContext[None], topic: str) -> str:
    """Delegate research to the researcher agent."""
    result = await researcher.run(topic, usage=ctx.usage)
    return result.output


async def pipeline(topic: str) -> str:
    """Research, then write: a hand-off between two agents."""
    notes = await researcher.run(topic)
    report = await writer.run(notes.output)
    return report.output
