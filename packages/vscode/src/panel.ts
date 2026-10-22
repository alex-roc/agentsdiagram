import * as path from "node:path";
import * as vscode from "vscode";
import type { HostMessage, GraphParams, GraphResult, Scope, ViewerMessage } from "@agentsdiagram/protocol/src/messages";
import { innermostNode, irRangeToVsCode, utf16ToCodePoints } from "./positions";

/** The slice of the language client the panel needs; keeps the panel testable and restart-safe. */
export interface GraphBackend {
  graph(params: GraphParams): Promise<GraphResult>;
  mermaid(params: GraphParams): Promise<{ text: string }>;
}

const DEBOUNCE_MS = 250;

export class DiagramPanel implements vscode.Disposable {
  private panel: vscode.WebviewPanel | undefined;
  private backend: GraphBackend | undefined;
  private scope: Scope = { kind: "workspace" };
  private lastGraph: GraphResult | undefined;
  private viewerReady = false;
  private pendingSelect: string | null | undefined;
  private status: Extract<HostMessage, { type: "status" }> = { type: "status", state: "starting" };
  private refreshTimer: NodeJS.Timeout | undefined;
  private cursorTimer: NodeJS.Timeout | undefined;
  private readonly disposables: vscode.Disposable[] = [];

  constructor(private readonly extensionUri: vscode.Uri, private readonly output: vscode.LogOutputChannel) {
    this.disposables.push(
      vscode.window.onDidChangeTextEditorSelection((e) => this.onSelection(e)),
    );
  }

  get currentScope(): Scope {
    return this.scope;
  }

  setBackend(backend: GraphBackend | undefined): void {
    this.backend = backend;
    if (backend) void this.refresh();
  }

  setStatus(state: "starting" | "ready" | "error", message?: string): void {
    this.status = { type: "status", state, message };
    this.post(this.status);
  }

  /** Opens or focuses the panel; changing the scope refetches the graph. */
  show(scope: Scope, select?: string): void {
    const changed = JSON.stringify(scope) !== JSON.stringify(this.scope);
    this.scope = scope;
    if (select !== undefined) this.pendingSelect = select;
    if (this.panel) {
      this.panel.reveal(undefined, true);
    } else {
      this.createPanel();
    }
    if (changed) void this.refresh();
    else if (select !== undefined) this.flushSelect();
  }

  /** Called on `agentsdiagram/graphChanged`. */
  notifyChanged(): void {
    if (!this.panel) return;
    clearTimeout(this.refreshTimer);
    this.refreshTimer = setTimeout(() => void this.refresh(), DEBOUNCE_MS);
  }

  async refresh(): Promise<void> {
    if (!this.panel || !this.viewerReady || !this.backend) return;
    try {
      const result = await this.backend.graph({ scope: this.scope });
      this.lastGraph = result;
      this.post({ type: "graph", result });
      this.setStatus("ready");
      this.flushSelect();
    } catch (err) {
      this.output.info(`agentsdiagram/graph failed: ${err}`);
      this.setStatus("error", String(err instanceof Error ? err.message : err));
    }
  }

  private flushSelect(): void {
    if (this.pendingSelect === undefined) return;
    this.post({ type: "select", nodeId: this.pendingSelect });
    this.pendingSelect = undefined;
  }

  private post(message: HostMessage): void {
    if (this.panel && this.viewerReady) void this.panel.webview.postMessage(message);
  }

  private createPanel(): void {
    const media = vscode.Uri.joinPath(this.extensionUri, "media");
    const panel = vscode.window.createWebviewPanel(
      "agentsdiagram.diagram",
      "Agents Diagram",
      { viewColumn: vscode.ViewColumn.Beside, preserveFocus: true },
      { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [media] },
    );
    this.panel = panel;
    this.viewerReady = false;
    panel.iconPath = vscode.Uri.joinPath(this.extensionUri, "resources", "icon.png");
    panel.webview.html = this.html(panel.webview, media);
    panel.webview.onDidReceiveMessage((m: ViewerMessage) => this.onViewerMessage(m), undefined, this.disposables);
    panel.onDidDispose(() => {
      this.panel = undefined;
      this.viewerReady = false;
    });
  }

  private html(webview: vscode.Webview, media: vscode.Uri): string {
    const nonce = Array.from({ length: 32 }, () => Math.random().toString(36)[2]).join("");
    const js = webview.asWebviewUri(vscode.Uri.joinPath(media, "viewer.js"));
    const css = webview.asWebviewUri(vscode.Uri.joinPath(media, "viewer.css"));
    const csp = [
      "default-src 'none'",
      `style-src ${webview.cspSource} 'unsafe-inline'`, // React Flow positions nodes with inline styles
      `script-src 'nonce-${nonce}'`,
      `font-src ${webview.cspSource}`,
      `img-src ${webview.cspSource} data:`,
    ].join("; ");
    return `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="${css}">
<title>Agents Diagram</title>
</head><body>
<div id="root"></div>
<script nonce="${nonce}" src="${js}"></script>
</body></html>`;
  }

  private onViewerMessage(message: ViewerMessage): void {
    switch (message.type) {
      case "ready":
        this.viewerReady = true;
        this.post(this.status);
        if (this.lastGraph) this.post({ type: "graph", result: this.lastGraph });
        void this.refresh();
        break;
      case "reveal":
        void this.reveal(message.source);
        break;
      case "copyMermaid":
        void this.copyMermaid();
        break;
      case "selectionChanged":
        break;
    }
  }

  /** Uses only `source`: diagnostics reveal with an empty nodeId. */
  private async reveal(source: NonNullable<Extract<ViewerMessage, { type: "reveal" }>["source"]>): Promise<void> {
    const root = this.lastGraph?.project.root;
    if (!root) return;
    try {
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(root, source.file)));
      const range = irRangeToVsCode(doc, source.name_range ?? source.range);
      const editor = await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.One, selection: range });
      editor.revealRange(range, vscode.TextEditorRevealType.InCenterIfOutsideViewport);
    } catch (err) {
      void vscode.window.showWarningMessage(`Agents Diagram: cannot open ${source.file}: ${err}`);
    }
  }

  private async copyMermaid(): Promise<void> {
    if (!this.backend) return;
    try {
      const { text } = await this.backend.mermaid({ scope: this.scope });
      await vscode.env.clipboard.writeText(text);
      void vscode.window.showInformationMessage("Agents Diagram: Mermaid copied to the clipboard.");
    } catch (err) {
      void vscode.window.showErrorMessage(`Agents Diagram: ${err}`);
    }
  }

  /** Editor -> diagram: select the innermost node under the cursor. */
  private onSelection(e: vscode.TextEditorSelectionChangeEvent): void {
    const doc = e.textEditor.document;
    if (!this.panel || !this.lastGraph || doc.languageId !== "python" || doc.uri.scheme !== "file") return;
    clearTimeout(this.cursorTimer);
    this.cursorTimer = setTimeout(() => {
      const graph = this.lastGraph;
      if (!graph) return;
      const rel = path.relative(graph.project.root, doc.uri.fsPath).split(path.sep).join("/");
      const cursor = e.selections[0].active;
      const at = { line: cursor.line + 1, column: utf16ToCodePoints(doc.lineAt(cursor.line).text, cursor.character) };
      const node = innermostNode(graph.project.nodes, rel, at);
      this.post({ type: "select", nodeId: node?.id ?? null });
    }, DEBOUNCE_MS);
  }

  dispose(): void {
    clearTimeout(this.refreshTimer);
    clearTimeout(this.cursorTimer);
    this.panel?.dispose();
    this.disposables.forEach((d) => d.dispose());
  }
}
