"""Things that cannot be resolved statically become `dynamic` nodes."""

from pydantic_ai import Agent


def build(extra_toolsets):
    return Agent("openai:gpt-5", toolsets=extra_toolsets)


agent = build([])
