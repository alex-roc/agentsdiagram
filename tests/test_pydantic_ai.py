from conftest import FIXTURES, by_name, edges_from, target_names

from agentsdiagram.analyze import analyze


def test_agent_attributes(fixtures_project):
    a = by_name(fixtures_project, "assistant", "agent")
    assert a.framework == "pydantic_ai"
    assert a.attrs.model == "openai:gpt-5"
    assert a.attrs.instructions == "You are a helpful travel assistant."
    assert a.attrs.deps_type == "Deps"
    assert a.attrs.dynamic_instructions == ["add_city"]
    assert "output_validator" in a.attrs.badges
    assert a.source and a.source.file == "pai/basic_tools.py"
    assert a.source.name_range and a.source.name_range.start.line == 18


def test_decorated_and_tool_objects(fixtures_project):
    a = by_name(fixtures_project, "assistant", "agent")
    assert target_names(fixtures_project, a.id, "uses") == {"weather", "roll", "convert_currency"}
    weather = by_name(fixtures_project, "weather", "tool")
    assert weather.attrs.takes_ctx is True
    assert weather.attrs.docstring == "Weather forecast for the user's city."
    roll = by_name(fixtures_project, "roll", "tool")
    assert roll.attrs.takes_ctx is False
    convert = by_name(fixtures_project, "convert_currency", "tool")
    assert "requires_approval" in convert.attrs.badges
    assert convert.attrs.docstring == "Convert an amount of USD to another currency."


def test_toolsets_mcp_and_capabilities(fixtures_project):
    analyst = by_name(fixtures_project, "analyst", "agent")
    uses = {e.target: e for e in edges_from(fixtures_project, analyst.id, "uses")}
    names = {fixtures_project.node(t).name for t in uses}
    assert {"math", "files", "MCP docs.example.com", "research", "WebSearchTool", "WebFetch"} <= names
    assert "MCP mcp.example.com" in names
    assert "Thinking" in analyst.attrs.badges
    math_edge = next(e for t, e in uses.items() if fixtures_project.node(t).name == "math")
    assert math_edge.wrappers == ['prefixed("math")']
    math = by_name(fixtures_project, "math", "toolset")
    assert target_names(fixtures_project, math.id, "provides") == {"add", "multiply"}
    files = by_name(fixtures_project, "files", "mcp_server")
    assert files.attrs.command == "uvx mcp-server-filesystem /tmp"
    research = by_name(fixtures_project, "research", "capability")
    assert target_names(fixtures_project, research.id, "provides") == {"cite"}


def test_cross_module_delegation_and_workflow(fixtures_project):
    lead = by_name(fixtures_project, "lead", "agent")
    research_tool = next(n for n in fixtures_project.nodes if n.name == "research" and n.kind == "tool")
    assert research_tool.id in {e.target for e in edges_from(fixtures_project, lead.id, "uses")}
    assert target_names(fixtures_project, research_tool.id, "delegates_to") == {"researcher"}
    pipeline = by_name(fixtures_project, "pipeline", "workflow")
    runs = sorted(edges_from(fixtures_project, pipeline.id, "runs"), key=lambda e: e.order)
    assert [fixtures_project.node(e.target).name for e in runs] == ["researcher", "writer"]


def test_subagents_and_factory_instances(fixtures_project):
    subagents = by_name(fixtures_project, "SubAgents", "capability")
    edges = edges_from(fixtures_project, subagents.id, "delegates_to")
    assert [(fixtures_project.node(e.target).name, e.label) for e in edges] == [("reviewer", "reviewer")]
    reviewer = by_name(fixtures_project, "reviewer", "agent")
    assert reviewer.status == "partial"
    assert reviewer.source.file == "pai/multi/orchestrator.py"
    # the factory's template agent is not shown on its own
    assert not [n for n in fixtures_project.nodes if n.name == "make_reviewer()"]


def test_graph_builder(fixtures_project):
    graph = by_name(fixtures_project, "build", "graph")
    steps = target_names(fixtures_project, graph.id, "contains")
    assert {"fetch", "summarize", "skip", "start", "end", "decision"} <= steps
    decision = by_name(fixtures_project, "decision", "graph_step")
    labels = {(fixtures_project.node(e.target).name, e.label) for e in edges_from(fixtures_project, decision.id)}
    assert ("summarize", "long") in labels
    summarize = by_name(fixtures_project, "summarize", "graph_step")
    assert target_names(fixtures_project, summarize.id, "runs") == {"summarizer"}


def test_base_nodes(fixtures_project):
    check = by_name(fixtures_project, "Check", "graph_step")
    assert target_names(fixtures_project, check.id, "transitions") == {"Ask", "end"}


def test_agent_spec(fixtures_project):
    spec = by_name(fixtures_project, "spec_agent", "agent")
    assert spec.attrs.model == "anthropic:claude-sonnet-5-5"
    assert "Thinking" in spec.attrs.badges
    assert target_names(fixtures_project, spec.id, "uses") == {"MCP docs.example.com"}


def test_dynamic_and_false_positives(fixtures_project):
    agent = next(
        n for n in fixtures_project.nodes if n.source and n.source.file == "pai/dynamic.py" and n.kind == "agent"
    )
    assert agent.name == "agent"
    targets = [fixtures_project.node(e.target) for e in edges_from(fixtures_project, agent.id)]
    assert [(t.kind, t.name) for t in targets] == [("dynamic", "extra_toolsets")]
    assert not [n for n in fixtures_project.nodes if n.name == "ping"]  # FastMCP server tool


def test_diagnostics(fixtures_project):
    codes = {(d.code, d.ref.file if d.ref else None) for d in fixtures_project.diagnostics}
    assert ("AD000", "pai/syntax_error.py") in codes
    assert ("AD101", "pai/v1_api.py") in codes


def test_stale_file_keeps_last_valid_version(tmp_path):
    from agentsdiagram.analyze import Cache

    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n")
    src = tmp_path / "app.py"
    src.write_text("from pydantic_ai import Agent\n\nhelper = Agent('openai:gpt-5')\n")
    cache = Cache()
    first = analyze(tmp_path, cache=cache)
    assert [n.status for n in first.nodes] == ["resolved"]
    broken = "from pydantic_ai import Agent\n\nhelper = Agent('openai:gpt-5'\n"
    second = analyze(tmp_path, cache=cache, overrides={src: broken})
    assert [n.status for n in second.nodes] == ["stale"]
    assert second.diagnostics[0].code == "AD000" and second.diagnostics[0].severity == "warning"


def test_single_file_scope_resolves_imports():
    project = analyze(FIXTURES / "pai/multi/orchestrator.py")
    names = {n.name for n in project.nodes}
    assert {"lead", "researcher", "writer", "pipeline"} <= names
