import * as assert from "node:assert";
import * as vscode from "vscode";

const COMMANDS = [
  "agentsdiagram.showWorkspace",
  "agentsdiagram.showFile",
  "agentsdiagram.showNode",
  "agentsdiagram.exportMermaid",
  "agentsdiagram.restartServer",
  "agentsdiagram.showOutput",
];

suite("Agents Diagram smoke", () => {
  test("activates and registers its commands", async () => {
    const ext = vscode.extensions.getExtension("alex-roc.agentsdiagram");
    assert.ok(ext, "extension not found");
    await ext.activate();
    const all = await vscode.commands.getCommands(true);
    for (const id of COMMANDS) assert.ok(all.includes(id), `missing command ${id}`);
  });
});
