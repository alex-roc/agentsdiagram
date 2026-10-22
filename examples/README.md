# Examples

Two small projects to try agentsdiagram on. They are written against the real APIs, but they are
only meant to be read: nothing here calls a model.

| Folder | Framework | Shows |
|---|---|---|
| `support_desk/` | PydanticAI 2.x | a triage agent that delegates to two specialists, a toolset with a tool that needs approval, an MCP server, native tools, a hand-off workflow and a pydantic-graph escalation flow |
| `research_team/` | smolagents 1.x | a manager with two managed agents, default tools, a `Tool` subclass, a `@tool` function and MCP tools |

```bash
uvx agentsdiagram scan examples/support_desk                  # Mermaid
uvx agentsdiagram scan examples -f html -o examples.html      # interactive page
```
