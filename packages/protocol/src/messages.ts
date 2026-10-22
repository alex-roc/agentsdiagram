/**
 * Messages between the viewer (webview / standalone HTML) and its host
 * (VS Code extension host, or the embedded data of `agentsdiagram scan --format html`).
 *
 * The extension talks to the Python language server with these custom LSP methods:
 *   request      agentsdiagram/graph    GraphParams   -> GraphResult
 *   request      agentsdiagram/mermaid  GraphParams   -> { text: string }
 *   notification agentsdiagram/graphChanged  { version: number }   (server -> client, debounced)
 * Standard LSP is used for diagnostics (publishDiagnostics) and code lenses.
 */
import type { Project, SourceRef } from "./ir";

export const PROTOCOL_VERSION = "1";

export type Scope = { kind: "workspace" } | { kind: "file"; uri: string };

export interface GraphParams {
  scope: Scope;
}

export interface GraphResult {
  protocolVersion: string;
  version: number;
  scope: Scope;
  project: Project;
}

/** host -> viewer */
export type HostMessage =
  | { type: "graph"; result: GraphResult }
  | { type: "select"; nodeId: string | null }
  | { type: "status"; state: "starting" | "ready" | "error"; message?: string };

/** viewer -> host */
export type ViewerMessage =
  | { type: "ready" }
  | { type: "reveal"; nodeId: string; source: SourceRef }
  | { type: "copyMermaid" }
  | { type: "selectionChanged"; nodeId: string | null };

/** How the viewer talks to whatever hosts it. */
export interface Transport {
  post(message: ViewerMessage): void;
  subscribe(listener: (message: HostMessage) => void): () => void;
}
