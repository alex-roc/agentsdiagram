"""Diagnostics: a managed agent without name/description and an @tool without hints."""

from smolagents import CodeAgent, InferenceClientModel, ToolCallingAgent, tool

model = InferenceClientModel()


@tool
def bad_tool(x):
    return x


helper = ToolCallingAgent(tools=[bad_tool], model=model)
boss = CodeAgent(tools=[], model=model, managed_agents=[helper], executor_type="wasm")
