import json

from conftest import FIXTURES

from agentsdiagram.analyze import analyze
from agentsdiagram.cli import main
from agentsdiagram.ir import IR_VERSION, json_schema
from agentsdiagram.render.mermaid import render


def test_mermaid_snapshot(snapshot):
    assert render(analyze(FIXTURES / "pai"), title="pai") == snapshot
    assert render(analyze(FIXTURES / "smol"), title="smol") == snapshot


def test_ir_snapshot(snapshot):
    project = analyze(FIXTURES)
    data = project.model_dump(mode="json")
    data["root"] = "<fixtures>"
    data["tool_version"] = "<version>"
    assert data == snapshot


def test_mermaid_ids_are_safe():
    text = render(analyze(FIXTURES))
    assert text.startswith("flowchart LR")
    assert "pydantic_ai:" not in text  # internal ids never leak into Mermaid


def test_cli_scan_json(capsys):
    assert main(["scan", str(FIXTURES / "smol"), "-f", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ir_version"] == IR_VERSION
    assert {n["name"] for n in data["nodes"] if n["kind"] == "agent"} >= {"manager", "web_agent"}


def test_cli_markdown(capsys):
    assert main(["scan", str(FIXTURES / "smol" / "managed.py"), "-f", "markdown"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# managed.py") and "```mermaid\nflowchart LR" in out


def test_cli_check_exit_codes(capsys):
    assert main(["check", str(FIXTURES / "smol" / "managed.py")]) == 0
    assert main(["check", str(FIXTURES / "smol" / "managed_without_name.py")]) == 1
    out = capsys.readouterr().out
    assert "AD201" in out and "AD204" in out


def test_cli_framework_filter(capsys):
    assert main(["scan", str(FIXTURES), "-f", "json", "--framework", "smolagents"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["frameworks"] == ["smolagents"]


def test_schema_matches_committed_file():
    committed = json.loads((FIXTURES.parents[1] / "packages/protocol/ir.schema.json").read_text())
    assert committed == json_schema(), "run `pnpm schema` to regenerate packages/protocol"


def test_missing_path(capsys):
    assert main(["scan", "/does/not/exist"]) == 2


def test_html_embeds_graph_and_viewer():
    import pytest

    from agentsdiagram.render.html import ViewerBundleMissing
    from agentsdiagram.render.html import render as render_html

    try:
        page = render_html(analyze(FIXTURES / "smol"), title="smol")
    except ViewerBundleMissing:
        pytest.skip("viewer bundle not built (pnpm --filter @agentsdiagram/viewer build)")
    assert '<script type="application/json" id="agentsdiagram-data">' in page
    assert page.count("</script>") == 3  # data, mermaid, viewer: nothing inside closes them early
    data = page.split('id="agentsdiagram-data">', 1)[1].split("</script>", 1)[0]
    assert json.loads(data.replace("<\\/", "</"))["project"]["nodes"]
