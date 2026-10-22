import type { Diagnostic, GraphResult, HostMessage } from "@agentsdiagram/protocol";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type ColorMode,
  type Node as RFNode,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Detail } from "./Detail";
import { Icon } from "./icons";
import { layoutGraph } from "./layout";
import { buildFlow, kindCounts, KIND_LABELS, kindsPresent, neighborhood, searchNodes, type Kind } from "./model";
import { nodeTypes, type ADNode } from "./nodes";
import type { ViewerTransport } from "./transport";

type Status = { state: "starting" | "ready" | "error"; message?: string };
type ThemeChoice = "light" | "dark" | null; // null: follow the system

const THEME_KEY = "agentsdiagram.theme";


function readStoredTheme(): ThemeChoice {
  try {
    const v = window.localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

/** VS Code decides the theme in the webview; in a browser the user can override the system. */
function useTheme(): { mode: ColorMode; hosted: boolean; toggle: () => void } {
  const [choice, setChoice] = useState<ThemeChoice>(readStoredTheme);
  const read = useCallback((): { mode: ColorMode; hosted: boolean } => {
    const cl = document.body.classList;
    if (cl.contains("vscode-dark") || cl.contains("vscode-high-contrast")) return { mode: "dark", hosted: true };
    if (cl.contains("vscode-light") || cl.contains("vscode-high-contrast-light")) return { mode: "light", hosted: true };
    if (choice) return { mode: choice, hosted: false };
    return { mode: window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light", hosted: false };
  }, [choice]);
  const [state, setState] = useState(read);
  useEffect(() => {
    const update = () => setState(read());
    update();
    const mo = new MutationObserver(update);
    mo.observe(document.body, { attributes: true, attributeFilter: ["class"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", update);
    return () => {
      mo.disconnect();
      mq.removeEventListener("change", update);
    };
  }, [read]);
  useEffect(() => {
    document.documentElement.dataset["theme"] = state.mode;
  }, [state.mode]);
  const toggle = () => {
    const next = state.mode === "dark" ? "light" : "dark";
    setChoice(next);
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // private window or blocked storage: the choice lasts until reload
    }
  };
  return { ...state, toggle };
}

function basename(path: string): string {
  return path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || path;
}

/** Name in the top bar: the page title given by `scan --title`, else the file or folder shown. */
function titleOf(result: GraphResult): string {
  const given = document.getElementById("root")?.dataset["title"];
  if (given) return given;
  if (result.scope.kind === "file" && result.scope.uri) return basename(decodeURIComponent(result.scope.uri));
  return basename(result.project.root);
}

function Viewer({ transport }: { transport: ViewerTransport }) {
  const [result, setResult] = useState<GraphResult | null>(null);
  const [status, setStatus] = useState<Status>({ state: "starting" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hidden, setHidden] = useState<ReadonlySet<Kind>>(new Set());
  const [problemsOpen, setProblemsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const theme = useTheme();
  const rf = useReactFlow();
  const searchRef = useRef<HTMLInputElement>(null);

  const graphRef = useRef<ReturnType<typeof layoutGraph> | null>(null);
  const selectedRef = useRef<string | null>(null);

  /** Frame a node with its neighbors. The timeout lets React Flow measure new nodes and a
   *  canvas narrowed by the side panel (it watches its size with a ResizeObserver). */
  const focus = useCallback(
    (id: string) => {
      setTimeout(() => {
        const g = graphRef.current;
        const ids = g && g.nodes.some((n) => n.id === id) ? [...neighborhood(g, id)] : [id];
        void rf.fitView({ nodes: ids.map((n) => ({ id: n })), duration: 300, padding: 0.3, maxZoom: 1.1 });
      }, 80);
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
  const near = useMemo(
    () => (laidOut && selectedId && laidOut.nodes.some((n) => n.id === selectedId) ? neighborhood(laidOut, selectedId) : null),
    [laidOut, selectedId],
  );

  graphRef.current = laidOut;
  selectedRef.current = selectedId;

  // when the graph (or the filter) changes, keep the selection in view, else show everything
  useEffect(() => {
    if (!laidOut || !laidOut.nodes.length) return;
    const sel = selectedRef.current;
    if (sel && laidOut.nodes.some((n) => n.id === sel)) {
      focus(sel);
      return;
    }
    const t = setTimeout(() => void rf.fitView({ duration: 200, padding: 0.15, maxZoom: 1.1 }), 100); // after measuring
    return () => clearTimeout(t);
  }, [laidOut, rf, focus]);

  // worst diagnostic severity per node, drawn as a marker on the card
  const problemOf = useMemo(() => {
    const out = new Map<string, "error" | "warning">();
    for (const d of project?.diagnostics ?? []) {
      if (!d.node_id || d.severity === "info") continue;
      if (d.severity === "error" || !out.has(d.node_id)) out.set(d.node_id, d.severity);
    }
    return out;
  }, [project]);

  const nodes = useMemo<RFNode[]>(
    () =>
      (laidOut?.nodes ?? []).map((n) => {
        const dim = searching ? !matches.has(n.id) : near !== null && !near.has(n.id);
        return {
          ...n,
          selected: n.id === selectedId,
          // groups sit behind their children
          zIndex: n.type === "graph" ? 0 : 1,
          className: `kind-${n.type}`,
          data: { ...n.data, match: matches.has(n.id), dim, problem: problemOf.get(n.id) ?? null },
        };
      }),
    [laidOut, selectedId, matches, searching, near, problemOf],
  );

  const edges = useMemo(
    () =>
      (laidOut?.edges ?? []).map((e) => {
        const touched = selectedId !== null && (e.source === selectedId || e.target === selectedId);
        const faded = (selectedId !== null && !touched) || (searching && !(matches.has(e.source) && matches.has(e.target)));
        return {
          ...e,
          markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
          className: `${e.className}${touched ? " touched" : ""}${faded ? " faded" : ""}`,
          ariaLabel: e.label ?? e.data.ir.kind,
        };
      }),
    [laidOut, selectedId, searching, matches],
  );

  const select = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      transport.post({ type: "selectionChanged", nodeId: id });
    },
    [transport],
  );

  // "/" focuses the search, Esc clears the search and then the selection
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (e.key === "/" && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (e.key === "Escape") {
        if (query) setQuery("");
        else if (selectedId) select(null);
        else if (problemsOpen) setProblemsOpen(false);
        if (typing) (e.target as HTMLElement).blur();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [query, selectedId, problemsOpen, select]);

  const selectedNode = project?.nodes.find((n) => n.id === selectedId) ?? null;
  const diagnostics = project?.diagnostics ?? [];
  const errors = diagnostics.filter((d) => d.severity === "error").length;
  const warnings = diagnostics.length - errors;

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
  const counts = project ? kindCounts(project) : new Map<Kind, number>();
  const empty = project !== null && project.nodes.length === 0;
  const sideOpen = selectedNode !== null || problemsOpen;

  return (
    <div className="viewer">
      <header className="topbar">
        <div className="brand" title={project?.root ?? undefined}>
          <span className="brand-mark" aria-hidden="true">
            <Icon name="graph" size={15} />
          </span>
          <span className="brand-name">{result ? titleOf(result) : "agentsdiagram"}</span>
        </div>
        <label className="search">
          <Icon name="search" size={14} />
          <input
            ref={searchRef}
            type="search"
            placeholder="Search nodes"
            aria-label="Search nodes by name"
            value={query}
            onChange={(e) => onSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && laidOut) {
                const ids = searchNodes(laidOut.nodes, query);
                if (ids.length) {
                  const next = ids[(ids.indexOf(selectedId ?? "") + 1) % ids.length] ?? ids[0]!;
                  select(next);
                  focus(next);
                }
              }
            }}
          />
          {searching ? (
            <span className="count" aria-live="polite">
              {matches.size} {matches.size === 1 ? "match" : "matches"}
            </span>
          ) : (
            <kbd aria-hidden="true">/</kbd>
          )}
        </label>
        <span className="spacer" />
        {diagnostics.length > 0 && (
          <button
            className={`tbtn problems${problemsOpen ? " on" : ""}`}
            aria-pressed={problemsOpen}
            onClick={() => setProblemsOpen((o) => !o)}
            title="Show problems found by the analysis"
          >
            <Icon name="problems" size={14} />
            <span className="label-long">Problems</span>
            {errors > 0 && <span className="pcount err">{errors}</span>}
            {warnings > 0 && <span className="pcount warn">{warnings}</span>}
          </button>
        )}
        {transport.canCopyMermaid && (
          <button className="tbtn" onClick={copyMermaid} title="Copy the diagram as Mermaid" aria-label={copied ? "Copied" : "Copy Mermaid"}>
            <Icon name={copied ? "check" : "copy"} size={14} />
            <span className="label-long">{copied ? "Copied" : "Copy Mermaid"}</span>
          </button>
        )}
        {!theme.hosted && (
          <button
            className="tbtn icon"
            onClick={theme.toggle}
            aria-label={theme.mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme.mode === "dark" ? "Light theme" : "Dark theme"}
          >
            <Icon name={theme.mode === "dark" ? "sun" : "moon"} size={15} />
          </button>
        )}
      </header>
      {kinds.length > 0 && (
        <fieldset className="legend">
          <legend className="sr-only">Show or hide node kinds</legend>
          {kinds.map((k) => (
            <label key={k} className={`chip kind-${k}${hidden.has(k) ? " off" : ""}`} title={hidden.has(k) ? `Show ${KIND_LABELS[k]}` : `Hide ${KIND_LABELS[k]}`}>
              <input type="checkbox" checked={!hidden.has(k)} onChange={() => toggleKind(k)} />
              <span className="swatch" aria-hidden="true">
                <Icon name={k} size={12} />
              </span>
              {KIND_LABELS[k]}
              <span className="n">{counts.get(k) ?? 0}</span>
            </label>
          ))}
        </fieldset>
      )}
      <div className="main">
        <div className="canvas" aria-label="Agents diagram">
          {status.state !== "ready" && !project && (
            <div className={`overlay ${status.state}`} role="status">
              {status.state === "error" ? (
                <>
                  <strong>The analysis failed</strong>
                  <span>{status.message ?? "Unknown error"}</span>
                </>
              ) : (
                <>
                  <span className="spinner" aria-hidden="true" />
                  <span>{status.message ?? "Reading your agents…"}</span>
                </>
              )}
            </div>
          )}
          {status.state === "error" && project && (
            <div className="banner" role="alert">
              Showing the last good diagram. {status.message ?? ""}
            </div>
          )}
          {empty && (
            <div className="overlay" role="status">
              <strong>No agents here yet</strong>
              <span>agentsdiagram looks for PydanticAI and smolagents agents in the Python files of this folder.</span>
            </div>
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            colorMode={theme.mode}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            onNodeClick={(_, n: ADNode | RFNode) => {
              select(n.id);
              focus(n.id);
            }}
            onPaneClick={() => select(null)}
            minZoom={0.1}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={18} size={1.2} />
            <Controls showInteractive={false} position="bottom-left" />
            {(laidOut?.nodes.length ?? 0) > 12 && (
              <MiniMap pannable zoomable position="bottom-right" style={{ width: 168, height: 110 }} nodeClassName={(n) => `kind-${n.type}`} nodeBorderRadius={4} />
            )}
          </ReactFlow>
        </div>
        {sideOpen && (
          <aside className="side">
            {selectedNode && (
              <Detail
                node={selectedNode}
                diagnostics={diagnostics.filter((d) => d.node_id === selectedNode.id)}
                onReveal={() => selectedNode.source && transport.post({ type: "reveal", nodeId: selectedNode.id, source: selectedNode.source })}
                onClose={() => select(null)}
              />
            )}
            {problemsOpen && (
              <section className="panel" aria-label="Problems">
                <header className="panel-head">
                  <div className="panel-title">
                    <h2>Problems</h2>
                    <p>
                      {diagnostics.length} found by the analysis. Click one to see it in the diagram or in the code.
                    </p>
                  </div>
                  <button className="icon-btn" onClick={() => setProblemsOpen(false)} aria-label="Close problems">
                    <Icon name="close" />
                  </button>
                </header>
                <ul className="diag-list">
                  {diagnostics.map((d, i) => (
                    <li key={i} className={`sev-${d.severity}`}>
                      <button className="diag-btn" onClick={() => onDiagnostic(d)}>
                        <span className="diag-msg">{d.message}</span>
                        <span className="diag-meta">
                          <code className="diag-code">{d.code}</code>
                          {d.ref && (
                            <span className="loc">
                              {d.ref.file}:{d.ref.range.start.line}
                            </span>
                          )}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

export function App({ transport }: { transport: ViewerTransport | null }) {
  if (!transport) {
    return (
      <div className="overlay error" role="alert">
        <strong>Nothing to show</strong>
        <span>This page was opened without a diagram. Create one with `agentsdiagram scan . -f html`.</span>
      </div>
    );
  }
  return (
    <ReactFlowProvider>
      <Viewer transport={transport} />
    </ReactFlowProvider>
  );
}
