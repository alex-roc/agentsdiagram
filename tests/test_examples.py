"""The examples are the website demos: keep them analysable and complete."""

from pathlib import Path

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
