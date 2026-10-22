// Pure IR -> React Flow transformation (no DOM, no React): unit-tested with the sample IR.
import type { Edge as IrEdge, Node as IrNode, Project } from "@agentsdiagram/protocol";

export type Kind = IrNode["kind"];
export type EdgeKind = IrEdge["kind"];

export const KINDS: Kind[] = [
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
];

export const KIND_LABELS: Record<Kind, string> = {
  agent: "Agent",
  tool: "Tool",
  toolset: "Toolset",
  mcp_server: "MCP server",
  native_tool: "Native tool",
  capability: "Capability",
  workflow: "Workflow",
  external_tool_source: "External source",
  graph: "Graph",
  graph_step: "Graph step",
  dynamic: "Dynamic",
};

export interface NodeData extends Record<string, unknown> {
  ir: IrNode;
  title: string;
  subtitle: string | null;
  badges: string[];
}

export interface FlowNode {
  id: string;
  type: Kind;
  data: NodeData;
  position: { x: number; y: number };
  parentId?: string;
  extent?: "parent";
  style?: Record<string, string | number>;
  width?: number;
  height?: number;
}

export interface EdgeData extends Record<string, unknown> {
  ir: IrEdge;
}

export interface FlowEdge {
  id: string;
  type: "default";
  source: string;
  target: string;
  label?: string;
  data: EdgeData;
  className: string;
  animated?: boolean;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export interface Filter {
  hiddenKinds: ReadonlySet<Kind>;
}

export const NODE_SIZE = { width: 210, height: 64 };

export function subtitleOf(n: IrNode): string | null {
  if (n.kind === "agent") return n.attrs.model ?? n.attrs.agent_class;
  if (n.kind === "mcp_server") return n.attrs.url ?? n.attrs.command;
  return null;
}

export function edgeLabel(e: IrEdge): string | undefined {
  const parts: string[] = [];
  if (e.order !== null) parts.push(`#${e.order}`);
  if (e.label) parts.push(e.label);
  if (e.wrappers.length) parts.push(e.wrappers.join(" · "));
  return parts.length ? parts.join(" ") : undefined;
}

/** Nodes and edges for React Flow, still unpositioned (see layout.ts). */
export function buildFlow(project: Project, filter: Filter = { hiddenKinds: new Set() }): FlowGraph {
  const visible = new Map<string, IrNode>();
  for (const n of project.nodes) if (!filter.hiddenKinds.has(n.kind)) visible.set(n.id, n);

  // graph_step -> graph, from `contains` edges (never drawn themselves).
  const parentOf = new Map<string, string>();
  for (const e of project.edges) {
    if (e.kind !== "contains") continue;
    if (visible.get(e.source)?.kind === "graph" && visible.get(e.target)?.kind === "graph_step") {
      parentOf.set(e.target, e.source);
    }
  }

  // React Flow requires parents before their children.
  const ordered = [...visible.values()].sort(
    (a, b) => Number(parentOf.has(a.id)) - Number(parentOf.has(b.id)),
  );
  const nodes: FlowNode[] = ordered.map((n) => {
    const parentId = parentOf.get(n.id);
    return {
      id: n.id,
      type: n.kind,
      position: { x: 0, y: 0 },
      ...(parentId ? { parentId, extent: "parent" as const } : {}),
      data: { ir: n, title: n.name, subtitle: subtitleOf(n), badges: n.attrs.badges },
    };
  });

  const edges: FlowEdge[] = [];
  for (const e of project.edges) {
    if (e.kind === "contains" || !visible.has(e.source) || !visible.has(e.target)) continue;
    const label = edgeLabel(e);
    edges.push({
      id: e.id,
      type: "default",
      source: e.source,
      target: e.target,
      ...(label ? { label } : {}),
      data: { ir: e },
      className: `edge edge-${e.kind}`,
      ...(e.kind === "delegates_to" || e.kind === "manages" ? { animated: true } : {}),
    });
  }
  return { nodes, edges };
}

/** Ids whose name matches (case-insensitive substring). Empty query matches nothing. */
export function searchNodes(nodes: readonly FlowNode[], query: string): string[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return nodes.filter((n) => n.data.ir.name.toLowerCase().includes(q)).map((n) => n.id);
}

export function kindsPresent(project: Project): Kind[] {
  const present = new Set(project.nodes.map((n) => n.kind));
  return KINDS.filter((k) => present.has(k));
}
