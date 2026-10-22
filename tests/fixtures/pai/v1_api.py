"""PydanticAI v1 API that still parses (diagnostic AD101)."""

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

server = MCPServerStdio("python", args=["-m", "my_server"])
legacy = Agent("openai:gpt-4o", mcp_servers=[server])
