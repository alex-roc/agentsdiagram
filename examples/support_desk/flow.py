"""Ticket handling: triage answers, a writer polishes the reply, a reviewer checks the tone."""

from pydantic_ai import Agent

from .agents import triage
from .tools import Deps

writer = Agent(
    "openai:gpt-5-mini",
    name="writer",
    instructions="Rewrite the answer as a short, friendly email.",
)

tone_check = Agent(
    "openai:gpt-5-nano",
    name="tone_check",
    instructions="Answer `ok` if the email is polite, otherwise explain why not.",
    output_type=bool,
)


async def handle_ticket(text: str, customer_id: str) -> str:
    """Answer a ticket end to end."""
    answer = await triage.run(text, deps=Deps(customer_id))
    email = await writer.run(answer.output)
    await tone_check.run(email.output)
    return email.output
