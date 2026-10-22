"""smolagents symbols recognised by the adapter.

Verified against smolagents 1.26.0 (2026-10-22). ``tests/test_symbols_drift.py`` imports
every entry. When the API changes, update this table and docs/adapters/smolagents.md.
"""

ROOTS = ("smolagents",)

AGENTS = {"smolagents.CodeAgent", "smolagents.ToolCallingAgent", "smolagents.MultiStepAgent"}
TOOL_DECORATOR = {"smolagents.tool"}
TOOL_BASES = {"smolagents.Tool", "smolagents.PipelineTool"}

# Default tools -> the `name` they expose (several share `web_search`).
DEFAULT_TOOLS = {
    "smolagents.PythonInterpreterTool": "python_interpreter",
    "smolagents.FinalAnswerTool": "final_answer",
    "smolagents.UserInputTool": "user_input",
    "smolagents.DuckDuckGoSearchTool": "web_search",
    "smolagents.GoogleSearchTool": "web_search",
    "smolagents.ApiWebSearchTool": "web_search",
    "smolagents.WebSearchTool": "web_search",
    "smolagents.VisitWebpageTool": "visit_webpage",
    "smolagents.WikipediaSearchTool": "wikipedia_search",
    "smolagents.SpeechToTextTool": "transcriber",
}

# add_base_tools=True adds TOOL_MAPPING minus python_interpreter for CodeAgent (agents.py `_setup_tools`).
BASE_TOOLS = {
    "web_search": "DuckDuckGoSearchTool",
    "visit_webpage": "VisitWebpageTool",
    "python_interpreter": "PythonInterpreterTool",
}

# Remote / wrapped tool sources: Tool.from_hub(...) etc. Matched on the method name.
EXTERNAL_METHODS = {"from_hub", "from_space", "from_langchain", "from_gradio", "from_code"}
EXTERNAL_FUNCTIONS = {"smolagents.load_tool"}
COLLECTIONS = {"smolagents.ToolCollection"}
MCP_CLIENT = {"smolagents.MCPClient"}

MODEL_ALIASES = {
    "OpenAIServerModel": "OpenAIModel",
    "AzureOpenAIServerModel": "AzureOpenAIModel",
    "AmazonBedrockServerModel": "AmazonBedrockModel",
    "HfApiModel": "InferenceClientModel",
}

EXECUTOR_TYPES = {"local", "blaxel", "e2b", "modal", "docker"}
REMOVED_EXECUTOR_TYPES = {"wasm": "removed in smolagents 1.26"}

RUN_METHODS = frozenset({"run"})


def all_symbols() -> set[str]:
    return AGENTS | TOOL_DECORATOR | TOOL_BASES | set(DEFAULT_TOOLS) | EXTERNAL_FUNCTIONS | COLLECTIONS | MCP_CLIENT
