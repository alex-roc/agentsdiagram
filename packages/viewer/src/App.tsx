import type { Diagnostic, GraphResult, HostMessage } from "@agentsdiagram/protocol";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type ColorMode,
  type Node as RFNode,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Detail } from "./Detail";
import { layoutGraph } from "./layout";
import { buildFlow, KIND_LABELS, kindsPresent, searchNodes, type Kind } from "./model";
import { nodeTypes, type ADNode } from "./nodes";
import type { ViewerTransport } from "./transport";

type Status = { state: "starting" | "ready" | "error"; message?: string };

function useColorMode(): ColorMode {
  const read = (): ColorMode => {
    const cl = document.body.classList;
    if (cl.contains("vscode-dark") || cl.contains("vscode-high-contrast")) return "dark";
    if (cl.contains("vscode-light") || cl.contains("vscode-high-contrast-light")) return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  };
  const [mode, setMode] = useState<ColorMode>(read);
  useEffect(() => {
    const update = () => setMode(read());
    const mo = new MutationObserver(update);
    mo.observe(document.body, { attributes: true, attributeFilter: ["class"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", update);
    return () => {
      mo.disconnect();
      mq.removeEventListener("change", update);
    };
  }, []);
  return mode;
}

function Viewer({ transport }: { transport: ViewerTransport }) {
  const [result, setResult] = useState<GraphResult | null>(null);
  const [status, setStatus] = useState<Status>({ state: "starting" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hidden, setHidden] = useState<ReadonlySet<Kind>>(new Set());
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const colorMode = useColorMode();
  const rf = useReactFlow();

  const focus = useCallback(
    (id: string) => {
      // let React Flow measure freshly rendered nodes first
      requestAnimationFrame(() => void rf.fitView({ nodes: [{ id }], duration: 300, maxZoom: 1.2, padding: 0.6 }));
    },
    [rf],
  );

  useEffect(() => {
    return transport.subscribe((m: HostMessage) => {
      if (m.type === "graph") {
        setResult(m.result);
        setStatus({ state: "ready" });
      } else if (m.type === "status") {
        setStatus({ state: m.state, ...(m.message ? { message: m.message } : {}) });
      } else if (m.type === "select") {
        setSelectedId(m.nodeId);
        if (m.nodeId) focus(m.nodeId);
      }
    });
  }, [transport, focus]);

  const project = result?.project ?? null;
  const laidOut = useMemo(() => (project ? layoutGraph(buildFlow(project, { hiddenKinds: hidden })) : null), [project, hidden]);
  const matches = useMemo(() => new Set(laidOut ? searchNodes(laidOut.nodes, query) : []), [laidOut, query]);
  const searching = query.trim() !== "";

  // keep the viewport sensible when the graph (or filter) changes
  useEffect(() => {
    if (!laidOut || !laidOut.nodes.length) return;
    const t = setTimeout(() => void rf.fitView({ duration: 200, padding: 0.15 }), 100); // after measuring
    return () => clearTimeout(t);
  }, [laidOut, rf]);

  const nodes = useMemo<RFNode[]>(
    () =>
      (laidOut?.nodes ?? []).map((n) => ({
        ...n,
        selected: n.id === selectedId,
        // groups sit behind their children
        zIndex: n.type === "graph" ? 0 : 1,
        data: { ...n.data, match: matches.has(n.id), dim: searching && !matches.has(n.id) },
      })),
    [laidOut, selectedId, matches, searching],
  );

  const edges = useMemo(
    () =>
      (laidOut?.edges ?? []).map((e) => {
        const touched = selectedId !== null && (e.source === selectedId || e.target === selectedId);
        return { ...e, markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 }, className: `${e.className}${touched ? " touched" : ""}`, ariaLabel: e.label ?? e.data.ir.kind };
      }),
    [laidOut, selectedId],
  );

  const select = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      transport.post({ type: "selectionChanged", nodeId: id });
    },
    [transport],
  );

  const selectedNode = project?.nodes.find((n) => n.id === selectedId) ?? null;
  const diagnostics = project?.diagnostics ?? [];

  const onDiagnostic = (d: Diagnostic) => {
    if (d.node_id && laidOut?.nodes.some((n) => n.id === d.node_id)) {
      select(d.node_id);
      focus(d.node_id);
    } else if (d.ref) {
      transport.post({ type: "reveal", nodeId: d.node_id ?? "", source: d.ref });
    }
  };

  const onSearch = (q: string) => {
    setQuery(q);
    const first = laidOut ? searchNodes(laidOut.nodes, q)[0] : undefined;
    if (first) focus(first);
  };

  const toggleKind = (k: Kind) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  const copyMermaid = () => {
    transport.post({ type: "copyMermaid" });
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const kinds = project ? kindsPresent(project) : [];
  const empty = project !== null && project.nodes.length === 0;

  return (
    <div className="viewer">
      <header className="toolbar" role="toolbar" aria-label="Diagram controls">
        <input
          type="search"
          className="search"
          placeholder="Search by name…"
          aria-label="Search nodes by name"
          value={query}
          onChange={(e) => onSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && laidOut) {
              const ids = searchNodes(laidOut.nodes, query);
              if (ids.length) focus(ids[(ids.indexOf(selectedId ?? "") + 1) % ids.length] ?? ids[0]!);
            }
          }}
        />
        {searching && <span className="count" aria-live="polite">{matches.size} {matches.size === 1 ? "match" : "matches"}</span>}
        <button
          className="btn secondary"
          aria-expanded={filtersOpen}
          aria-controls="kind-filter"
          onClick={() => setFiltersOpen((o) => !o)}
        >
          Filter{hidden.size ? ` (${hidden.size} hidden)` : ""}
        </button>
        <span className="spacer" />
        {transport.canCopyMermaid && (
          <button className="btn secondary" onClick={copyMermaid}>
            {copied ? "Copied!" : "Copy Mermaid"}
          </button>
        )}
      </header>
      {filtersOpen && (
        <fieldset id="kind-filter" className="filters">
          <legend className="sr-only">Filter by node kind</legend>
          {kinds.map((k) => (
            <label key={k} className={`chip kind-${k}`}>
              <input type="checkbox" checked={!hidden.has(k)} onChange={() => toggleKind(k)} />
              {KIND_LABELS[k]}
            </label>
          ))}
        </fieldset>
      )}
      <div className="main">
        <div className="canvas" aria-label="Agents diagram">
          {status.state !== "ready" && !project && (
            <div className={`overlay ${status.state}`} role="status">
              {status.state === "error" ? `Error: ${status.message ?? "unknown"}` : status.message ?? "Analyzing…"}
            </div>
          )}
          {status.state === "error" && project && (
            <div className="banner error" role="alert">{status.message ?? "Error"}</div>
          )}
          {empty && <div className="overlay" role="status">No agents found in this scope.</div>}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            colorMode={colorMode}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            onNodeClick={(_, n: ADNode | RFNode) => select(n.id)}
            onPaneClick={() => select(null)}
            minZoom={0.1}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        {(selectedNode || diagnostics.length > 0) && (
          <div className="side">
            {selectedNode && (
              <Detail
                node={selectedNode}
                diagnostics={diagnostics.filter((d) => d.node_id === selectedNode.id)}
                onReveal={() => selectedNode.source && transport.post({ type: "reveal", nodeId: selectedNode.id, source: selectedNode.source })}
                onClose={() => select(null)}
              />
            )}
            {diagnostics.length > 0 && (
              <section className="panel" aria-label="Diagnostics">
                <h3>Diagnostics ({diagnostics.length})</h3>
                <ul className="diag-list">
                  {diagnostics.map((d, i) => (
                    <li key={i} className={`sev-${d.severity}`}>
                      <button className="link" onClick={() => onDiagnostic(d)}>
                        <code>{d.code}</code> {d.message}
                        {d.ref && <span className="loc"> {d.ref.file}:{d.ref.range.start.line}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function App({ transport }: { transport: ViewerTransport | null }) {
  if (!transport) {
    return <div className="overlay error" role="alert">No data: missing VS Code transport or the #agentsdiagram-data script.</div>;
  }
  return (
    <ReactFlowProvider>
      <Viewer transport={transport} />
    </ReactFlowProvider>
  );
}
