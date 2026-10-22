"""PydanticAI symbols recognised by the adapter.

Verified against pydantic-ai 2.59.0 and pydantic-ai-harness 0.59.0 (2026-10-22).
Names are ``root.LastName`` (see ``adapters.base.symbol``). ``tests/test_symbols_drift.py``
imports every entry, so a rename in a new release fails CI (and the weekly drift job).
When the API changes, update this table and docs/adapters/pydantic_ai.md together.
"""

ROOTS = ("pydantic_ai", "pydantic_ai_harness", "pydantic_graph", "fastmcp")

AGENT = {"pydantic_ai.Agent"}
TOOL = {"pydantic_ai.Tool"}

FUNCTION_TOOLSET = {"pydantic_ai.FunctionToolset"}
# Wrapper toolsets: first positional arg (or `wrapped=`) is the inner toolset.
WRAPPER_TOOLSETS = {
    "pydantic_ai.PrefixedToolset",
    "pydantic_ai.FilteredToolset",
    "pydantic_ai.RenamedToolset",
    "pydantic_ai.PreparedToolset",
    "pydantic_ai.ApprovalRequiredToolset",
    "pydantic_ai.DeferredLoadingToolset",
    "pydantic_ai.IncludeReturnSchemasToolset",
    "pydantic_ai.SetMetadataToolset",
    "pydantic_ai.WrapperToolset",
}
COMBINED_TOOLSET = {"pydantic_ai.CombinedToolset"}
EXTERNAL_TOOLSET = {"pydantic_ai.ExternalToolset"}
# Chainable toolset methods that return a wrapper: `ts.prefixed('x')`.
TOOLSET_METHODS = {
    "prefixed",
    "filtered",
    "renamed",
    "prepared",
    "approval_required",
    "defer_loading",
    "include_return_schemas",
    "with_metadata",
}

MCP_TOOLSET = {"pydantic_ai.MCPToolset"}
MCP_TRANSPORTS = {
    "pydantic_ai.StdioTransport",
    "fastmcp.StdioTransport",
    "pydantic_ai.StreamableHttpTransport",
    "fastmcp.StreamableHttpTransport",
    "pydantic_ai.SSETransport",
    "fastmcp.SSETransport",
}
MCP_CONFIG_LOADERS = {"pydantic_ai.load_mcp_toolsets"}
# PydanticAI v1 names, still recognised (with diagnostic AD101).
MCP_V1 = {
    "pydantic_ai.MCPServerStdio",
    "pydantic_ai.MCPServerSSE",
    "pydantic_ai.MCPServerStreamableHTTP",
    "pydantic_ai.MCPServerHTTP",
}
MCP_CONFIG_LOADERS_V1 = {"pydantic_ai.load_mcp_servers"}

NATIVE_TOOLS = {
    "pydantic_ai.WebSearchTool",
    "pydantic_ai.XSearchTool",
    "pydantic_ai.CodeExecutionTool",
    "pydantic_ai.ImageGenerationTool",
    "pydantic_ai.WebFetchTool",
    "pydantic_ai.MemoryTool",
    "pydantic_ai.MCPServerTool",
    "pydantic_ai.FileSearchTool",
    "pydantic_ai.AdvisorTool",
}
NATIVE_TOOLS_V1 = {"pydantic_ai.UrlContextTool"}

# Capabilities with structural meaning. Any other capability becomes a badge on the agent.
CAP_NATIVE_TOOL = {"pydantic_ai.NativeTool"}
CAP_ADAPTIVE_TOOLS = {
    "pydantic_ai.WebSearch",
    "pydantic_ai.WebFetch",
    "pydantic_ai.ImageGeneration",
    "pydantic_ai.XSearch",
}
CAP_MCP = {"pydantic_ai.MCP"}
CAP_CAPABILITY = {"pydantic_ai.Capability"}
CAP_TOOLSET = {"pydantic_ai.Toolset"}
CAP_SUBAGENTS = {"pydantic_ai_harness.SubAgents"}
CAP_SUBAGENT = {"pydantic_ai_harness.SubAgent"}
CAP_DYNAMIC_WORKFLOW = {"pydantic_ai_harness.DynamicWorkflow"}

OUTPUT_MARKERS = {
    "pydantic_ai.ToolOutput",
    "pydantic_ai.NativeOutput",
    "pydantic_ai.PromptedOutput",
    "pydantic_ai.TextOutput",
    "pydantic_ai.StructuredDict",
}

# Agent decorators: name -> meaning
DECORATOR_TOOL = {"tool", "tool_plain"}
DECORATOR_INSTRUCTIONS = {"instructions", "system_prompt"}
DECORATOR_TOOLSET = {"toolset"}
DECORATOR_BADGE = {"output_validator": "output_validator", "on_event": "on_event"}

RUN_METHODS = frozenset({"run", "run_sync", "run_stream", "run_stream_sync", "run_stream_events", "iter"})

# Agent(...) keyword arguments removed in v2 (AD101)
AGENT_KWARGS_V1 = {
    "builtin_tools": "capabilities=[NativeTool(...)]",
    "mcp_servers": "toolsets=[...]",
    "history_processors": "capabilities=[ProcessHistory(...)]",
    "prepare_tools": "capabilities=[PrepareTools(...)]",
    "event_stream_handler": "capabilities=[ProcessEventStream(...)]",
    "instrument": "capabilities=[Instrumentation(...)]",
}

# pydantic-graph
GRAPH_BUILDER = {"pydantic_graph.GraphBuilder"}
GRAPH_BASE_NODE = {"pydantic_graph.BaseNode"}
GRAPH_END = {"pydantic_graph.End"}
AGENT_FROM_SPEC = {"from_file", "from_spec"}


def all_symbols() -> set[str]:
    groups = [
        AGENT,
        TOOL,
        FUNCTION_TOOLSET,
        WRAPPER_TOOLSETS,
        COMBINED_TOOLSET,
        EXTERNAL_TOOLSET,
        MCP_TOOLSET,
        MCP_CONFIG_LOADERS,
        NATIVE_TOOLS,
        CAP_NATIVE_TOOL,
        CAP_ADAPTIVE_TOOLS,
        CAP_MCP,
        CAP_CAPABILITY,
        CAP_TOOLSET,
        CAP_SUBAGENTS,
        CAP_SUBAGENT,
        CAP_DYNAMIC_WORKFLOW,
        OUTPUT_MARKERS,
        GRAPH_BUILDER,
        GRAPH_BASE_NODE,
        GRAPH_END,
    ]
    return set().union(*groups)
