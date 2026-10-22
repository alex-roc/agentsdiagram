"""Every symbol the adapters recognise must exist in the installed library versions.

The weekly `drift` workflow runs this against the latest releases, so a rename in
PydanticAI or smolagents shows up as a failing test instead of silently missing nodes.
"""

import importlib

import pytest

from agentsdiagram.adapters.pydantic_ai import symbols as pai
from agentsdiagram.adapters.smolagents import symbols as smol

# where each root re-exports its public API
SEARCH = {
    "pydantic_ai": [
        "pydantic_ai",
        "pydantic_ai.capabilities",
        "pydantic_ai.mcp",
        "pydantic_ai.native_tools",
        "pydantic_ai.toolsets",
    ],
    "pydantic_ai_harness": ["pydantic_ai_harness"],
    "pydantic_graph": ["pydantic_graph"],
    "fastmcp": ["fastmcp", "fastmcp.client.transports"],
    "smolagents": ["smolagents", "smolagents.tools"],
}

# symbols that need an optional extra to import (checked by name only)
OPTIONAL = {"pydantic_ai_harness.DynamicWorkflow"}


def _exists(symbol: str) -> bool:
    root, name = symbol.split(".", 1)
    for module_name in SEARCH[root]:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        try:
            if getattr(module, name, None) is not None:
                return True
        except ImportError:
            return symbol in OPTIONAL
        if name in getattr(module, "__all__", ()):
            return True
    return False


@pytest.mark.parametrize("symbol", sorted(pai.all_symbols() | pai.MCP_TRANSPORTS))
def test_pydantic_ai_symbol_exists(symbol):
    pytest.importorskip(symbol.split(".", 1)[0])
    assert _exists(symbol), f"{symbol} no longer exists: update adapters/pydantic_ai/symbols.py"


@pytest.mark.parametrize("symbol", sorted(smol.all_symbols()))
def test_smolagents_symbol_exists(symbol):
    pytest.importorskip("smolagents")
    assert _exists(symbol), f"{symbol} no longer exists: update adapters/smolagents/symbols.py"


def test_pydantic_ai_run_methods_exist():
    agent_cls = pytest.importorskip("pydantic_ai").Agent
    for method in pai.RUN_METHODS:
        assert hasattr(agent_cls, method), method


def test_smolagents_base_tools_match_library():
    from smolagents.default_tools import TOOL_MAPPING

    assert set(TOOL_MAPPING) == set(smol.BASE_TOOLS)
    for name, cls_name in smol.BASE_TOOLS.items():
        assert TOOL_MAPPING[name].__name__ == cls_name


def test_smolagents_default_tool_names():
    import smolagents

    for symbol, exposed in smol.DEFAULT_TOOLS.items():
        assert getattr(smolagents, symbol.split(".", 1)[1]).name == exposed
