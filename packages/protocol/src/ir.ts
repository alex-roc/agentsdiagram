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
/**
 * Write a new (planned) agent. With ``parent`` it is wired to an existing agent:
 * a managed agent in smolagents, a delegation tool in PydanticAI.
 *
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "AddAgent".
 */
export interface AddAgent {
  op: "add_agent";
  framework: "pydantic_ai" | "smolagents";
  name: string;
  /**
   * POSIX path relative to the project root; created if missing
   */
  file: string;
  model?: string | null;
  instructions?: string | null;
  description?: string | null;
  /**
   * smolagents only
   */
  agent_class?: ("CodeAgent" | "ToolCallingAgent") | null;
  /**
   * Node id of the agent that manages / delegates to it
   */
  parent?: string | null;
}
/**
 * Connect an MCP server (URL or stdio command) to an agent.
 *
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "AddMcp".
 */
export interface AddMcp {
  op: "add_mcp";
  agent: string;
  name?: string | null;
  url?: string | null;
  /**
   * Shell-style command line, e.g. 'uvx arxiv-mcp-server'
   */
  command?: string | null;
}
/**
 * Write a planned tool stub and give it to an agent.
 *
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "AddTool".
 */
export interface AddTool {
  op: "add_tool";
  agent: string;
  name: string;
  description?: string | null;
  /**
   * Parameter list, e.g. 'order_id: str, limit: int = 5'
   */
  params?: string | null;
  returns?: string | null;
}
/**
 * Let ``source`` hand work to ``target``: managed_agents (smolagents) or a delegation tool (PydanticAI).
 *
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "Connect".
 */
export interface Connect {
  op: "connect";
  source: string;
  target: string;
  /**
   * smolagents: description added to the target if missing
   */
  description?: string | null;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "Disconnect".
 */
export interface Disconnect {
  op: "disconnect";
  edge: string;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "EditParams".
 */
export interface EditParams {
  request: AddAgent | AddTool | AddMcp | Connect | Disconnect | Remove | SetModel | SetInstructions | ExportSpec;
  /**
   * The files as the diagram saw them; the edit is refused if one changed since
   */
  expect?: FileVersion[];
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "Remove".
 */
export interface Remove {
  op: "remove";
  node: string;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "SetModel".
 */
export interface SetModel {
  op: "set_model";
  agent: string;
  model: string;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "SetInstructions".
 */
export interface SetInstructions {
  op: "set_instructions";
  agent: string;
  /**
   * Empty removes them
   */
  instructions: string;
}
/**
 * PydanticAI: move an agent's literal settings to an Agent Spec (YAML).
 *
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "ExportSpec".
 */
export interface ExportSpec {
  op: "export_spec";
  agent: string;
  /**
   * Spec file relative to the project root
   */
  path?: string | null;
  /**
   * Rewrite the code to load the spec with Agent.from_file
   */
  replace?: boolean;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "FileVersion".
 */
export interface FileVersion {
  /**
   * POSIX path relative to the project root
   */
  file: string;
  sha256: string;
}
/**
 * This interface was referenced by `Project`'s JSON-Schema
 * via the `definition` "EditResult".
 */
export interface EditResult {
  ok: boolean;
  message: string;
  /**
   * Files changed or created
   */
  files: string[];
  /**
   * Id of the node to select once the graph is redrawn
   */
  focus: string | null;
}
