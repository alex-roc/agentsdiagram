"""The examples are the website demos: keep them analysable and complete."""

import importlib
from pathlib import Path

import pytest

from agentsdiagram.analyze import analyze

EXAMPLES = Path(__file__).parent.parent / "examples"


def _edges(project, kind):
    names = {n.id: n.name for n in project.nodes}
    return {(names[e.source], names[e.target]) for e in project.edges if e.kind == kind}


def test_support_desk():
    project = analyze(EXAMPLES / "support_desk")
    assert not project.diagnostics
    agents = {n.name for n in project.nodes if n.kind == "agent"}
    assert agents == {"triage", "billing", "tech", "writer", "tone_check"}
    assert _edges(project, "delegates_to") == {("ask_billing", "billing"), ("ask_tech", "tech")}
    assert ("handle_ticket", "writer") in _edges(project, "runs")
    assert {n.kind for n in project.nodes} >= {"toolset", "mcp_server", "native_tool", "workflow", "graph"}


def test_research_team():
    project = analyze(EXAMPLES / "research_team")
    assert not project.diagnostics
    assert _edges(project, "manages") == {("lead", "web_researcher"), ("lead", "analyst")}
    tools = {n.name for n in project.nodes if n.kind == "tool"}
    assert {"csv_summary", "plot", "web_search", "visit_webpage"} <= tools


def test_hello_examples():
    for folder in ("hello_smolagents", "hello_pydantic_ai"):
        project = analyze(EXAMPLES / folder)
        assert not project.diagnostics, folder
        assert _edges(project, "uses") >= {("assistant", "get_weather")}, folder


@pytest.mark.oracle
def test_hello_examples_import(monkeypatch):
    """The first tutorial's code runs with the real libraries."""
    pytest.importorskip("smolagents")
    pytest.importorskip("pydantic_ai")
    for key in ("OPENAI_API_KEY", "HF_TOKEN"):
        monkeypatch.setenv(key, "test")
    monkeypatch.syspath_prepend(str(EXAMPLES.parent))
    smol = importlib.import_module("examples.hello_smolagents.agent")
    assert set(smol.assistant.tools) >= {"get_weather", "web_search"}
    pai = importlib.import_module("examples.hello_pydantic_ai.agent")
    assert set(pai.assistant._function_toolset.tools) == {"get_weather", "home_city"}
