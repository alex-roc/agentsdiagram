# 3. Teams of agents

One agent is easy to keep in your head. A manager with specialists, MCP servers and a hand-off
workflow is not, and that is where a diagram pays off.

## smolagents: a manager and its managed agents

[`examples/research_team/team.py`](../../examples/research_team/team.py) has a lead `CodeAgent` that
manages a web researcher and a data analyst, and gets arXiv tools from an MCP server:

```python
web_researcher = ToolCallingAgent(
    tools=[WebSearchTool(), VisitWebpageTool()],
    model=model,
    name="web_researcher",
    description="Searches the web and reads pages. Give it a precise question.",
)

analyst = CodeAgent(
    tools=[CsvSummary(), plot], model=model, name="analyst", description="Analyses CSV data and draws charts."
)

papers = StdioServerParameters(command="uvx", args=["arxiv-mcp-server"])

with ToolCollection.from_mcp(papers, trust_remote_code=True) as arxiv:
    lead = CodeAgent(tools=[*arxiv.tools], model=model, managed_agents=[web_researcher, analyst])
```

[▶ Open the live diagram](https://alex-roc.github.io/agentsdiagram/demo/research-team.html)

- Dashed animated edges are **manages**: `lead` can call `web_researcher` and `analyst` as tools.
- **MCP uvx** is the MCP server with its command line. Its tools only exist at runtime, so the
  diagram shows the server, not a guessed list of tools.
- **csv_summary** is a `Tool` subclass: the panel shows its `inputs` and `output_type`.

smolagents needs a `name` and a `description` on every managed agent (the manager reads the
description to decide when to call it). Remove one and `agentsdiagram check` fails with AD201.

## PydanticAI: delegation and hand-offs

PydanticAI has no "managed agents"; an agent delegates by running another agent inside a tool.
[`examples/support_desk/`](../../examples/support_desk/) does it twice:

```python
@triage.tool
async def ask_billing(ctx: RunContext[Deps], question: str) -> str:
    """Send a billing question to the billing specialist."""
    result = await billing.run(question, deps=ctx.deps, usage=ctx.usage)
    return result.output
```

[▶ Open the live diagram](https://alex-roc.github.io/agentsdiagram/demo/support-desk.html)

- `triage` **uses** the tool `ask_billing`, which **hands work to** `billing`. The analyzer finds
  the `billing.run(...)` call inside the tool body.
- `handle_ticket` is a **workflow**: a plain function that runs agents one after the other. The
  numbered edges (`#1`, `#2`, `#3`) are the order of the calls.
- `build_escalation` is a pydantic-graph flow, drawn as a group with its steps and decisions.
- `crm.prefixed("crm")` becomes an edge label: the wrapper is part of the relation.

## Reading big diagrams

- Click a node: it and its neighbors stay lit and are framed; everything else fades.
- `/` searches by name, `Enter` jumps to the next match.
- Hide what you do not need from the legend (for example the graph steps).
- `agentsdiagram scan src/app/agents.py` (a file) draws only what that file declares and what it
  uses.

## Next

[4. Plan before you code](04-plan-before-you-code.md): draw what does not exist yet.
