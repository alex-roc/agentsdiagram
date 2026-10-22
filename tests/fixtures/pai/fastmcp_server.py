"""A FastMCP server: its @server.tool() functions are NOT agent tools."""

from fastmcp import FastMCP

server = FastMCP("demo")


@server.tool()
def ping() -> str:
    return "pong"
