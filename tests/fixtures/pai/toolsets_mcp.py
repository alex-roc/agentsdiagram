"""Toolsets, wrappers, MCP servers and capabilities (PydanticAI 2.x)."""

from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, Capability, FunctionToolset, NativeTool, WebSearchTool
from pydantic_ai.capabilities import MCP, Thinking, WebFetch
from pydantic_ai.mcp import MCPToolset

math = FunctionToolset(id="math")


@math.tool_plain
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


math.add_function(multiply)

files = MCPToolset(StdioTransport(command="uvx", args=["mcp-server-filesystem", "/tmp"]), id="files")
docs = MCPToolset("https://docs.example.com/mcp")

research = Capability(id="research", description="Look things up on the web")


@research.tool_plain
def cite(url: str) -> str:
    """Format a citation."""
    return url


TOOLSETS = [math.prefixed("math"), files]

analyst = Agent(
    "anthropic:claude-sonnet-5-5",
    toolsets=TOOLSETS + [docs.filtered(lambda ctx, t: True)],
    capabilities=[
        research,
        NativeTool(WebSearchTool()),
        WebFetch(),
        MCP(url="https://mcp.example.com/mcp"),
        Thinking(effort="high"),
    ],
)
