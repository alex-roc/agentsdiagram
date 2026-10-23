# Command line

Run it without installing anything with [uv](https://docs.astral.sh/uv/): `uvx agentsdiagram …`.
Or install it once: `uv tool install agentsdiagram` (or `pip install agentsdiagram`). Python 3.11+.

Every command takes a file or a folder (default `.`). The project root is the nearest folder with
a `pyproject.toml` or `.git`; ids and globs are relative to it.

## `scan`: draw the diagram

```
agentsdiagram scan [PATH] [-f mermaid|json|html|markdown] [-o FILE] [--title TEXT]
                   [--framework smolagents|pydantic_ai] [--include GLOB] [--exclude GLOB]
```

| Format | Use it for |
|---|---|
| `mermaid` (default) | pasting into docs, issues or any Mermaid renderer |
| `markdown` | a `.md` file with a Mermaid block: GitHub renders it (`-o AGENTS-DIAGRAM.md`) |
| `html` | one self-contained interactive page (no server, no network) to open or share |
| `json` | the [IR](ir.md), for your own tools |

`--include`/`--exclude` are repeatable globs relative to the project root. Set them once in
`pyproject.toml`:

```toml
[tool.agentsdiagram]
include = ["src/**"]
exclude = ["tests/**", "notebooks/**"]
```

## `check`: diagnostics for CI

```
agentsdiagram check [PATH] [--strict] [--json]
```

Prints what the analysis found (`file:line:col: severity CODE message`) and exits with 1 if there
are errors (`--strict`: also warnings). Codes are listed in [the IR reference](ir.md#diagnostic-codes),
for example a smolagents managed agent without a description (AD201) or PydanticAI v1 API still in
use (AD101). Planned nodes are reported as AD401 (info).

## `serve`: live, editable diagram in the browser

```
agentsdiagram serve [PATH] [--port 8765] [--no-open] [--read-only] [--title TEXT]
```

Opens the viewer at `http://127.0.0.1:8765/` and redraws it whenever a file changes. From the page
you can plan and edit agents (see [Plan and edit](editing.md)); the server writes the files.
`--read-only` turns editing off. The server only listens on localhost, and edits need a token
that only the page it serves knows.

## `edit`: plan and edit from the command line

```
agentsdiagram edit OPERATION … [-p PROJECT] [--dry-run] [--json]
```

Each operation prints the unified diff it applied; `--dry-run` prints it without writing, `--json`
prints the result as JSON (handy for scripts and coding agents). Agents and nodes are named by
name when that is unambiguous (`analyst`), by the end of their id (`team.analyst`) or by full id
(`smolagents:agent:app.team.analyst`, see `scan -f json`).

| Operation | Example |
|---|---|
| `add-agent NAME [--file FILE] [--parent AGENT] [--framework F] [--model M] [--description D] [--instructions T] [--class CodeAgent\|ToolCallingAgent]` | `agentsdiagram edit add-agent reviewer --parent lead --description "Checks the report."` (`--file` defaults to the parent's file) |
| `add-tool AGENT NAME [--params P] [--returns T] [--description D]` | `agentsdiagram edit add-tool analyst fetch_dataset --params "url: str, limit: int = 100"` |
| `add-mcp AGENT (--url URL \| --command CMD) [--name N]` | `agentsdiagram edit add-mcp tech --command "uvx mcp-server-fetch"` |
| `connect SOURCE TARGET [--description D]` | `agentsdiagram edit connect triage billing` |
| `disconnect SOURCE TARGET` | `agentsdiagram edit disconnect lead web_researcher` |
| `remove NODE` | `agentsdiagram edit remove plot` |
| `set-model AGENT MODEL` | `agentsdiagram edit set-model triage anthropic:claude-opus-5-5` |
| `set-instructions AGENT TEXT` | `agentsdiagram edit set-instructions billing "Be brief."` (`""` removes them) |
| `export-spec AGENT [--path P] [--no-replace]` | `agentsdiagram edit export-spec tech` (PydanticAI) |

## `lsp` and `schema`

`agentsdiagram lsp` runs the language server the VS Code extension uses (needs the `lsp` extra:
`uvx --from 'agentsdiagram[lsp]' agentsdiagram lsp`). `agentsdiagram schema` prints the JSON
Schema of the IR and of the edit protocol.
