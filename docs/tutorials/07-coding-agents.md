# 7. With coding agents

Coding agents (Claude Code, Codex, Cursor's agent…) write a lot of agent code now. agentsdiagram
gives them, and you, two things: a picture of what they built, and precise commands to change its
structure instead of hand-editing lists of tools.

## Let the agent see the structure

`scan -f json` prints the whole graph: agents, tools, who uses what, with file and line for each
node. It is a compact map of a multi-agent codebase, far smaller than the code itself.

```bash
agentsdiagram scan . -f json
agentsdiagram check . --json     # what is wrong, with locations
```

## Let it make structural changes with one command

Every `agentsdiagram edit` operation is deterministic, prints the diff it applied, and refuses
with an explanation when it cannot do the change cleanly. That makes it a good tool for an agent:

```bash
agentsdiagram edit add-agent reviewer --parent lead --description "Reviews the report."
agentsdiagram edit add-tool reviewer score_report --params "report: str" --returns "float"
agentsdiagram edit add-mcp reviewer --command "uvx mcp-server-fetch"
agentsdiagram edit set-model reviewer Qwen/Qwen3-Coder-30B-A3B-Instruct
agentsdiagram edit remove old_tool --dry-run
```

Use `--json` for a machine-readable result:

```json
{
  "ok": true,
  "message": "Planned tool `score_report` for `reviewer` in app/team.py.",
  "files": ["app/team.py"],
  "focus": "smolagents:tool:app.team.score_report",
  "written": true
}
```

## A note for your project's agent instructions

Add something like this to `AGENTS.md` or `CLAUDE.md`:

```markdown
## Agents in this repo
- See the structure with `uvx agentsdiagram scan . -f json`; run `uvx agentsdiagram check .` after changes.
- To add or wire agents, tools and MCP servers, prefer `uvx agentsdiagram edit …`
  (add-agent, add-tool, add-mcp, connect, disconnect, remove, set-model); it writes idiomatic code.
- Planned stubs raise NotImplementedError("agentsdiagram: planned"): implement them, don't delete the marker silently.
```

## Plan with a human, build with an agent

A workflow that works well:

1. You sketch the system in the diagram (`agentsdiagram serve` or VS Code): agents, tools, MCP
   servers. Everything lands in the code as planned stubs.
2. You ask your coding agent to "implement the planned nodes". `agentsdiagram check` lists them
   (AD401) with file and line.
3. The diagram shows progress: planned nodes lose their dashed outline as they are implemented.
