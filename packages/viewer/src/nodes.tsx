import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Node as RFNode } from "@xyflow/react";
import { Icon } from "./icons";
import { KIND_LABELS, type NodeData } from "./model";

export type ADNode = RFNode<NodeData>;

function isTerminal(data: NodeData): boolean {
  const role = data.ir.attrs.extra["role"];
  return data.ir.kind === "graph_step" && (role === "start" || role === "end");
}

function stateClasses(data: NodeData, selected: boolean): string {
  return [selected ? "selected" : "", data["match"] ? "match" : "", data["dim"] ? "dim" : ""].join(" ");
}

/** Second line of a card: the model for agents, otherwise the kind and where it comes from. */
function caption(data: NodeData): string {
  const { ir } = data;
  if (data.subtitle) return data.subtitle;
  if (ir.kind === "graph_step") return ir.attrs.extra["role"] === "decision" ? "Decision" : "Step";
  const origin = data.badges[0];
  const label = KIND_LABELS[ir.kind];
  return origin && !label.toLowerCase().includes(origin.toLowerCase()) ? `${label}, ${origin}` : label;
}

function KindNode({ data, selected }: NodeProps<ADNode>) {
  const { ir } = data;
  const vertical = ir.kind === "graph_step";
  if (isTerminal(data)) {
    return (
      <div className={`ad-terminal ${stateClasses(data, selected)}`} title={`${ir.name} of the flow`}>
        <Handle type="target" position={Position.Top} />
        {ir.name}
        <Handle type="source" position={Position.Bottom} />
      </div>
    );
  }
  const agent = ir.kind === "agent";
  const extraBadges = agent ? data.badges : data.badges.slice(1);
  const classes = ["ad-node", `kind-${ir.kind}`, `status-${ir.status}`, stateClasses(data, selected)].join(" ");
  return (
    <div className={classes} title={`${KIND_LABELS[ir.kind]}: ${ir.name}`}>
      <Handle type="target" position={vertical ? Position.Top : Position.Left} />
      <span className="ad-tile">
        <Icon name={ir.kind} size={agent ? 18 : 15} />
      </span>
      <div className="ad-body">
        <div className="ad-title">{data.title}</div>
        <div className="ad-sub">
          {agent && data.subtitle ? <span className="ad-model">{data.subtitle}</span> : caption(data)}
        </div>
        {extraBadges.length > 0 && (
          <div className="ad-badges">
            {extraBadges.map((b) => (
              <span key={b} className="ad-badge">
                {b}
              </span>
            ))}
          </div>
        )}
      </div>
      {ir.status !== "resolved" && <span className={`ad-status s-${ir.status}`}>{ir.status}</span>}
      {data["problem"] ? (
        <span className={`ad-problem p-${String(data["problem"])}`} title={data["problem"] === "error" ? "Has errors" : "Has warnings"}>
          <span className="sr-only">{data["problem"] === "error" ? "Has errors" : "Has warnings"}</span>
        </span>
      ) : null}
      <Handle type="source" position={vertical ? Position.Bottom : Position.Right} />
    </div>
  );
}

function GroupNode({ data, selected }: NodeProps<ADNode>) {
  const { ir } = data;
  return (
    <div className={`ad-group status-${ir.status} ${stateClasses(data, selected)}`}>
      <Handle type="target" position={Position.Left} />
      <div className="ad-group-title">
        <Icon name="graph" size={14} />
        <span className="ad-group-name">{data.title}</span>
        <span className="ad-group-fw">pydantic-graph</span>
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
