"""End-to-end tests of the language server with pytest-lsp (real stdio process)."""

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_lsp
from conftest import FIXTURES
from lsprotocol import types
from pytest_lsp import ClientServerConfig, LanguageClient

pytest.importorskip("pygls")


def plain(value):
    """pygls turns JSON objects of custom methods into namedtuples on the client side."""
    if hasattr(value, "_asdict"):
        return {k: plain(v) for k, v in value._asdict().items()}
    if isinstance(value, list | tuple):
        return [plain(v) for v in value]
    return value


async def request(client: LanguageClient, method: str, params: dict) -> dict:
    return plain(await client.protocol.send_request_async(method, params))


@pytest_lsp.fixture(config=ClientServerConfig(server_command=[sys.executable, "-m", "agentsdiagram.cli", "lsp"]))
async def client(lsp_client: LanguageClient):
    result = await lsp_client.initialize_session(
        types.InitializeParams(
            capabilities=types.ClientCapabilities(),
            workspace_folders=[types.WorkspaceFolder(uri=(FIXTURES / "smol").as_uri(), name="smol")],
        )
    )
    assert result.capabilities.experimental == {"agentsdiagram": {"protocolVersion": "2", "edit": True}}
    yield
    await lsp_client.shutdown_session()


@pytest.mark.asyncio(loop_scope="function")
async def test_graph_request(client: LanguageClient):
    result = await request(client, "agentsdiagram/graph", {"scope": {"kind": "workspace"}})
    names = {n["name"] for n in result["project"]["nodes"] if n["kind"] == "agent"}
    assert {"manager", "web_agent", "boss", "helper"} <= names
    assert result["protocolVersion"] == "2"


@pytest.mark.asyncio(loop_scope="function")
async def test_file_scope_and_mermaid(client: LanguageClient):
    uri = (FIXTURES / "smol" / "managed.py").as_uri()
    result = await request(client, "agentsdiagram/graph", {"scope": {"kind": "file", "uri": uri}})
    names = {n["name"] for n in result["project"]["nodes"] if n["kind"] == "agent"}
    assert names == {"manager", "web_agent"}
    text = await request(client, "agentsdiagram/mermaid", {"scope": {"kind": "file", "uri": uri}})
    assert text["text"].count("flowchart LR") == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_diagnostics_code_lens_and_unsaved_edits(client: LanguageClient):
    path = FIXTURES / "smol" / "managed_without_name.py"
    uri = path.as_uri()
    client.text_document_did_open(
        types.DidOpenTextDocumentParams(
            text_document=types.TextDocumentItem(uri=uri, language_id="python", version=1, text=path.read_text())
        )
    )
    await client.wait_for_notification(types.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS)
    for _ in range(20):
        if any(d.code == "AD201" for d in client.diagnostics.get(uri, [])):
            break
        await client.wait_for_notification(types.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS)
    codes = sorted(d.code for d in client.diagnostics[uri])
    assert codes == ["AD201", "AD203", "AD203", "AD204"]

    lenses = await client.text_document_code_lens_async(
        types.CodeLensParams(text_document=types.TextDocumentIdentifier(uri=uri))
    )
    assert {lens.command.command for lens in lenses} == {"agentsdiagram.showNode"}
    assert len(lenses) == 2  # helper, boss

    # an unsaved edit that adds a third agent shows up without touching the file
    text = path.read_text() + '\nextra = ToolCallingAgent(tools=[], model=model, name="extra")\n'
    client.text_document_did_change(
        types.DidChangeTextDocumentParams(
            text_document=types.VersionedTextDocumentIdentifier(uri=uri, version=2),
            content_changes=[types.TextDocumentContentChangeWholeDocument(text=text)],
        )
    )
    await client.wait_for_notification("agentsdiagram/graphChanged")
    result = await request(client, "agentsdiagram/graph", {"scope": {"kind": "workspace"}})
    assert "extra" in {n["name"] for n in result["project"]["nodes"]}


# ---------------------------------------------------------------------- edits

EDIT_ROOT = Path(tempfile.mkdtemp(prefix="agentsdiagram-lsp-"))


def apply_text_edits(text: str, edits: list[dict]) -> str:
    lines = text.splitlines(keepends=True)
    for e in sorted(edits, key=lambda e: (e["range"]["start"]["line"], e["range"]["start"]["character"]), reverse=True):
        start, end = e["range"]["start"], e["range"]["end"]
        assert start["character"] == 0 and end["character"] == 0  # whole-line edits
        lines[start["line"] : end["line"]] = [e["newText"]] if e["newText"] else []
    return "".join(lines)


@pytest_lsp.fixture(config=ClientServerConfig(server_command=[sys.executable, "-m", "agentsdiagram.cli", "lsp"]))
async def edit_client(lsp_client: LanguageClient):
    shutil.rmtree(EDIT_ROOT, ignore_errors=True)
    shutil.copytree(FIXTURES / "smol", EDIT_ROOT)
    (EDIT_ROOT / "pyproject.toml").write_text('[project]\nname = "smol"\n')
    await lsp_client.initialize_session(
        types.InitializeParams(
            capabilities=types.ClientCapabilities(),
            workspace_folders=[types.WorkspaceFolder(uri=EDIT_ROOT.as_uri(), name="smol")],
        )
    )
    yield
    await lsp_client.shutdown_session()


@pytest.mark.asyncio(loop_scope="function")
async def test_edit_returns_a_versioned_workspace_edit(edit_client: LanguageClient):
    path = EDIT_ROOT / "managed.py"
    uri = path.as_uri()
    unsaved = "# unsaved comment\n" + path.read_text()
    edit_client.text_document_did_open(
        types.DidOpenTextDocumentParams(
            text_document=types.TextDocumentItem(uri=uri, language_id="python", version=7, text=unsaved)
        )
    )
    sha = hashlib.sha256(unsaved.encode()).hexdigest()
    for _ in range(20):  # the first graphChanged may be the one from startup
        await edit_client.wait_for_notification("agentsdiagram/graphChanged")
        graph = await request(edit_client, "agentsdiagram/graph", {"scope": {"kind": "workspace"}})
        if any(f["path"] == "managed.py" and f["sha256"] == sha for f in graph["project"]["files"]):
            break
    manager = next(n for n in graph["project"]["nodes"] if n["name"] == "manager")
    params = {
        "request": {"op": "add_tool", "agent": manager["id"], "name": "lookup", "params": "term: str"},
        "expect": [{"file": "managed.py", "sha256": sha}],
    }
    result = await request(edit_client, "agentsdiagram/edit", params)
    assert result["ok"], result["message"]
    assert result["focus"].endswith("managed.lookup")
    (change,) = result["edit"]["documentChanges"]
    assert change["textDocument"] == {"uri": uri, "version": 7}
    new_text = apply_text_edits(unsaved, change["edits"])
    assert new_text.startswith("# unsaved comment\n")
    assert (
        "tools=[get_weather, lookup]" in new_text and 'raise NotImplementedError("agentsdiagram: planned")' in new_text
    )
    assert path.read_text() == unsaved.removeprefix("# unsaved comment\n")  # the server never writes

    stale = params | {"expect": [{"file": "managed.py", "sha256": "0" * 64}]}
    refused = await request(edit_client, "agentsdiagram/edit", stale)
    assert not refused["ok"] and "changed since" in refused["message"]
