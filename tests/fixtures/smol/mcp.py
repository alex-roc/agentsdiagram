"""MCP tools in smolagents: ToolCollection.from_mcp and MCPClient."""

from mcp import StdioServerParameters
from smolagents import CodeAgent, InferenceClientModel, MCPClient, ToolCollection

params = StdioServerParameters(command="uvx", args=["pubmedmcp@0.1.3"])

with ToolCollection.from_mcp(params, trust_remote_code=True) as collection:
    agent = CodeAgent(tools=[*collection.tools], model=InferenceClientModel())

with MCPClient({"url": "http://127.0.0.1:8000/mcp", "transport": "streamable-http"}) as tools:
    http_agent = CodeAgent(tools=tools, model=InferenceClientModel())
