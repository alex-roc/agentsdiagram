# Getting started

agentsdiagram reads the code of your [smolagents](https://huggingface.co/docs/smolagents) and
[PydanticAI](https://ai.pydantic.dev) agents and draws them: agents, tools, MCP servers, managed
agents and delegation, workflows and flows. It can also write code for you: plan agents and tools
in the diagram and they appear in your files as stubs, ready to fill in.

It is **static analysis**. Your code is parsed, never imported or run, so it needs no API keys,
none of your project's dependencies and no network, and it works on code that does not run yet.

## 1. Draw your first diagram

From the root of a project that uses smolagents or PydanticAI, with
[uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uvx agentsdiagram scan . -f html -o agents.html
```

Open `agents.html` in any browser. Click a node to see its details, press `/` to search, use the
legend to hide node kinds and the moon button for the dark theme. The page is self-contained: you
can attach it to an issue or send it to a colleague.

No project at hand? Clone the repository and try the examples:

```bash
git clone https://github.com/alex-roc/agentsdiagram && cd agentsdiagram
uvx agentsdiagram scan examples -f html -o examples.html
```

## 2. Keep it next to your code

Install **Agents Diagram** from the
[VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=alex-roc.agentsdiagram)
or [Open VSX](https://open-vsx.org/extension/alex-roc/agentsdiagram) (Cursor, Windsurf, Positron).
Open a Python file and run **Agents Diagram: Show Workspace Diagram**. The diagram follows your
edits as you type, "Go to code" jumps to a definition, and moving the cursor selects the node
under it. See [the extension guide](vscode.md).

Not using VS Code? `uvx agentsdiagram serve` gives you the same live diagram in a browser.

## 3. Plan and edit

In VS Code or `agentsdiagram serve`, the **Plan agent** button and the actions in a node's panel
write code: a new agent, a tool stub, an MCP server, a connection between two agents, a new model.
Each change is a normal edit you can undo, and the diagram is redrawn from the result. See
[Plan before you code](tutorials/04-plan-before-you-code.md).

## Next

- Tutorials, from one agent to a team: [1. One smolagents agent](tutorials/01-one-smolagents-agent.md) ·
  [2. One PydanticAI agent](tutorials/02-one-pydantic-ai-agent.md) ·
  [3. Teams of agents](tutorials/03-teams-of-agents.md) ·
  [4. Plan before you code](tutorials/04-plan-before-you-code.md) ·
  [5. Edit from the diagram](tutorials/05-edit-from-the-diagram.md) ·
  [6. Diagrams in CI and docs](tutorials/06-ci-and-docs.md) ·
  [7. With coding agents](tutorials/07-coding-agents.md)
- Reference: [command line](cli.md) · [plan and edit](editing.md) · coverage for
  [smolagents](adapters/smolagents.md) and [PydanticAI](adapters/pydantic_ai.md) · [IR](ir.md)
