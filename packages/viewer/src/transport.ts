// Transports: how the viewer talks to its host. Chosen once at startup (see main.tsx).
import type { GraphResult, HostMessage, Project, Transport, ViewerMessage } from "@agentsdiagram/protocol";

export interface ViewerTransport extends Transport {
  /** Whether a "Copy Mermaid" action can be served by this host. */
  readonly canCopyMermaid: boolean;
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
  return { protocolVersion: "1", version: 0, scope: { kind: "workspace" }, project: d as Project };
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
  if (json) return staticTransport(JSON.parse(json), scriptText("agentsdiagram-mermaid"));
  if (import.meta.env.DEV) {
    const sample = (await import("../../protocol/fixtures/sample.json")).default;
    return staticTransport(sample, null);
  }
  return null;
}
