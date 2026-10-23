# Examples

Small projects to try agentsdiagram on, from one agent to a team. They are written against the real
APIs, but they are only meant to be read: nothing here calls a model.

| Folder | Framework | Shows |
|---|---|---|
| `hello_smolagents/` | smolagents 1.x | one `CodeAgent` with a `@tool` function and a default tool ([tutorial 1](../docs/tutorials/01-one-smolagents-agent.md)) |
| `hello_pydantic_ai/` | PydanticAI 2.x | one `Agent` with `@agent.tool_plain` and `@agent.tool` ([tutorial 2](../docs/tutorials/02-one-pydantic-ai-agent.md)) |
| `research_team/` | smolagents 1.x | a manager with two managed agents, default tools, a `Tool` subclass, a `@tool` function and MCP tools ([tutorial 3](../docs/tutorials/03-teams-of-agents.md)) |
| `support_desk/` | PydanticAI 2.x | a triage agent that delegates to two specialists, a toolset with a tool that needs approval, an MCP server, native tools, a hand-off workflow and a pydantic-graph escalation flow ([tutorial 3](../docs/tutorials/03-teams-of-agents.md)) |

```bash
uvx agentsdiagram scan examples/hello_smolagents              # Mermaid
uvx agentsdiagram scan examples -f html -o examples.html      # all of them, interactive
cp -r examples/hello_smolagents ~/travel && uvx agentsdiagram serve ~/travel   # plan and edit a copy
```

The website demos are generated from these folders, and `tests/test_examples.py` keeps them
complete: change an example and adjust the test.
