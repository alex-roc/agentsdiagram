// Visual check of the diagram panel inside a real VS Code window (macOS only, not run in CI).
// `pnpm test:visual` opens examples/, drives the panel through its commands and saves a
// screenshot of each step to $AGENTSDIAGRAM_SHOTS (default: packages/vscode/.shots).
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import * as path from "node:path";
import * as vscode from "vscode";

const REPO = path.resolve(__dirname, "../../../..");
const SHOTS = process.env["AGENTSDIAGRAM_SHOTS"] ?? path.join(REPO, "packages/vscode/.shots");

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** A real mouse click in this test's window (x < 0 counts from the right edge). */
function click(x: number, y: number): string {
  const script = path.join(REPO, "packages/vscode/scripts/window_click.py");
  return execFileSync("uv", ["run", "-q", "--no-project", script, "Extension Development Host", String(x), String(y)]).toString();
}

/** Screenshot of this test's window only (other windows may cover it). */
function shot(name: string): void {
  mkdirSync(SHOTS, { recursive: true });
  const script = path.join(REPO, "packages/vscode/scripts/window_shot.py");
  execFileSync("uv", ["run", "-q", "--no-project", script, "Extension Development Host", path.join(SHOTS, `${name}.png`)]);
}

suite("Agents Diagram visual", () => {
  test("panel, selection sync and themes", async () => {
    const config = vscode.workspace.getConfiguration();
    await config.update("agentsdiagram.server.command", ["uv", "run", "--project", REPO, "agentsdiagram", "lsp"], vscode.ConfigurationTarget.Global);
    await config.update("workbench.colorTheme", "Default Light Modern", vscode.ConfigurationTarget.Global);

    await vscode.extensions.getExtension("alex-roc.agentsdiagram")!.activate();
    await vscode.commands.executeCommand("agentsdiagram.restartServer");

    const folder = vscode.workspace.workspaceFolders![0].uri;
    const agents = vscode.Uri.joinPath(folder, "support_desk", "agents.py");
    let editor = await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(agents));
    await vscode.commands.executeCommand("workbench.action.closeSidebar");
    await vscode.commands.executeCommand("workbench.action.closeAuxiliaryBar");
    await vscode.commands.executeCommand("notifications.clearAll");

    await vscode.commands.executeCommand("agentsdiagram.showWorkspace");
    await sleep(9000); // server start, analysis, first layout
    shot("1-workspace-light");

    // what a code lens does: show one node
    await vscode.commands.executeCommand("agentsdiagram.showNode", "pydantic_ai:agent:examples.support_desk.agents.triage");
    await sleep(1500);
    shot("2-show-node-triage");

    // diagram -> code: a real click on "Go to code" in the webview's detail panel
    const tools = vscode.Uri.joinPath(folder, "support_desk", "tools.py");
    await vscode.window.showTextDocument(await vscode.workspace.openTextDocument(tools), vscode.ViewColumn.One);
    await sleep(800);
    console.log(click(-172, 268));
    await sleep(1500);
    const active = vscode.window.activeTextEditor;
    const where = `${active?.document.uri.path}:${(active?.selection.start.line ?? -1) + 1}`;
    if (!where.endsWith("support_desk/agents.py:34")) throw new Error(`Go to code opened ${where}`);
    shot("2b-go-to-code");
    editor = active!;

    // code -> diagram: put the cursor on the `tech` agent
    const line = editor.document.getText().split("\n").findIndex((l) => l.startsWith("tech = Agent("));
    editor = await vscode.window.showTextDocument(editor.document, vscode.ViewColumn.One);
    editor.selection = new vscode.Selection(0, 0, 0, 0);
    await sleep(300);
    editor.selection = new vscode.Selection(line + 2, 4, line + 2, 4);
    await sleep(1500);
    shot("3-cursor-on-tech");

    // the server answers one code lens per agent (no duplicates from a second client)
    const lenses = await vscode.commands.executeCommand<vscode.CodeLens[]>("vscode.executeCodeLensProvider", agents);
    const titles = lenses.map((l) => l.command?.title ?? "");
    if (new Set(titles).size !== titles.length) throw new Error(`duplicate code lenses: ${titles.join(", ")}`);

    await config.update("workbench.colorTheme", "Default Dark Modern", vscode.ConfigurationTarget.Global);
    await sleep(1500);
    shot("4-dark");

    // live update: add a tool without saving
    await editor.edit((b) =>
      b.insert(new vscode.Position(editor.document.lineCount, 0), "\n\n@tech.tool_plain\ndef restart_service(name: str) -> str:\n    \"\"\"Restart a service.\"\"\"\n    return name\n"),
    );
    await sleep(3000);
    shot("5-live-edit");
    await vscode.commands.executeCommand("workbench.action.files.revert");
  });
});
