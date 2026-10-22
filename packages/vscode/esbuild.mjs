// Bundles the extension host (CJS) and the smoke tests, and copies the viewer build to media/.
import { build, context } from "esbuild";
import { cp, mkdir, access } from "node:fs/promises";

const watch = process.argv.includes("--watch");
const production = process.argv.includes("--production");

const common = {
  bundle: true,
  platform: "node",
  target: "node22",
  format: "cjs",
  external: ["vscode"],
  sourcemap: !production,
  minify: production,
  logLevel: "info",
};

const configs = [
  { ...common, entryPoints: ["src/extension.ts"], outfile: "dist/extension.js" },
  // Tests are never shipped (.vscodeignore), so they stay unminified.
  { ...common, minify: false, external: ["vscode", "mocha"], entryPoints: ["src/test/smoke.test.ts", "src/test/e2e.test.ts", "src/test/visual.test.ts"], outdir: "dist/test" },
];

async function copyViewer() {
  const dist = new URL("../viewer/dist/", import.meta.url);
  await mkdir("media", { recursive: true });
  for (const file of ["viewer.js", "viewer.css"]) {
    try {
      await access(new URL(file, dist));
      await cp(new URL(file, dist), `media/${file}`);
    } catch {
      console.warn(`warning: packages/viewer/dist/${file} not found (build the viewer first)`);
    }
  }
}

await copyViewer();
if (watch) {
  for (const config of configs) await (await context(config)).watch();
} else {
  await Promise.all(configs.map((config) => build(config)));
  if (production) await access("media/viewer.js"); // fail the package if the viewer is missing
}
