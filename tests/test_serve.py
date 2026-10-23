"""`agentsdiagram serve`: the live page, the API, the edit endpoint and its guards."""

import json
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from agentsdiagram.serve import LiveProject, make_server

EXAMPLES = Path(__file__).parent.parent / "examples"


def page(base: str) -> str:
    """The viewer page, or skip when the bundle is not built (the Python CI job does not build it)."""
    try:
        return get(base + "/")[1]
    except urllib.error.HTTPError as exc:
        if exc.code == 500 and b"viewer bundle" in exc.read():
            pytest.skip("viewer bundle not built (pnpm --filter @agentsdiagram/viewer build)")
        raise


@pytest.fixture
def server(tmp_path: Path):
    shutil.copytree(EXAMPLES / "research_team", tmp_path / "team")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    live = LiveProject(tmp_path)
    srv = make_server(live, port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv, live, f"http://127.0.0.1:{srv.server_port}"
    live.stop()
    srv.shutdown()
    srv.server_close()


def get(url: str, headers: dict | None = None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=10) as r:
        return r.status, r.read().decode()


def post(url: str, body: dict, headers: dict):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def test_page_and_graph(server):
    srv, _, base = server
    _, graph = get(base + "/api/graph")
    names = {n["name"] for n in json.loads(graph)["project"]["nodes"]}
    assert {"lead", "analyst", "web_researcher"} <= names
    _, mermaid = get(base + "/api/mermaid")
    assert mermaid.startswith("---") or "flowchart" in mermaid
    html = page(base)
    assert 'id="agentsdiagram-live"' in html and srv.token in html


def test_edit_needs_the_token_and_writes(server, tmp_path):
    srv, live, base = server
    request = {"request": {"op": "add_tool", "agent": "smolagents:agent:team.team.analyst", "name": "lookup"}}
    status, body = post(base + "/api/edit", request, {})
    assert status == 403 and not body["ok"]
    version = live.version
    status, body = post(base + "/api/edit", request, {"X-Agentsdiagram-Token": srv.token})
    assert status == 200 and body["ok"], body
    assert body["focus"] == "smolagents:tool:team.team.lookup"
    assert "def lookup(query: str) -> str:" in (tmp_path / "team/team.py").read_text()
    assert live.version > version  # redrawn right away, before the watcher notices
    _, graph = get(base + "/api/graph")
    assert "lookup" in {n["name"] for n in json.loads(graph)["project"]["nodes"]}
    status, body = post(base + "/api/edit", {"request": {"op": "nope"}}, {"X-Agentsdiagram-Token": srv.token})
    assert status == 400


def test_other_hosts_are_refused(server):
    _, _, base = server
    with pytest.raises(urllib.error.HTTPError) as err:
        get(base + "/api/graph", {"Host": "evil.example.com"})
    assert err.value.code == 403


def test_read_only(tmp_path):
    (tmp_path / "a.py").write_text("from smolagents import CodeAgent\n")
    live = LiveProject(tmp_path)
    srv = make_server(live, port=0, editable=False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        status, _ = post(base + "/api/edit", {"request": {}}, {"X-Agentsdiagram-Token": srv.token})
        assert status == 403
        html = page(base)
        assert '"editable": false' in html and srv.token not in html
    finally:
        srv.shutdown()
        srv.server_close()
