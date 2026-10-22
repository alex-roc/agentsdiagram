// dagre layout: top level LR; each graph group is laid out internally (TB) and then
// placed as one block of its computed size.
import dagre from "@dagrejs/dagre";
import { NODE_SIZE, sizeOf, type FlowGraph, type FlowNode } from "./model";

const GAP = 48;
const GROUP_PAD = { x: 24, top: 44, bottom: 24 };

interface LayoutEdge {
  source: string;
  target: string;
  label?: string | undefined;
}

interface Box {
  width: number;
  height: number;
}

function runDagre(
  ids: string[],
  size: (id: string) => Box,
  edges: LayoutEdge[],
  rankdir: "LR" | "TB",
): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir, nodesep: 36, ranksep: 70, marginx: 0, marginy: 0 });
  g.setDefaultEdgeLabel(() => ({}));
  const known = new Set(ids);
  for (const id of ids) g.setNode(id, { ...size(id) }); // dagre writes x/y into the label: never share objects
  for (const e of edges) {
    if (!known.has(e.source) || !known.has(e.target) || e.source === e.target) continue;
    // reserve room for the label so it is not drawn under a node
    g.setEdge(e.source, e.target, e.label ? { width: e.label.length * 6.6 + 12, height: 18, labelpos: "c" } : {});
  }
  dagre.layout(g);
  const out = new Map<string, { x: number; y: number }>();
  for (const id of ids) {
    const n = g.node(id);
    const s = size(id);
    out.set(id, { x: n.x - s.width / 2, y: n.y - s.height / 2 });
  }
  return out;
}

/**
 * dagre stacks disconnected components in one column; lay each component out on its own
 * and shelf-pack them into rows so the diagram keeps a screen-like aspect ratio.
 */
function layoutComponents(
  ids: string[],
  size: (id: string) => Box,
  edges: LayoutEdge[],
): Map<string, { x: number; y: number }> {
  const parent = new Map(ids.map((id) => [id, id]));
  const find = (x: string): string => {
    const p = parent.get(x)!;
    if (p === x) return x;
    const r = find(p);
    parent.set(x, r);
    return r;
  };
  for (const e of edges) if (parent.has(e.source) && parent.has(e.target)) parent.set(find(e.source), find(e.target));
  const comps = new Map<string, string[]>();
  for (const id of ids) comps.set(find(id), [...(comps.get(find(id)) ?? []), id]);

  const laid = [...comps.values()].map((members) => {
    const set = new Set(members);
    const pos = runDagre(members, size, edges.filter((e) => set.has(e.source) && set.has(e.target)), "LR");
    let width = 0;
    let height = 0;
    for (const [id, p] of pos) {
      width = Math.max(width, p.x + size(id).width);
      height = Math.max(height, p.y + size(id).height);
    }
    return { pos, width, height };
  });
  laid.sort((a, b) => b.height - a.height);

  const area = laid.reduce((acc, c) => acc + (c.width + GAP) * (c.height + GAP), 0);
  const rowWidth = Math.max(Math.sqrt(area * 1.8), ...laid.map((c) => c.width));
  const out = new Map<string, { x: number; y: number }>();
  let x = 0;
  let y = 0;
  let rowH = 0;
  for (const c of laid) {
    if (x > 0 && x + c.width > rowWidth) {
      x = 0;
      y += rowH + GAP;
      rowH = 0;
    }
    for (const [id, p] of c.pos) out.set(id, { x: p.x + x, y: p.y + y });
    x += c.width + GAP;
    rowH = Math.max(rowH, c.height);
  }
  return out;
}

export function layoutGraph(graph: FlowGraph): FlowGraph {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const children = new Map<string, FlowNode[]>();
  for (const n of graph.nodes) {
    if (n.parentId && byId.has(n.parentId)) {
      children.set(n.parentId, [...(children.get(n.parentId) ?? []), n]);
    }
  }
  const groupOf = (id: string) => byId.get(id)?.parentId ?? id;
  const box = (id: string): Box => {
    const n = byId.get(id);
    return n ? sizeOf(n.data.ir) : NODE_SIZE;
  };

  // 1. inside each group
  const sizes = new Map<string, Box>();
  const placed = new Map<string, { x: number; y: number }>();
  for (const [gid, kids] of children) {
    const ids = kids.map((k) => k.id);
    const inner = graph.edges.filter((e) => groupOf(e.source) === gid && groupOf(e.target) === gid && e.source !== gid);
    const pos = runDagre(ids, box, inner, "TB");
    let w = 0;
    let h = 0;
    for (const [id, p] of pos) {
      w = Math.max(w, p.x + box(id).width);
      h = Math.max(h, p.y + box(id).height);
    }
    for (const [id, p] of pos) placed.set(id, { x: p.x + GROUP_PAD.x, y: p.y + GROUP_PAD.top });
    sizes.set(gid, { width: w + GROUP_PAD.x * 2, height: h + GROUP_PAD.top + GROUP_PAD.bottom });
  }

  // 2. top level, groups as blocks; edges re-pointed at their group
  const top = graph.nodes.filter((n) => !n.parentId || !byId.has(n.parentId));
  const topEdges = graph.edges.map((e) => ({ source: groupOf(e.source), target: groupOf(e.target), label: e.label }));
  const topPos = layoutComponents(top.map((n) => n.id), (id) => sizes.get(id) ?? box(id), topEdges);

  // Only groups with children get a container size; everything else is a plain card.
  const nodes: FlowNode[] = graph.nodes.map((n) => {
    const isChild = Boolean(n.parentId && byId.has(n.parentId));
    const group = sizes.get(n.id);
    const position = (isChild ? placed.get(n.id) : topPos.get(n.id)) ?? { x: 0, y: 0 };
    return { ...n, position, ...(group ?? box(n.id)) };
  });
  return { nodes, edges: graph.edges };
}
