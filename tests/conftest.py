from pathlib import Path

import pytest

from agentsdiagram.analyze import analyze
from agentsdiagram.ir import Project

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_project() -> Project:
    return analyze(FIXTURES)


def by_name(project: Project, name: str, kind: str | None = None):
    matches = [n for n in project.nodes if n.name == name and (kind is None or n.kind == kind)]
    assert matches, f"no node named {name!r} ({kind})"
    return matches[0]


def edges_from(project: Project, node_id: str, kind: str | None = None):
    return [e for e in project.edges if e.source == node_id and (kind is None or e.kind == kind)]


def target_names(project: Project, node_id: str, kind: str | None = None) -> set[str]:
    nodes = {n.id: n for n in project.nodes}
    return {nodes[e.target].name for e in edges_from(project, node_id, kind)}
