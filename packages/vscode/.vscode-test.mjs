import { defineConfig } from "@vscode/test-cli";
import { fileURLToPath } from "node:url";

const common = { version: "stable", launchArgs: ["--disable-extensions"] };

export default defineConfig([
  // Needs no Python server.
  { ...common, label: "smoke", files: "dist/test/smoke.test.js", mocha: { ui: "tdd", timeout: 30000 } },
  // Needs uv and the repo checkout (runs the real server from the repo).
  {
    ...common,
    label: "e2e",
    files: "dist/test/e2e.test.js",
    workspaceFolder: fileURLToPath(new URL("../../tests/fixtures", import.meta.url)),
    mocha: { ui: "tdd", timeout: 120000 },
  },
]);
