# @agentsdiagram/viewer

The agents graph viewer (React 19 + `@xyflow/react` 12.12 + dagre). One bundle
(`dist/viewer.js` + `dist/viewer.css`, IIFE, no hashes, no external assets) loaded by:

- the VS Code extension webview (`packages/vscode`, copied to `media/`);
- the self-contained HTML that `agentsdiagram scan -f html` generates (Python inlines both files).

`postbuild` copies the bundle to `src/agentsdiagram/_static/`.

## Architecture

- `src/model.ts`: pure IR → React Flow transform (kind filter, `graph` groups with their
  `graph_step`s, edge labels, search). No DOM or React; tested against `sample.json`.
- `src/layout.ts`: dagre. LR at the top level (connected components packed in rows), TB inside groups.
- `src/transport.ts`: `Transport` implementations (`@agentsdiagram/protocol`).
- `src/App.tsx`, `nodes.tsx`, `Detail.tsx`, `styles.css`: UI. Themed with `--vscode-*` variables and light/dark fallbacks.

## Transports (chosen at start-up, in this order)

1. `acquireVsCodeApi` exists → VS Code: posts `{type:"ready"}`, listens to `window.message`.
2. `<script type="application/json" id="agentsdiagram-data">` → static. The JSON is a `GraphResult`
   (a bare `Project` is accepted too). "Go to code" opens `vscode://file/<root>/<file>:<line>:<col+1>`.
   If `<script type="text/plain" id="agentsdiagram-mermaid">` exists, "Copy Mermaid" copies it.
3. `pnpm dev` → loads `packages/protocol/fixtures/sample.json`.

The bundle mounts on `#root`.

## Development

```
pnpm --filter @agentsdiagram/viewer dev        # Vite with the sample
pnpm --filter @agentsdiagram/viewer test       # vitest
pnpm --filter @agentsdiagram/viewer typecheck
pnpm --filter @agentsdiagram/viewer build      # dist/ + copy to src/agentsdiagram/_static/
```
