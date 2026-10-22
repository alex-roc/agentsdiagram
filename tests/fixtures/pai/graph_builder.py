"""pydantic-graph GraphBuilder with a decision, and an agent run inside a step."""

from dataclasses import dataclass

from pydantic_ai import Agent
from pydantic_graph import GraphBuilder, StepContext

summarizer = Agent("openai:gpt-5-mini", name="summarizer")


@dataclass
class State:
    text: str = ""


def build():
    g = GraphBuilder(state_type=State, output_type=str)

    @g.step
    async def fetch(ctx: StepContext[State, None, None]) -> str:
        """Fetch the document."""
        return "text"

    @g.step
    async def summarize(ctx: StepContext[State, None, str]) -> str:
        """Summarize with an agent."""
        return (await summarizer.run(ctx.inputs)).output

    @g.step
    async def skip(ctx: StepContext[State, None, str]) -> str:
        return ctx.inputs

    g.add(
        g.edge_from(g.start_node).to(fetch),
        g.edge_from(fetch).to(
            g.decision()
            .branch(g.match(str, matches=lambda s: len(s) > 100).label("long").to(summarize))
            .branch(g.match(str).to(skip))
        ),
        g.edge_from(summarize, skip).to(g.end_node),
    )
    return g.build()
