"""Escalation workflow as a pydantic-graph: classify, then auto-reply or page a human."""

from dataclasses import dataclass

from pydantic_graph import GraphBuilder, StepContext

from .agents import triage


@dataclass
class Ticket:
    text: str
    priority: str = "normal"


def build_escalation():
    g = GraphBuilder(state_type=Ticket, output_type=str)

    @g.step
    async def classify(ctx: StepContext[Ticket, None, None]) -> str:
        """Estimate the priority of the ticket."""
        return ctx.state.priority

    @g.step
    async def auto_reply(ctx: StepContext[Ticket, None, str]) -> str:
        """Let the triage agent answer."""
        return (await triage.run(ctx.state.text)).output

    @g.step
    async def page_on_call(ctx: StepContext[Ticket, None, str]) -> str:
        """Page the on-call engineer."""
        return "paged"

    g.add(
        g.edge_from(g.start_node).to(classify),
        g.edge_from(classify).to(
            g.decision()
            .branch(g.match(str, matches=lambda p: p == "urgent").label("urgent").to(page_on_call))
            .branch(g.match(str).label("normal").to(auto_reply))
        ),
        g.edge_from(auto_reply, page_on_call).to(g.end_node),
    )
    return g.build()
