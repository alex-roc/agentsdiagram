from conftest import by_name, edges_from, target_names


def test_manager_and_managed(fixtures_project):
    manager = by_name(fixtures_project, "manager", "agent")
    assert manager.attrs.agent_class == "CodeAgent"
    assert manager.attrs.model == "InferenceClientModel('Qwen/Qwen3-Next-80B-A3B-Thinking')"
    assert manager.attrs.extra["planning_interval"] == "3"
    assert target_names(fixtures_project, manager.id, "manages") == {"web_agent"}
    assert target_names(fixtures_project, manager.id, "uses") == {"get_weather"}
    web = by_name(fixtures_project, "web_agent", "agent")
    assert target_names(fixtures_project, web.id, "uses") == {"web_search", "visit_webpage"}


def test_tool_subclass_model_alias_and_base_tools(fixtures_project):
    agent = next(n for n in fixtures_project.nodes if n.kind == "agent" and n.source.file == "smol/tool_class.py")
    assert agent.attrs.model == "OpenAIModel('gpt-5')"
    tools = target_names(fixtures_project, agent.id, "uses")
    # add_base_tools on a ToolCallingAgent includes python_interpreter (smolagents agents.py `_setup_tools`)
    assert tools == {"stock_price", "web_search", "visit_webpage", "python_interpreter"}
    stock = by_name(fixtures_project, "stock_price", "tool")
    assert stock.attrs.description == "Latest price of a stock."


def test_mcp(fixtures_project):
    agent = next(
        n for n in fixtures_project.nodes if n.kind == "agent" and n.source.file == "smol/mcp.py" and n.name == "agent"
    )
    (mcp_id,) = [e.target for e in edges_from(fixtures_project, agent.id, "uses")]
    mcp = fixtures_project.node(mcp_id)
    assert mcp.kind == "mcp_server" and mcp.attrs.command == "uvx pubmedmcp@0.1.3"
    http_agent = by_name(fixtures_project, "http_agent", "agent")
    assert {fixtures_project.node(e.target).attrs.url for e in edges_from(fixtures_project, http_agent.id)} == {
        "http://127.0.0.1:8000/mcp"
    }


def test_diagnostics(fixtures_project):
    diags = [d for d in fixtures_project.diagnostics if d.ref and d.ref.file == "smol/managed_without_name.py"]
    codes = sorted(d.code for d in diags)
    assert codes == ["AD201", "AD203", "AD203", "AD204"]
