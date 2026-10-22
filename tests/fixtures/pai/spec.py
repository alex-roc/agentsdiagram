"""An agent loaded from an Agent Spec file."""

from pydantic_ai import Agent

spec_agent = Agent.from_file("agent.yaml")
