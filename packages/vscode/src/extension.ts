import * as vscode from "vscode";
import { LanguageClient, type LanguageClientOptions, type ServerOptions, TransportKind } from "vscode-languageclient/node";
import type { EditParams } from "@agentsdiagram/protocol/src/ir";
import type { EditResponse, GraphParams, GraphResult, Scope } from "@agentsdiagram/protocol/src/messages";
import { PROTOCOL_VERSION } from "@agentsdiagram/protocol/src/messages";
import { DiagramPanel } from "./panel";
import { resolveServerCommand, UV_INSTALL_URL } from "./server";

let client: LanguageClient | undefined;
let panel: DiagramPanel;
let output: vscode.LogOutputChannel;
let version = "0.0.0";
let starting: Promise<void> | undefined;

const SETTINGS_QUERY = "@ext:alex-roc.agentsdiagram";

async function startClient(): Promise<void> {
  const cmd = resolveServerCommand(version);
  if (!cmd) {
    panel.setStatus("error", "uv not found");
    const pick = await vscode.window.showErrorMessage(
      "Agents Diagram needs uv (to run the analyzer) or a custom command in `agentsdiagram.server.command`.",
      "Install uv",
      "Open settings",
    );
    if (pick === "Install uv") void vscode.env.openExternal(vscode.Uri.parse(UV_INSTALL_URL));
    else if (pick === "Open settings") void vscode.commands.executeCommand("workbench.action.openSettings", SETTINGS_QUERY);
    return;
  }
  if (!vscode.workspace.isTrusted && vscode.workspace.getConfiguration("agentsdiagram.server").get<string[]>("command", []).length > 0) {
    // restrictedConfigurations makes the value inspect as default in untrusted workspaces, so this is defensive.
    return;
  }
  output.info(`Starting server: ${cmd.command} ${cmd.args.join(" ")}`);
  panel.setStatus("starting");

  const config = vscode.workspace.getConfiguration("agentsdiagram");
  const serverOptions: ServerOptions = { command: cmd.command, args: cmd.args, transport: TransportKind.stdio };
  const clientOptions: LanguageClientOptions = {
    documentSelector: [
      { scheme: "file", language: "python" },
      { scheme: "file", pattern: "**/*.agent.{yaml,yml,json}" },
    ],
    outputChannel: output,
    initializationOptions: {
      include: config.get<string[]>("include", []),
      exclude: config.get<string[]>("exclude", []),
      codeLens: { enabled: config.get<boolean>("codeLens.enabled", true) },
    },
  };
  const next = new LanguageClient("agentsdiagram", "Agents Diagram", serverOptions, clientOptions);
  next.onNotification("agentsdiagram/graphChanged", () => panel.notifyChanged());
  client = next;

  try {
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Agents Diagram: starting analyzer (first run downloads it)" },
      () => next.start(),
    );
  } catch (err) {
    output.info(`Server failed to start: ${err}`);
    panel.setStatus("error", `Server failed to start: ${err}`);
    void vscode.window
      .showErrorMessage("Agents Diagram: the language server failed to start.", "Show output")
      .then((pick) => pick && output.show());
    client = undefined;
    return;
  }

  const theirs = (next.initializeResult?.capabilities.experimental as { agentsdiagram?: { protocolVersion?: string } } | undefined)
    ?.agentsdiagram?.protocolVersion;
  if (theirs !== PROTOCOL_VERSION) {
    const msg = `Agents Diagram: server protocol ${theirs ?? "unknown"} does not match the extension (${PROTOCOL_VERSION}). Update agentsdiagram or the extension.`;
    output.info(msg);
    panel.setStatus("error", msg);
    void vscode.window.showWarningMessage(msg);
  }
  panel.setBackend({
    graph: (params: GraphParams) => next.sendRequest<GraphResult>("agentsdiagram/graph", params),
    mermaid: (params: GraphParams) => next.sendRequest<{ text: string }>("agentsdiagram/mermaid", params),
    edit: (params: EditParams) => next.sendRequest<EditResponse>("agentsdiagram/edit", params),
    toWorkspaceEdit: async (edit: unknown) => {
      type LspEdit = Parameters<typeof next.protocol2CodeConverter.asWorkspaceEdit>[0];
      return (await next.protocol2CodeConverter.asWorkspaceEdit(edit as LspEdit)) ?? new vscode.WorkspaceEdit();
    },
  });
}

function ensureStarted(): Promise<void> {
  starting ??= startClient();
  return starting;
}

async function stopClient(): Promise<void> {
  // a start still in flight would otherwise leave a second client (and duplicate code lenses) behind
  const pending = starting;
  starting = undefined;
  if (pending) await pending.catch(() => undefined);
  panel.setBackend(undefined);
  const old = client;
  client = undefined;
  if (old) await old.stop().catch((err) => output.info(`stop failed: ${err}`));
}

function activeFileScope(): Scope | undefined {
  const doc = vscode.window.activeTextEditor?.document;
  if (!doc || doc.uri.scheme !== "file") return undefined;
  return { kind: "file", uri: doc.uri.toString() };
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  version = context.extension.packageJSON.version as string;
  output = vscode.window.createOutputChannel("Agents Diagram", { log: true });
  panel = new DiagramPanel(context.extensionUri, output);
  context.subscriptions.push(output, panel);

  const open = (scope: Scope, select?: string) => {
    panel.show(scope, select);
    void ensureStarted();
  };

  context.subscriptions.push(
    vscode.commands.registerCommand("agentsdiagram.showWorkspace", () => open({ kind: "workspace" })),
    vscode.commands.registerCommand("agentsdiagram.showFile", () => {
      const scope = activeFileScope();
      if (!scope) return void vscode.window.showInformationMessage("Agents Diagram: open a file first.");
      open(scope);
    }),
    vscode.commands.registerCommand("agentsdiagram.showNode", (nodeId: string) => open(panel.currentScope, nodeId)),
    vscode.commands.registerCommand("agentsdiagram.exportMermaid", async () => {
      await ensureStarted();
      if (!client) return;
      try {
        const scope = activeFileScope() && vscode.window.activeTextEditor?.document.languageId === "python" ? activeFileScope()! : panel.currentScope;
        const { text } = await client.sendRequest<{ text: string }>("agentsdiagram/mermaid", { scope });
        const doc = await vscode.workspace.openTextDocument({ language: "markdown", content: "```mermaid\n" + text.trimEnd() + "\n```\n" });
        await vscode.window.showTextDocument(doc);
      } catch (err) {
        void vscode.window.showErrorMessage(`Agents Diagram: ${err}`);
      }
    }),
    vscode.commands.registerCommand("agentsdiagram.restartServer", async () => {
      await stopClient();
      await ensureStarted();
    }),
    vscode.commands.registerCommand("agentsdiagram.showOutput", () => output.show()),
    // the same edits as the diagram, for scripts, other extensions and tests: (EditParams) -> EditResult
    vscode.commands.registerCommand("agentsdiagram.edit", async (params: EditParams) => {
      await ensureStarted();
      return panel.edit(params);
    }),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("agentsdiagram") && client) {
        void vscode.window
          .showInformationMessage("Agents Diagram: settings changed, restart the server to apply them.", "Restart")
          .then((pick) => pick && vscode.commands.executeCommand("agentsdiagram.restartServer"));
      }
    }),
    { dispose: () => void stopClient() },
  );

  // Python is open (activation event): bring the analyzer up so diagnostics and code lenses appear.
  void ensureStarted();
}

export async function deactivate(): Promise<void> {
  await stopClient();
}
