"""The agents of the support desk: a triage router and two specialists."""

from pydantic_ai import Agent, RunContext, Tool, WebSearchTool
from pydantic_ai.capabilities import NativeTool, Thinking

from .tools import Deps, crm, help_center


def status_page(service: str) -> str:
    """Current status of one of our services."""
    return "operational"


billing = Agent(
    "openai:gpt-5-mini",
    name="billing",
    description="Invoices, refunds and plan changes.",
    instructions="You handle billing questions. Always check the order history first.",
    deps_type=Deps,
    toolsets=[crm.prefixed("crm")],
)

tech = Agent(
    "anthropic:claude-sonnet-5-5",
    name="tech",
    description="Bugs, outages and how-to questions.",
    instructions="You solve technical problems. Quote the help center when you can.",
    deps_type=Deps,
    tools=[Tool(status_page, takes_ctx=False)],
    toolsets=[help_center],
    capabilities=[NativeTool(WebSearchTool()), Thinking(effort="medium")],
)

triage = Agent(
    "openai:gpt-5",
    name="triage",
    instructions="Read the ticket and hand it to the right specialist.",
    deps_type=Deps,
)


@triage.tool
async def ask_billing(ctx: RunContext[Deps], question: str) -> str:
    """Send a billing question to the billing specialist."""
    result = await billing.run(question, deps=ctx.deps, usage=ctx.usage)
    return result.output


@triage.tool
async def ask_tech(ctx: RunContext[Deps], question: str) -> str:
    """Send a technical question to the tech specialist."""
    result = await tech.run(question, deps=ctx.deps, usage=ctx.usage)
    return result.output


@triage.instructions
def customer_context(ctx: RunContext[Deps]) -> str:
    return f"The customer id is {ctx.deps.customer_id}."
