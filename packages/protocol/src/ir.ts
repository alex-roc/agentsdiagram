/* Generated from ir.schema.json by json-schema-to-typescript. Do not edit: run `pnpm schema` at the repo root. */

export interface Project {
  ir_version: string;
  tool_version: string;
  root: string;
  frameworks: ("pydantic_ai" | "smolagents")[];
  files: FileInfo[];
  nodes: Node[];
  edges: Edge[];
  diagnostics: Diagnostic[];
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "FileInfo".
 */
export interface FileInfo {
  path: string;
  module: string;
  frameworks: ("pydantic_ai" | "smolagents")[];
  status: "ok" | "stale" | "error";
  sha256: string;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "Node".
 */
export interface Node {
  id: string;
  kind:
    | "agent"
    | "tool"
    | "toolset"
    | "mcp_server"
    | "native_tool"
    | "capability"
    | "workflow"
    | "external_tool_source"
    | "graph"
    | "graph_step"
    | "dynamic";
  framework: "pydantic_ai" | "smolagents";
  name: string;
  status: "resolved" | "partial" | "dynamic" | "planned" | "stale";
  source: SourceRef | null;
  attrs: NodeAttrs;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "SourceRef".
 */
export interface SourceRef {
  /**
   * POSIX path relative to the project root
   */
  file: string;
  range: Range;
  /**
   * Range of the identifier (variable, function or class name)
   */
  name_range: Range | null;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "Range".
 */
export interface Range {
  start: Position;
  end: Position;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "Position".
 */
export interface Position {
  /**
   * 1-based line
   */
  line: number;
  /**
   * 0-based column, in code points
   */
  column: number;
}
/**
 * Typed attributes that are stable across library versions. Everything else goes to ``extra``.
 *
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "NodeAttrs".
 */
export interface NodeAttrs {
  agent_class: string | null;
  model: string | null;
  instructions: string | null;
  dynamic_instructions: string[];
  description: string | null;
  output_type: string | null;
  deps_type: string | null;
  docstring: string | null;
  signature: string | null;
  takes_ctx: boolean | null;
  url: string | null;
  command: string | null;
  badges: string[];
  extra: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "Edge".
 */
export interface Edge {
  id: string;
  kind: "uses" | "provides" | "wraps" | "delegates_to" | "manages" | "runs" | "contains" | "transitions";
  source: string;
  target: string;
  label: string | null;
  /**
   * Call order for `runs` edges
   */
  order: number | null;
  /**
   * Toolset wrappers applied on this edge, e.g. prefixed('x')
   */
  wrappers: string[];
  /**
   * Where this relation is written
   */
  ref: SourceRef | null;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "Diagnostic".
 */
export interface Diagnostic {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  ref: SourceRef | null;
  node_id: string | null;
}
