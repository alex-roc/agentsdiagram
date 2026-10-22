import * as assert from "node:assert";
import * as path from "node:path";
import * as vscode from "vscode";

// Bundled to dist/test/e2e.test.js, so the repo root is three levels up from packages/vscode/dist/test.
const REPO = path.resolve(__dirname, "../../../..");

async function waitFor<T>(probe: () => T | undefined, timeoutMs: number, what: string): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const value = probe();
    if (value !== undefined) return value;
    if (Date.now() > deadline) throw new Error(`timed out waiting for ${what}`);
    await new Promise((r) => setTimeout(r, 500));
  }
}

suite("Agents Diagram e2e (real server)", () => {
  test("diagnostics, workspace panel and mermaid export", async () => {
    const config = vscode.workspace.getConfiguration("agentsdiagram.server");
    await config.update("command", ["uv", "run", "--project", REPO, "agentsdiagram", "lsp"], vscode.ConfigurationTarget.Global);

    const ext = vscode.extensions.getExtension("alex-roc.agentsdiagram")!;
    await ext.activate();
    await vscode.commands.executeCommand("agentsdiagram.restartServer");

    const folder = vscode.workspace.workspaceFolders![0].uri;
    const uri = vscode.Uri.joinPath(folder, "smol", "managed_without_name.py");
    await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(uri));

    const codes = await waitFor(() => {
      const found = vscode.languages
        .getDiagnostics(uri)
        .filter((d) => d.source === "agentsdiagram")
        .map((d) => String(typeof d.code === "object" ? d.code.value : d.code));
      return found.includes("AD201") && found.includes("AD204") ? found : undefined;
    }, 60000, "AD201 and AD204 diagnostics");
    assert.ok(codes.length >= 2);

    await vscode.commands.executeCommand("agentsdiagram.showWorkspace");

    await vscode.commands.executeCommand("agentsdiagram.exportMermaid");
    const doc = vscode.window.activeTextEditor?.document;
    assert.ok(doc, "no document opened by exportMermaid");
    assert.strictEqual(doc.languageId, "markdown");
    assert.ok(doc.getText().includes("flowchart LR"), doc.getText());
  });
});
