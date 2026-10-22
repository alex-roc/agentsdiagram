import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Node as RFNode } from "@xyflow/react";
import type { Kind, NodeData } from "./model";

export type ADNode = RFNode<NodeData>;

export const ICONS: Record<Kind, string> = {
  agent: "🤖",
  tool: "🔧",
  toolset: "🧰",
  mcp_server: "🔌",
  native_tool: "⚙️",
  capability: "✨",
  workflow: "🔀",
  external_tool_source: "🌐",
  graph: "🕸️",
  graph_step: "◆",
  dynamic: "❓",
};

function isTerminal(data: NodeData): boolean {
  const role = data.ir.attrs.extra["role"];
  return data.ir.kind === "graph_step" && (role === "start" || role === "end");
}

function KindNode({ data, selected }: NodeProps<ADNode>) {
  const { ir } = data;
  const vertical = ir.kind === "graph_step";
  const terminal = isTerminal(data);
  const classes = [
    "ad-node",
    `kind-${ir.kind}`,
    `status-${ir.status}`,
    terminal ? "terminal" : "",
    selected ? "selected" : "",
    data["match"] ? "match" : "",
    data["dim"] ? "dim" : "",
  ].join(" ");
  return (
    <div className={classes} title={`${ir.kind}: ${ir.name}`}>
      <Handle type="target" position={vertical ? Position.Top : Position.Left} />
      <span className="ad-icon" aria-hidden="true">
        {ICONS[ir.kind]}
      </span>
      <div className="ad-body">
        <div className="ad-title">{data.title}</div>
        {data.subtitle && !terminal && <div className="ad-sub">{data.subtitle}</div>}
        {data.badges.length > 0 && !terminal && (
          <div className="ad-badges">
            {data.badges.map((b) => (
              <span key={b} className="ad-badge">
                {b}
              </span>
            ))}
          </div>
        )}
        {ir.status !== "resolved" && !terminal && <div className="ad-status">{ir.status}</div>}
      </div>
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} />
    </div>
  );
}

function GroupNode({ data, selected }: NodeProps<ADNode>) {
  const { ir } = data;
  const classes = ["ad-group", `status-${ir.status}`, selected ? "selected" : "", data["match"] ? "match" : "", data["dim"] ? "dim" : ""].join(" ");
  return (
    <div className={classes}>
      <Handle type="target" position={Position.Left} />
      <div className="ad-group-title">
        <span aria-hidden="true">{ICONS.graph}</span> {data.title}
        <span className="ad-group-fw">{ir.framework}</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export const nodeTypes = {
  agent: KindNode,
  tool: KindNode,
  toolset: KindNode,
  mcp_server: KindNode,
  native_tool: KindNode,
  capability: KindNode,
  workflow: KindNode,
  external_tool_source: KindNode,
  graph: GroupNode,
  graph_step: KindNode,
  dynamic: KindNode,
};
