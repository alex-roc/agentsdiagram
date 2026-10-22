"""Intermediate representation (IR) shared by every adapter, renderer and the editor protocol.

The IR is the contract between the Python core and the TypeScript viewer/extension:
``agentsdiagram schema`` exports its JSON Schema (serialization mode) and
``packages/protocol`` generates TS types from it. Bump ``IR_VERSION`` on any
breaking change.

Design notes (see docs/ir.md):
- Node ids are stable across runs (``framework:kind:module.qualname``), but they are
  not the only anchor for edits: every node and edge carries a ``SourceRef``.
- Positions use 1-based lines and 0-based columns counted in code points.
  The LSP layer converts columns to UTF-16.
- Fields that change often between library releases go to ``extra`` instead of the
  typed attributes, so the contract stays stable.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

IR_VERSION = "1"

Framework = Literal["pydantic_ai", "smolagents"]

NodeKind = Literal[
    "agent",
    "tool",
    "toolset",
    "mcp_server",
    "native_tool",
    "capability",
    "workflow",
    "external_tool_source",
    "graph",
    "graph_step",
    "dynamic",
]

EdgeKind = Literal[
    "uses",  # agent -> tool | toolset | mcp_server | native_tool | capability
    "provides",  # toolset | capability -> tool
    "wraps",  # toolset -> wrapped toolset
    "delegates_to",  # tool | capability -> agent (agent called from inside a tool)
    "manages",  # smolagents manager -> managed agent
    "runs",  # workflow -> agent (ordered by `order`)
    "contains",  # graph -> graph_step
    "transitions",  # graph_step -> graph_step
]

Status = Literal["resolved", "partial", "dynamic", "planned", "stale"]
Severity = Literal["error", "warning", "info"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class Position(_Model):
    line: int = Field(description="1-based line")
    column: int = Field(description="0-based column, in code points")


class Range(_Model):
    start: Position
    end: Position


class SourceRef(_Model):
    file: str = Field(description="POSIX path relative to the project root")
    range: Range
    name_range: Range | None = Field(
        default=None, description="Range of the identifier (variable, function or class name)"
    )


class NodeAttrs(_Model):
    """Typed attributes that are stable across library versions. Everything else goes to ``extra``."""

    agent_class: str | None = None
    model: str | None = None
    instructions: str | None = None
    dynamic_instructions: list[str] = Field(default_factory=list)
    description: str | None = None
    output_type: str | None = None
    deps_type: str | None = None
    docstring: str | None = None
    signature: str | None = None
    takes_ctx: bool | None = None
    url: str | None = None
    command: str | None = None
    badges: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class Node(_Model):
    id: str
    kind: NodeKind
    framework: Framework
    name: str
    status: Status = "resolved"
    source: SourceRef | None = None
    attrs: NodeAttrs = Field(default_factory=NodeAttrs)


class Edge(_Model):
    id: str
    kind: EdgeKind
    source: str
    target: str
    label: str | None = None
    order: int | None = Field(default=None, description="Call order for `runs` edges")
    wrappers: list[str] = Field(
        default_factory=list, description="Toolset wrappers applied on this edge, e.g. prefixed('x')"
    )
    ref: SourceRef | None = Field(default=None, description="Where this relation is written")


class Diagnostic(_Model):
    code: str
    severity: Severity
    message: str
    ref: SourceRef | None = None
    node_id: str | None = None


class FileInfo(_Model):
    path: str
    module: str
    frameworks: list[Framework] = Field(default_factory=list)
    status: Literal["ok", "stale", "error"] = "ok"
    sha256: str


class Project(_Model):
    ir_version: str = IR_VERSION
    tool_version: str
    root: str
    frameworks: list[Framework] = Field(default_factory=list)
    files: list[FileInfo] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)


def json_schema() -> dict[str, Any]:
    """JSON Schema of the IR (serialization mode: fields with defaults are always present).

    Property titles are dropped so generated TypeScript uses inline types instead of one
    alias per field.
    """
    schema = Project.model_json_schema(mode="serialization")

    def strip(node: Any, in_properties: bool = False) -> None:
        if isinstance(node, dict):
            if in_properties:
                for prop in node.values():
                    if isinstance(prop, dict):
                        prop.pop("title", None)
            for key, value in node.items():
                strip(value, key == "properties")
        elif isinstance(node, list):
            for item in node:
                strip(item)

    strip(schema)
    return schema
