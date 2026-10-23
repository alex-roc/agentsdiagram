# Architecture

`agentsdiagram` turns agent code into a graph without running it, and turns edits made on the
graph back into code. One Python core feeds four front ends (CLI, static HTML page, `serve`,
VS Code extension) through one JSON format (the IR) and one edit protocol.

```
src/agentsdiagram/
  project.py    file discovery (git ls-files), module index, one-pass LibCST collector
  facts.py      per-module facts recorded by adapters (Defs + pending edges)
  adapters/     one package per framework: symbols.py (data) + extract.py (logic)
  analyze.py    lazy loading, name resolution across modules, linking, IR build
  planned.py    the planned markers (a stub body, a comment)
  ir.py         the IR (pydantic), the edit protocol and their JSON Schema
  edit/         plan and edit: doc.py (LibCST changes), engine.py (operations), session.py,
                codegen.py, textedit.py (minimal line edits, diffs), cli.py (`agentsdiagram edit`)
  adapters/<framework>/edit.py   the code each framework gets (agents, tools, MCP, delegation)
  render/       mermaid.py, html.py (inlines the viewer bundle from _static/)
  serve.py      `agentsdiagram serve`: live page, server-sent events, POST /api/edit
  lsp.py        pygls 2 language server for the extension (graph, mermaid, edit)
  cli.py        argparse CLI
packages/
  protocol/     TS types generated from the IR schema + viewer/extension messages
  viewer/       React Flow viewer, one IIFE bundle (viewer.js + viewer.css)
  vscode/       the extension (LanguageClient + webview panel)
```

## Pipeline

1. **Collect.** `project.collect()` lists Python files (honouring `.gitignore` via
   `git ls-files`), builds a module index for cross-module resolution and selects the *seed*
   files to analyse (`[tool.agentsdiagram]` include/exclude apply).
2. **Prefilter.** A seed is parsed only if its bytes mention a framework (`pydantic_ai`,
   `smolagents`…) or an agent run method (`.run(`), so large repos stay fast.
3. **Parse.** LibCST parses each file once. A single custom visitor computes parents,
   scopes, bindings, qualified names and the list of calls. It replaces LibCST's
   Scope/QualifiedName providers, which were 3–4x slower. It follows Python's LEGB
   lookup for module, function and class scopes.
4. **Extract.** Each adapter records `Def`s (things that may become nodes) and pending
   edges whose target is still an expression. Plain functions and classes are registered
   too, so they become tools only when something uses them.
5. **Resolve and link.** `Analyzer.resolve()` follows names through assignments, imports and
   re-exports across modules, factory functions (`return Agent(...)`), list literals, `+`
   concatenation and method calls (`ts.prefixed("x")` becomes an edge wrapper). Modules
   are loaded lazily. Unresolvable expressions become `dynamic` nodes. Library objects
   with no structural meaning (e.g. `Thinking()`) become badges.
6. **Implicit relations.** Function bodies of visible tools and graph steps are scanned for
   `agent.run(...)` calls, which produce `delegates_to` and `runs` edges. A plain function
   that runs two or more agents becomes a `workflow` node with ordered `runs` edges.
7. **Build.** Visible defs (explicit ones in seed files, plus everything reachable) become
   nodes with stable ids. Adapters then run whole-graph checks (`check()`).

## Editing

An edit request names ids from the diagram (see [Plan and edit](editing.md)). `edit.plan_edit`:

1. analyses the project again on the current text (unsaved buffers included in the LSP), and
   refuses the request if a file's hash differs from the one the diagram saw (`expect`);
2. finds each node again in the code by its `SourceRef` range and opens the file as a `Doc`;
3. queues changes against the original LibCST tree (`update` a node, remove a list item or a
   decorator, insert or delete module-level statements, add imports) and renders them in one
   pass, so positions computed on the original stay valid. Framework-specific code comes from
   `adapters/<framework>/edit.py`; the rest (disconnect, remove, instructions) is generic;
4. parses every result again and returns the new texts. The CLI and `serve` write them; the LSP
   turns them into minimal line `TextEdit`s in a versioned `WorkspaceEdit` that the editor
   applies (undo works). The server never writes files itself.

Imports are merged isort-style, and imports an edit makes unused are dropped (comparing the names
used before and after). Planned code is recognised by the analyzer (`planned.py`), so "planned"
is never stored anywhere but in the code.

## Key decisions

- **Static only.** It never imports user code. This keeps it safe and independent of the user's
  environment, and makes it work on broken projects.
- **The code is the single source of truth.** Planning and editing write code with LibCST; the
  diagram never stores state of its own, and planned nodes are marked in the code.
- **Data-driven adapters.** Library symbols live in `symbols.py` tables matched by root
  package and last name (`pydantic_ai.Agent` also matches `pydantic_ai.agent.Agent`).
  `tests/test_symbols_drift.py` imports every entry, and a weekly workflow runs it against the
  latest releases.
- **Factory instances.** `planner = make_agent(...)` creates its own node, a copy of the
  factory's product, and the factory's template node is hidden. Without this, every agent
  built by one factory would collapse into a single node.
- **Tolerant to broken code.** A file with a syntax error keeps its last valid version, marked
  `stale`, plus diagnostic AD000. Each adapter runs isolated, and a crash becomes AD900.
- **Stable ids.** Ids are `framework:kind:module.qualname`. Unnamed constructs use an ordinal
  within their scope, never line numbers. Every node and edge also carries a `SourceRef` (range
  plus name range), which edits use as anchors.
- **LSP for the editor.** pygls gives us unsaved buffers, lifecycle, cancellation and the
  Problems panel. IR columns are code points and are converted to UTF-16 at the LSP boundary.
- **The extension does not embed Python.** It runs `uvx agentsdiagram[lsp]==<its version>`, or a
  user-configured command (machine scope, restricted in untrusted workspaces).

## Development

```bash
uv sync && pnpm install
uv run pytest                     # Python: unit, snapshots (syrupy), oracles, drift, LSP (pytest-lsp)
uv run pytest --snapshot-update   # after an intended output change
pnpm build                        # viewer -> src/agentsdiagram/_static and packages/vscode/media
pnpm schema                       # after changing ir.py: regenerate the schema and TS types
pnpm --filter agentsdiagram test:e2e   # extension + real language server (needs uv)
pnpm --filter agentsdiagram test:visual   # macOS, manual: screenshots of the panel on examples/
```

`test:visual` opens `examples/` in a VS Code window, drives the panel (show a node, a real mouse
click on "Go to code", cursor sync, light and dark themes, an unsaved edit) and saves one
screenshot per step to `packages/vscode/.shots/` (ignored). It needs the Accessibility and Screen
Recording permissions for the terminal. Helpers: `packages/vscode/scripts/window_shot.py` and
`window_click.py` (uv scripts, pyobjc) capture and click one window even if others cover it.

### Viewer

`packages/viewer` is one React Flow app for both hosts. Design tokens live at the top of
`styles.css`: a light and a dark set on `<html data-theme>`, and inside VS Code the editor's
`--vscode-*` variables win, so the panel looks native in any theme. Icons are hand-drawn SVG
paths (`icons.tsx`), no icon library. `model.ts` is pure (IR -> nodes, neighborhood, counts) and
unit-tested; `layout.ts` runs dagre with per-kind node sizes and room for edge labels. Check UI
changes in a browser on `examples/` (`agentsdiagram scan examples -f html`), light and dark,
desktop and 390px wide.

Fixtures live in `tests/fixtures` (their own project root). Oracle tests import them with the
real libraries, so a fixture that stops importing is also a failing test.

## Website

`site/` is the website at <https://alex-roc.github.io/agentsdiagram/>: a hand-written landing
page (`index.html` + `style.css`) and the documentation, rendered from `docs/` by `site/build.py`. Its colour tokens mirror
`packages/viewer/src/styles.css`, and it shares the viewer's `agentsdiagram.theme` key in
`localStorage`, so the embedded demos follow the site's theme toggle.

The documentation pages (`site/docs/`) and the live demos (`site/demo/`) are generated, never
committed (`.gitignore`):

```bash
pnpm --filter @agentsdiagram/viewer build   # only if src/agentsdiagram/_static/ is missing
uv run --group site python site/build.py    # docs/ -> site/docs/, examples/ -> site/demo/
python -m http.server 8000 -d site          # preview
```

`site/build.py` renders every page listed in its `PAGES` table (Markdown from `docs/`, the same
files GitHub shows), rewrites links between them, embeds a live demo where a page has a
`[▶ …](…/demo/x.html)` link, and generates the demos, including one made by running
`agentsdiagram edit` on a copy of an example (the planning tutorial).

`.github/workflows/pages.yml` does the same on every push to `main` that touches `site/`,
`examples/`, `packages/viewer/` or `src/` (or by hand, *workflow_dispatch*) and deploys with
`actions/deploy-pages`. One-time setup: repository Settings → Pages → Source: *GitHub Actions*.

