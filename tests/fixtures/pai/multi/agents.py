"""Agents defined in one module, used from another (cross-module resolution)."""

from pydantic_ai import Agent

researcher = Agent("openai:gpt-5-mini", name="researcher", instructions="Find facts.")
writer = Agent("openai:gpt-5", name="writer", instructions="Write a short report.")
