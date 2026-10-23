/**
 * Messages between the viewer (webview / standalone HTML) and its host
 * (VS Code extension host, or the embedded data of `agentsdiagram scan --format html`).
 *
 * The extension talks to the Python language server with these custom LSP methods:
 *   request      agentsdiagram/graph    GraphParams   -> GraphResult
 *   request      agentsdiagram/mermaid  GraphParams   -> { text: string }
 *   request      agentsdiagram/edit     EditParams    -> EditResponse (a WorkspaceEdit the client applies)
 *   notification agentsdiagram/graphChanged  { version: number }   (server -> client, debounced)
 * Standard LSP is used for diagnostics (publishDiagnostics) and code lenses.
 */
import type { EditParams, EditResult, Project, SourceRef } from "./ir";

export const PROTOCOL_VERSION = "2";

/** One plan/edit operation (add_agent, add_tool, connect, remove…). */
export type EditRequest = EditParams["request"];

/** `agentsdiagram/edit` over LSP: the result plus the LSP `WorkspaceEdit` to apply (null on failure). */
export interface EditResponse extends EditResult {
  edit?: unknown;
}

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
  | { type: "status"; state: "starting" | "ready" | "error"; message?: string }
  | { type: "editResult"; id: number; result: EditResult };

/** viewer -> host */
export type ViewerMessage =
  | { type: "ready" }
  | { type: "reveal"; nodeId: string; source: SourceRef }
  | { type: "copyMermaid" }
  | { type: "selectionChanged"; nodeId: string | null }
  | { type: "edit"; id: number; params: EditParams };

/** How the viewer talks to whatever hosts it. */
export interface Transport {
  post(message: ViewerMessage): void;
  subscribe(listener: (message: HostMessage) => void): () => void;
}
