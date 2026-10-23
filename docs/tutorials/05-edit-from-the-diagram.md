# 5. Edit from the diagram

Once a system exists, the diagram is also a fast way to change its shape: give an agent a new
helper, swap a model, cut a connection, delete a tool you no longer need. Every change is written
to your code; in VS Code it is a normal edit you can undo.

Select an agent and use the **Plan and edit** buttons in its panel. The **Connections** list
under them shows every relation of the node, with a disconnect button where the relation is a
list item or a decorator.

## Connect two agents

**Hand work to…** lets one agent call another.

In smolagents it adds the agent to `managed_agents`, and adds the `name`/`description` the managed
agent needs if they are missing:

```diff
 analyst = CodeAgent(
     tools=[CsvSummary(), plot],
     model=model,
     name="analyst",
     description="Analyses CSV data and draws charts.",
+    managed_agents=[web_researcher],
 )
```

In PydanticAI it writes a delegation tool that runs the other agent, passing the usage (and the
deps when both agents have the same `deps_type`):

```diff
+@tech.tool
+async def tech_asks_billing(ctx: RunContext[Deps], task: str) -> str:
+    """Invoices, refunds and plan changes."""
+    result = await billing.run(task, deps=ctx.deps, usage=ctx.usage)
+    return result.output
```

From the command line: `agentsdiagram edit connect tech billing`.

## Change a model or the instructions

**Change model** replaces the model of that agent only. In smolagents several agents often share
one `model = InferenceClientModel(...)`; changing one of them gives it its own model object and
leaves the others alone.

```bash
agentsdiagram edit set-model triage anthropic:claude-opus-5-5
agentsdiagram edit set-instructions billing "Always check the order history first."
```

## Disconnect and remove

- **Disconnect** (the unlink icon in **Connections**) removes the item from `tools=[...]`,
  `toolsets=[...]` or `managed_agents=[...]`, or the `@agent.tool` decorator.
- **Remove** deletes a node: first the places that reference it, then its definition, if nothing
  else uses it. Imports left unused are removed too.

agentsdiagram refuses changes it cannot make cleanly, and says why:

```
`billing` is still needed: `ask_billing` runs it (examples/support_desk/agents.py:45). Remove those first.
```

Remove `ask_billing` first and then `billing` can go.

## Move settings to an Agent Spec (PydanticAI)

**Move to Agent Spec** writes `tech.agent.yaml` with the agent's model, name, description,
instructions and literal capabilities, and loads it from code. Tools, toolsets and `deps_type`
stay in Python, where they belong:

```yaml
model: anthropic:claude-sonnet-5-5
name: tech
description: Bugs, outages and how-to questions.
instructions: You solve technical problems. Quote the help center when you can.
capabilities:
- Thinking:
    effort: medium
```

```python
tech = Agent.from_file(
    Path(__file__).parent / "tech.agent.yaml",
    deps_type=Deps,
    tools=[Tool(status_page, takes_ctx=False)],
    toolsets=[help_center],
    capabilities=[NativeTool(WebSearchTool())],
)
```

Now prompts and models can be changed without touching Python, and the diagram still shows the
whole agent.

## When the code changed under you

Each edit carries the hash of the files the diagram was drawn from. If you edit a file and click a
button before the diagram catches up, the edit is refused ("changed since the diagram was drawn")
instead of landing in the wrong place. Wait a moment for the redraw and try again.

See [Plan and edit](../editing.md) for every operation and its limits.

## Next

[6. Diagrams in CI and docs](06-ci-and-docs.md).
