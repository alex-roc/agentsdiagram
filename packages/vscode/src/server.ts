import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as vscode from "vscode";

export interface ServerCommand {
  command: string;
  args: string[];
}

export const UV_INSTALL_URL = "https://docs.astral.sh/uv/getting-started/installation/";

function isExecutable(file: string): boolean {
  try {
    fs.accessSync(file, fs.constants.X_OK);
    return fs.statSync(file).isFile();
  } catch {
    return false;
  }
}

/** GUI apps do not inherit the shell PATH, so look in the usual uv install locations too. */
export function findUvx(configured: string | undefined): string | undefined {
  if (configured) return isExecutable(configured) ? configured : undefined;
  const win = process.platform === "win32";
  const exe = win ? "uvx.exe" : "uvx";
  const home = os.homedir();
  const dirs = (process.env.PATH ?? "").split(path.delimiter).filter(Boolean);
  dirs.push(path.join(home, ".local", "bin"), path.join(home, ".cargo", "bin"));
  if (win) {
    dirs.push(path.join(process.env.USERPROFILE ?? home, ".local", "bin"));
    if (process.env.LOCALAPPDATA) dirs.push(path.join(process.env.LOCALAPPDATA, "uv"));
  } else {
    dirs.push("/opt/homebrew/bin", "/usr/local/bin");
  }
  for (const dir of dirs) {
    const candidate = path.join(dir, exe);
    if (isExecutable(candidate)) return candidate;
  }
  return undefined;
}

/** `server.command` as is, else `uvx --from agentsdiagram[lsp]==<version> agentsdiagram lsp`; undefined if neither is possible. */
export function resolveServerCommand(version: string): ServerCommand | undefined {
  const config = vscode.workspace.getConfiguration("agentsdiagram.server");
  const custom = config.get<string[]>("command", []);
  if (custom.length > 0) return { command: custom[0], args: custom.slice(1) };
  const uvx = findUvx(config.get<string>("uvPath") || undefined);
  if (!uvx) return undefined;
  return { command: uvx, args: ["--from", `agentsdiagram[lsp]==${version}`, "agentsdiagram", "lsp"] };
}
