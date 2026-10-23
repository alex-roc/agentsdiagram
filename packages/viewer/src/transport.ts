// Transports: how the viewer talks to its host. Chosen once at startup (see main.tsx).
import type { EditResult, GraphResult, HostMessage, Project, Transport, ViewerMessage } from "@agentsdiagram/protocol";

export interface ViewerTransport extends Transport {
  /** Whether a "Copy Mermaid" action can be served by this host. */
  readonly canCopyMermaid: boolean;
  /** Whether the host can change the code (VS Code, `agentsdiagram serve`); a static page cannot. */
  readonly canEdit: boolean;
}

interface VsCodeApi {
  postMessage(message: unknown): void;
}
declare function acquireVsCodeApi(): VsCodeApi;

export function hasVsCodeApi(): boolean {
  return typeof (globalThis as { acquireVsCodeApi?: unknown }).acquireVsCodeApi === "function";
}

export function vscodeTransport(): ViewerTransport {
  const api = acquireVsCodeApi();
  return {
    canCopyMermaid: true,
    canEdit: true,
    post: (message) => api.postMessage(message),
    subscribe(listener) {
      const handler = (event: MessageEvent) => {
        if (event.data && typeof event.data.type === "string") listener(event.data as HostMessage);
      };
      window.addEventListener("message", handler);
      api.postMessage({ type: "ready" } satisfies ViewerMessage);
      return () => window.removeEventListener("message", handler);
    },
  };
}

/** Accepts a GraphResult or a bare Project (what `agentsdiagram scan` emits). */
export function toGraphResult(data: unknown): GraphResult {
  const d = data as Partial<GraphResult> & Partial<Project>;
  if (d.project) return d as GraphResult;
  return { protocolVersion: "2", version: 0, scope: { kind: "workspace" }, project: d as Project };
}

export function revealUrl(root: string, file: string, line: number, column: number): string {
  const base = root.replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
  return `vscode://file/${base}/${file}:${line}:${column + 1}`;
}

/** Static data: graph embedded in the page (or loaded in dev); reveal opens a vscode:// link. */
export function staticTransport(data: unknown, mermaid: string | null): ViewerTransport {
  const result = toGraphResult(data);
  return {
    canCopyMermaid: mermaid !== null,
    canEdit: false,
    post(message) {
      if (message.type === "reveal") {
        const { file, range } = message.source;
        window.location.href = revealUrl(result.project.root, file, range.start.line, range.start.column);
      } else if (message.type === "copyMermaid" && mermaid !== null) {
        copyText(mermaid);
      }
    },
    subscribe(listener) {
      const t = setTimeout(() => listener({ type: "graph", result }), 0);
      return () => clearTimeout(t);
    },
  };
}

export interface LiveConfig {
  token: string | null;
  editable: boolean;
}

/** `agentsdiagram serve`: redraw on server-sent events, edits go to POST /api/edit. */
export function liveTransport(data: unknown, config: LiveConfig, base = ""): ViewerTransport {
  let root = toGraphResult(data).project.root;
  const listeners = new Set<(m: HostMessage) => void>();
  const emit = (m: HostMessage) => listeners.forEach((l) => l(m));
  let events: EventSource | null = null;

  const fetchGraph = async () => {
    const res = await fetch(`${base}/api/graph`, { cache: "no-store" });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const result = (await res.json()) as GraphResult;
    root = result.project.root;
    emit({ type: "graph", result });
  };

  const connect = () => {
    events = new EventSource(`${base}/api/events`);
    events.addEventListener("graph", () => void fetchGraph().catch(() => undefined));
    events.onerror = () => emit({ type: "status", state: "error", message: "Lost the connection to agentsdiagram serve; retrying." });
    events.onopen = () => emit({ type: "status", state: "ready" });
  };

  return {
    canCopyMermaid: true,
    canEdit: config.editable && config.token !== null,
    post(message) {
      if (message.type === "reveal") {
        const { file, range } = message.source;
        window.location.href = revealUrl(root, file, range.start.line, range.start.column);
      } else if (message.type === "copyMermaid") {
        void fetch(`${base}/api/mermaid`).then((r) => r.text()).then(copyText);
      } else if (message.type === "edit") {
        const fail = (msg: string): EditResult => ({ ok: false, message: msg, files: [], focus: null });
        void fetch(`${base}/api/edit`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Agentsdiagram-Token": config.token ?? "" },
          body: JSON.stringify(message.params),
        })
          .then(async (r) => ((await r.json()) as EditResult) ?? fail(`${r.status}`))
          .catch((err: unknown) => fail(`The server did not answer: ${String(err)}`))
          .then((result) => emit({ type: "editResult", id: message.id, result }));
      }
    },
    subscribe(listener) {
      listeners.add(listener);
      const t = setTimeout(() => listener({ type: "graph", result: toGraphResult(data) }), 0);
      if (!events) connect();
      return () => {
        clearTimeout(t);
        listeners.delete(listener);
        if (!listeners.size) {
          events?.close();
          events = null;
        }
      };
    },
  };
}

/** Clipboard API when allowed (secure contexts), else the old textarea + execCommand route. */
function copyText(text: string): void {
  const fallback = () => {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  };
  if (navigator.clipboard) navigator.clipboard.writeText(text).catch(fallback);
  else fallback();
}

function scriptText(id: string): string | null {
  return document.getElementById(id)?.textContent ?? null;
}

/** Picks the transport for the current environment; null if there is nothing to show. */
export async function pickTransport(): Promise<ViewerTransport | null> {
  if (hasVsCodeApi()) return vscodeTransport();
  const json = scriptText("agentsdiagram-data");
  const live = scriptText("agentsdiagram-live");
  if (json && live) return liveTransport(JSON.parse(json), JSON.parse(live) as LiveConfig);
  if (json) return staticTransport(JSON.parse(json), scriptText("agentsdiagram-mermaid"));
  if (import.meta.env.DEV) {
    const sample = (await import("../../protocol/fixtures/sample.json")).default;
    return staticTransport(sample, null);
  }
  return null;
}
