"""Plan and edit: every operation on copies of the examples, then the result analysed again.

The oracle tests at the end import the edited code with the real libraries: the code the
planner writes must run, not only look right.
"""

import importlib
import shutil
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from agentsdiagram.analyze import analyze
from agentsdiagram.edit import EditError, line_edits, plan_edit
from agentsdiagram.ir import EditRequest

EXAMPLES = Path(__file__).parent.parent / "examples"
SMOL = "smolagents:agent:examples.research_team.team"
PAI = "pydantic_ai:agent:examples.support_desk.agents"
REQUEST = TypeAdapter(EditRequest)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    return tmp_path


def edit(root: Path, **request):
    outcome = plan_edit(root, REQUEST.validate_python(request))
    outcome.write()
    return outcome


def node(project, name: str, kind: str | None = None):
    found = [n for n in project.nodes if n.name == name and (kind is None or n.kind == kind)]
    assert found, f"no node {name!r}"
    return found[0]


def pairs(project, kind: str) -> set[tuple[str, str]]:
    names = {n.id: n.name for n in project.nodes}
    return {(names[e.source], names[e.target]) for e in project.edges if e.kind == kind}


def codes(project) -> list[str]:
    return sorted(d.code for d in project.diagnostics)


# ---------------------------------------------------------------------- smolagents


def test_smol_add_tool_is_planned(root):
    out = edit(root, op="add_tool", agent=f"{SMOL}.analyst", name="fetch_dataset", params="url: str, limit: int = 5")
    p = analyze(root / "examples/research_team")
    tool = node(p, "fetch_dataset", "tool")
    assert tool.status == "planned" and out.focus == tool.id
    assert ("analyst", "fetch_dataset") in pairs(p, "uses")
    assert codes(p) == ["AD401"]  # type hints and Args: docstring are there (no AD203)
    text = (root / "examples/research_team/team.py").read_text()
    assert "        url: Url.\n        limit: Limit.\n" in text
    assert "\n\n\n@tool\ndef fetch_dataset" in text


def test_smol_add_tool_needs_type_hints(root):
    with pytest.raises(EditError, match="type hint"):
        plan_edit(
            root, REQUEST.validate_python({"op": "add_tool", "agent": f"{SMOL}.analyst", "name": "f", "params": "x"})
        )


def test_smol_add_managed_agent(root):
    edit(
        root,
        op="add_agent",
        framework="smolagents",
        name="reviewer",
        file="examples/research_team/team.py",
        parent=f"{SMOL}.lead",
        instructions="Be strict.",
    )
    p = analyze(root / "examples/research_team")
    reviewer = node(p, "reviewer", "agent")
    assert reviewer.status == "planned" and reviewer.attrs.agent_class == "ToolCallingAgent"
    assert reviewer.attrs.model == "InferenceClientModel('Qwen/Qwen3-Next-80B-A3B-Thinking')"  # the file's model
    assert ("lead", "reviewer") in pairs(p, "manages")
    assert "AD201" not in codes(p)  # name and description written


def test_smol_add_mcp_and_set_model(root):
    edit(root, op="add_mcp", agent=f"{SMOL}.analyst", url="https://data.example.com/mcp")
    edit(root, op="set_model", agent=f"{SMOL}.analyst", model="Qwen/Qwen3-Coder")
    p = analyze(root / "examples/research_team")
    mcp = node(p, "MCP data.example.com", "mcp_server")
    assert ("analyst", mcp.name) in pairs(p, "uses")
    assert node(p, "analyst", "agent").attrs.model == "InferenceClientModel('Qwen/Qwen3-Coder')"
    assert node(p, "web_researcher", "agent").attrs.model.endswith("Thinking')")  # shared `model` untouched
    text = (root / "examples/research_team/team.py").read_text()
    assert "    MCPClient,\n" in text  # merged into the existing parenthesised import


def test_smol_connect_disconnect_remove(root):
    edit(root, op="connect", source=f"{SMOL}.analyst", target=f"{SMOL}.web_researcher")
    p = analyze(root / "examples/research_team")
    assert ("analyst", "web_researcher") in pairs(p, "manages")
    with pytest.raises(EditError, match="defined after"):
        plan_edit(
            root,
            REQUEST.validate_python({"op": "connect", "source": f"{SMOL}.web_researcher", "target": f"{SMOL}.analyst"}),
        )
    edge = next(
        e
        for e in p.edges
        if e.kind == "manages" and p.node(e.target).name == "web_researcher" and p.node(e.source).name == "lead"
    )
    edit(root, op="disconnect", edge=edge.id)
    p = analyze(root / "examples/research_team")
    assert ("lead", "web_researcher") not in pairs(p, "manages")
    edit(root, op="remove", node=node(p, "plot", "tool").id)
    p = analyze(root / "examples/research_team")
    assert "plot" not in {n.name for n in p.nodes}
    assert "def plot" not in (root / "examples/research_team/team.py").read_text()
    assert "    tool,\n" not in (root / "examples/research_team/team.py").read_text()  # import pruned


def test_smol_remove_agent(root):
    edit(root, op="remove", node=f"{SMOL}.analyst")
    p = analyze(root / "examples/research_team")
    assert "analyst" not in {n.name for n in p.nodes}
    assert pairs(p, "manages") == {("lead", "web_researcher")}


# ---------------------------------------------------------------------- PydanticAI


def test_pai_add_tool_and_agent(root):
    edit(root, op="add_tool", agent=f"{PAI}.billing", name="refund_status", params="order_id: str")
    edit(
        root,
        op="add_agent",
        framework="pydantic_ai",
        name="sales",
        file="examples/support_desk/agents.py",
        parent=f"{PAI}.triage",
        description="Pricing and upgrades.",
    )
    p = analyze(root / "examples/support_desk")
    assert node(p, "refund_status", "tool").status == "planned"
    assert ("billing", "refund_status") in pairs(p, "uses")
    sales = node(p, "sales", "agent")
    assert sales.status == "planned" and sales.attrs.model == "openai:gpt-5-mini"
    assert ("ask_sales", "sales") in pairs(p, "delegates_to")
    assert ("triage", "ask_sales") in pairs(p, "uses")
    assert codes(p) == ["AD401", "AD401"]


def test_pai_mcp_model_instructions(root):
    edit(root, op="add_mcp", agent=f"{PAI}.tech", command="uvx mcp-server-fetch")
    edit(root, op="set_model", agent=f"{PAI}.triage", model="anthropic:claude-opus-5-5")
    edit(root, op="set_instructions", agent=f"{PAI}.billing", instructions="Be brief.")
    p = analyze(root / "examples/support_desk")
    mcp = node(p, "mcp_server_fetch", "mcp_server")
    assert mcp.attrs.command == "uvx mcp-server-fetch"
    assert ("tech", "mcp_server_fetch") in pairs(p, "uses")
    assert node(p, "triage", "agent").attrs.model == "anthropic:claude-opus-5-5"
    assert node(p, "billing", "agent").attrs.instructions == "Be brief."
    text = (root / "examples/support_desk/agents.py").read_text()
    assert "from pydantic_ai.capabilities import NativeTool, Thinking\nfrom pydantic_ai.mcp import" in text
    edit(root, op="set_instructions", agent=f"{PAI}.billing", instructions="")
    assert analyze(root / "examples/support_desk").node(f"{PAI}.billing").attrs.instructions is None


def test_pai_connect_writes_a_delegation_tool(root):
    edit(root, op="connect", source=f"{PAI}.tech", target=f"{PAI}.billing")
    p = analyze(root / "examples/support_desk")
    assert ("tech_asks_billing", "billing") in pairs(p, "delegates_to")  # ask_billing exists already
    assert "deps=ctx.deps" in (root / "examples/support_desk/agents.py").read_text()  # same deps_type
    with pytest.raises(EditError, match="already"):
        plan_edit(
            root, REQUEST.validate_python({"op": "connect", "source": f"{PAI}.triage", "target": f"{PAI}.billing"})
        )


def test_pai_remove_needs_the_delegation_gone_first(root):
    with pytest.raises(EditError, match="ask_billing"):
        plan_edit(root, REQUEST.validate_python({"op": "remove", "node": f"{PAI}.billing"}))
    p = analyze(root / "examples/support_desk")
    edit(root, op="remove", node=node(p, "ask_billing", "tool").id)
    edit(root, op="remove", node=f"{PAI}.billing")
    p = analyze(root / "examples/support_desk")
    assert {"billing", "ask_billing"}.isdisjoint({n.name for n in p.nodes})
    assert not [d for d in p.diagnostics if d.code == "AD001"]


def test_pai_disconnect_a_decorator_tool(root):
    p = analyze(root / "examples/support_desk")
    edge = next(e for e in p.edges if e.kind == "uses" and p.node(e.target).name == "ask_tech")
    edit(root, op="disconnect", edge=edge.id)
    p = analyze(root / "examples/support_desk")
    assert "ask_tech" not in {n.name for n in p.nodes}
    with pytest.raises(EditError, match="runs `billing` inside"):
        e = next(e for e in p.edges if e.kind == "delegates_to")
        plan_edit(root, REQUEST.validate_python({"op": "disconnect", "edge": e.id}))


def test_pai_export_spec(root):
    out = edit(root, op="export_spec", agent=f"{PAI}.tech")
    assert out.files == ["examples/support_desk/agents.py", "examples/support_desk/tech.agent.yaml"]
    p = analyze(root / "examples/support_desk")
    tech = node(p, "tech", "agent")
    assert tech.attrs.agent_class == "Agent (spec)" and tech.attrs.model == "anthropic:claude-sonnet-5-5"
    assert "Thinking" in tech.attrs.badges
    assert {"help_center", "status_page", "WebSearchTool"} <= {
        p.node(e.target).name for e in p.edges if e.source == tech.id
    }


def test_new_file_and_stale_expectations(root):
    out = edit(
        root, op="add_agent", framework="pydantic_ai", name="scout", file="examples/scout.py", model="openai:gpt-5"
    )
    assert out.changes[0].before is None
    assert (
        (root / "examples/scout.py")
        .read_text()
        .startswith("from pydantic_ai import Agent\n\n# agentsdiagram: planned\n")
    )
    with pytest.raises(EditError, match="changed since"):
        plan_edit(
            root,
            REQUEST.validate_python({"op": "set_model", "agent": f"{PAI}.tech", "model": "x:y"}),
            expect={"examples/support_desk/agents.py": "0" * 64},
        )


def test_unknown_ids_and_bad_names(root):
    with pytest.raises(EditError, match="not in the diagram"):
        plan_edit(root, REQUEST.validate_python({"op": "remove", "node": "nope"}))
    with pytest.raises(EditError, match="already exists"):
        plan_edit(root, REQUEST.validate_python({"op": "add_tool", "agent": f"{PAI}.tech", "name": "status_page"}))
    with pytest.raises(EditError, match="not a valid"):
        plan_edit(root, REQUEST.validate_python({"op": "add_tool", "agent": f"{PAI}.tech", "name": "class"}))


@pytest.mark.parametrize(
    ("before", "after"),
    [("a\nb\nc\n", "a\nx\nc\n"), ("a\nb", "a\nb\nc\n"), ("", "x\n"), ("a\nb\nc\n", "c\n")],
)
def test_line_edits_rebuild_the_text(before, after):
    lines = before.splitlines(keepends=True)
    for e in reversed(line_edits(before, after)):
        lines[e.start : e.end] = [e.text] if e.text else []
    assert "".join(lines) == after


# ---------------------------------------------------------------------- oracles: the written code runs

SMOL_APP = """from smolagents import CodeAgent, InferenceClientModel, ToolCallingAgent

model = InferenceClientModel(model_id="Qwen/Qwen3-Next-80B-A3B-Thinking")

helper = ToolCallingAgent(tools=[], model=model, name="helper", description="Helps.")

boss = CodeAgent(tools=[], model=model)
"""

PAI_APP = """from dataclasses import dataclass

from pydantic_ai import Agent


@dataclass
class Deps:
    user: str


expert = Agent("openai:gpt-5-mini", name="expert", deps_type=Deps)

lead = Agent(
    "openai:gpt-5",
    name="lead",
    instructions="Route the question.",
    deps_type=Deps,
    capabilities=[],
)
"""


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN"):
        monkeypatch.setenv(key, "test")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n')
    pkg = tmp_path / "edited_app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "smol.py").write_text(SMOL_APP)
    (pkg / "pai.py").write_text(PAI_APP)
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    for name in [m for m in sys.modules if m.startswith("edited_app")]:
        del sys.modules[name]


@pytest.mark.oracle
def test_oracle_smolagents_code_runs(app):
    pytest.importorskip("smolagents")
    a = "smolagents:agent:edited_app.smol"
    edit(app, op="add_tool", agent=f"{a}.boss", name="lookup", params="term: str")
    edit(app, op="connect", source=f"{a}.boss", target=f"{a}.helper")
    edit(app, op="add_agent", framework="smolagents", name="critic", file="edited_app/smol.py", parent=f"{a}.boss")
    edit(app, op="set_model", agent=f"{a}.helper", model="Qwen/Qwen3-Coder")
    m = importlib.import_module("edited_app.smol")
    assert "lookup" in m.boss.tools
    assert set(m.boss.managed_agents) == {"helper", "critic"}
    assert m.helper.model.model_id == "Qwen/Qwen3-Coder"
    with pytest.raises(NotImplementedError, match="agentsdiagram: planned"):
        m.lookup("x")


@pytest.mark.oracle
def test_oracle_pydantic_ai_code_runs(app):
    pytest.importorskip("pydantic_ai")
    a = "pydantic_ai:agent:edited_app.pai"
    edit(app, op="add_tool", agent=f"{a}.expert", name="search_docs", params="query: str, limit: int = 3")
    edit(app, op="connect", source=f"{a}.lead", target=f"{a}.expert")
    edit(app, op="add_agent", framework="pydantic_ai", name="writer", file="edited_app/pai.py", parent=f"{a}.lead")
    edit(app, op="add_mcp", agent=f"{a}.expert", url="https://docs.example.com/mcp")
    edit(app, op="export_spec", agent=f"{a}.lead")
    m = importlib.import_module("edited_app.pai")
    assert set(m.expert._function_toolset.tools) == {"search_docs"}
    assert set(m.lead._function_toolset.tools) == {"ask_expert", "ask_writer"}
    assert m.lead.name == "lead" and m.lead.model.model_name == "gpt-5"
    assert [type(t).__name__ for t in m.expert.toolsets][-1] == "MCPToolset"
    p = analyze(app)
    assert node(p, "lead", "agent").attrs.agent_class == "Agent (spec)"
    assert {"ask_expert", "ask_writer"} <= {p.node(e.target).name for e in p.edges if e.source == f"{a}.lead"}


# ---------------------------------------------------------------------- command line


def test_cli_edit_commands(root, capsys):
    from agentsdiagram.cli import main

    p = str(root)
    assert main(["edit", "add-tool", "analyst", "load", "-p", p, "--dry-run"]) == 0
    assert "+def load(query: str) -> str:" in capsys.readouterr().out
    assert "def load" not in (root / "examples/research_team/team.py").read_text()  # dry run
    assert main(["edit", "add-mcp", "tech", "-p", p, "--command", "uvx mcp-server-fetch"]) == 0
    assert main(["edit", "add-mcp", "analyst", "-p", p, "--url", "https://x.example.com/mcp", "--json"]) == 0
    assert '"ok": true' in capsys.readouterr().out
    assert main(["edit", "connect", "tech", "billing", "-p", p]) == 0
    assert main(["edit", "disconnect", "triage", "billing", "-p", p]) == 1
    assert "goes through `ask_billing`" in capsys.readouterr().err
    assert main(["edit", "set-model", "lead", "Qwen/Qwen3-Coder", "-p", p]) == 0
    assert main(["edit", "remove", "nope", "-p", p]) == 1
    assert main(["edit", "add-agent", "x", "--file", "examples/x.py", "-p", p]) == 1  # two frameworks here
    assert "--framework" in capsys.readouterr().err
