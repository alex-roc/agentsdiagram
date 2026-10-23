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

  test("plan an agent and a tool from the diagram's edit command", async () => {
    const folder = vscode.workspace.workspaceFolders![0].uri;
    const file = vscode.Uri.joinPath(folder, "smol", "_e2e_planned.py");
    type Result = { ok: boolean; message: string; files: string[]; focus: string | null };
    try {
      const planned = await vscode.commands.executeCommand<Result>("agentsdiagram.edit", {
        request: { op: "add_agent", framework: "smolagents", name: "scout", file: "smol/_e2e_planned.py" },
      });
      assert.ok(planned.ok, planned.message);
      assert.strictEqual(planned.focus, "smolagents:agent:smol._e2e_planned.scout");
      const doc = await vscode.workspace.openTextDocument(file);
      assert.ok(!doc.isDirty, "the new file is saved");
      assert.ok(doc.getText().includes("# agentsdiagram: planned\nscout = CodeAgent("), doc.getText());

      const tool = await vscode.commands.executeCommand<Result>("agentsdiagram.edit", {
        request: { op: "add_tool", agent: planned.focus, name: "lookup", params: "term: str" },
      });
      assert.ok(tool.ok, tool.message);
      assert.ok(doc.getText().includes("tools=[lookup]"), doc.getText());

      const refused = await vscode.commands.executeCommand<Result>("agentsdiagram.edit", {
        request: { op: "set_model", agent: planned.focus, model: "x" },
        expect: [{ file: "smol/_e2e_planned.py", sha256: "0".repeat(64) }],
      });
      assert.ok(!refused.ok && refused.message.includes("changed since"), refused.message);
    } finally {
      await vscode.commands.executeCommand("workbench.action.closeAllEditors");
      await vscode.workspace.fs.delete(file).then(undefined, () => undefined);
    }
  });
});
