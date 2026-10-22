"""A Tool subclass, an OpenAI model and add_base_tools."""

from smolagents import OpenAIServerModel, Tool, ToolCallingAgent


class StockPrice(Tool):
    name = "stock_price"
    description = "Latest price of a stock."
    inputs = {"symbol": {"type": "string", "description": "Ticker symbol"}}
    output_type = "number"

    def forward(self, symbol: str) -> float:
        return 1.0


agent = ToolCallingAgent(
    tools=[StockPrice()],
    model=OpenAIServerModel(model_id="gpt-5"),
    add_base_tools=True,
)
