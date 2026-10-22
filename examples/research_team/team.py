"""A manager CodeAgent that coordinates a web researcher and a data analyst."""

from mcp import StdioServerParameters
from smolagents import (
    CodeAgent,
    InferenceClientModel,
    Tool,
    ToolCallingAgent,
    ToolCollection,
    VisitWebpageTool,
    WebSearchTool,
    tool,
)

model = InferenceClientModel(model_id="Qwen/Qwen3-Next-80B-A3B-Thinking")


class CsvSummary(Tool):
    name = "csv_summary"
    description = "Columns, row count and basic statistics of a CSV file."
    inputs = {"path": {"type": "string", "description": "Path to the CSV file"}}
    output_type = "string"

    def forward(self, path: str) -> str:
        return "3 columns, 120 rows"


@tool
def plot(path: str, x: str, y: str) -> str:
    """Draw a line chart and return the image path.

    Args:
        path: CSV file with the data.
        x: Column for the x axis.
        y: Column for the y axis.
    """
    return "chart.png"


web_researcher = ToolCallingAgent(
    tools=[WebSearchTool(), VisitWebpageTool()],
    model=model,
    name="web_researcher",
    description="Searches the web and reads pages. Give it a precise question.",
    max_steps=8,
)

analyst = CodeAgent(
    tools=[CsvSummary(), plot],
    model=model,
    name="analyst",
    description="Analyses CSV data and draws charts.",
    additional_authorized_imports=["pandas", "numpy"],
)

papers = StdioServerParameters(command="uvx", args=["arxiv-mcp-server"])

with ToolCollection.from_mcp(papers, trust_remote_code=True) as arxiv:
    lead = CodeAgent(
        tools=[*arxiv.tools],
        model=model,
        managed_agents=[web_researcher, analyst],
        planning_interval=3,
    )
