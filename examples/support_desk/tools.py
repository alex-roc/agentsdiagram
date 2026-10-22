"""Tools shared by the support agents."""

from dataclasses import dataclass

from pydantic_ai import FunctionToolset, RunContext
from pydantic_ai.mcp import MCPToolset


@dataclass
class Deps:
    customer_id: str


crm = FunctionToolset(id="crm")


@crm.tool
async def lookup_customer(ctx: RunContext[Deps]) -> dict:
    """Name, plan and open tickets of the current customer."""
    return {"id": ctx.deps.customer_id, "plan": "pro"}


@crm.tool
async def order_history(ctx: RunContext[Deps], limit: int = 5) -> list[dict]:
    """The customer's latest orders."""
    return []


def refund(order_id: str, amount: float) -> str:
    """Refund an order (needs human approval)."""
    return f"refunded {amount} on {order_id}"


crm.add_function(refund, requires_approval=True)

help_center = MCPToolset("https://help.example.com/mcp", id="help_center")
