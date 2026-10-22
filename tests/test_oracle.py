"""Oracle tests: import each fixture with the real libraries and compare with the static IR.

They catch analyzer mistakes *and* fixtures that drift from the real API (a fixture that
no longer imports is a fixture that no longer reflects the library).
"""

import importlib
import sys

import pytest
from conftest import FIXTURES, by_name, edges_from

pytestmark = pytest.mark.oracle

pydantic_ai = pytest.importorskip("pydantic_ai")
smolagents = pytest.importorskip("smolagents")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN"):
        monkeypatch.setenv(key, "test")
    monkeypatch.syspath_prepend(str(FIXTURES))


def load(name: str):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def uses(project, agent_name: str) -> set[str]:
    agent = by_name(project, agent_name, "agent")
    return {project.node(e.target).name for e in edges_from(project, agent.id, "uses")}


@pytest.mark.parametrize(
    ("module", "var"),
    [("pai.basic_tools", "assistant"), ("pai.multi.orchestrator", "lead")],
)
def test_pydantic_function_tools(fixtures_project, module, var):
    agent = getattr(load(module), var)
    assert agent.name == var
    real = set(agent._function_toolset.tools)
    assert real <= uses(fixtures_project, var)


def test_pydantic_toolsets_and_capabilities(fixtures_project):
    m = load("pai.toolsets_mcp")
    assert set(m.math.tools) == {"add", "multiply"}
    caps = {type(c).__name__: c for c in m.analyst.root_capability.capabilities}
    assert caps["Capability"].id == "research"
    assert "Thinking" in by_name(fixtures_project, "analyst", "agent").attrs.badges
    assert {"research", "WebSearchTool", "WebFetch"} <= uses(fixtures_project, "analyst")
    real_toolsets = [type(t).__name__ for t in m.analyst.toolsets]
    assert real_toolsets.count("MCPToolset") + real_toolsets.count("FilteredToolset") == 2


def test_pydantic_graph_builds():
    graph = load("pai.graph_builder").build()
    assert graph is not None


def test_pydantic_spec(fixtures_project, monkeypatch):
    monkeypatch.chdir(FIXTURES / "pai")
    agent = load("pai.spec").spec_agent
    assert agent.name == by_name(fixtures_project, "spec_agent", "agent").name


def test_smolagents_manager(fixtures_project):
    m = load("smol.managed")
    data = m.manager.to_dict()  # 1.26: lists of dicts (not names) for tools and managed agents
    assert {a["name"] for a in data["managed_agents"]} == {"web_agent"} == set(m.manager.managed_agents)
    assert {t["name"] for t in data["tools"]} - {"final_answer"} == uses(fixtures_project, "manager")
    assert set(m.web_agent.tools) - {"final_answer"} == uses(fixtures_project, "web_agent")


def test_smolagents_base_tools(fixtures_project):
    m = load("smol.tool_class")
    agent = next(n for n in fixtures_project.nodes if n.kind == "agent" and n.source.file == "smol/tool_class.py")
    static = {fixtures_project.node(e.target).name for e in edges_from(fixtures_project, agent.id, "uses")}
    assert set(m.agent.tools) - {"final_answer"} == static
