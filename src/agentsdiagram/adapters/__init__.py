"""Framework adapters. Add a framework by writing an adapter and registering it here."""

from .base import Adapter
from .pydantic_ai.extract import PydanticAIAdapter
from .smolagents.extract import SmolagentsAdapter

ADAPTERS: dict[str, Adapter] = {
    "pydantic_ai": PydanticAIAdapter(),  # type: ignore[dict-item]
    "smolagents": SmolagentsAdapter(),  # type: ignore[dict-item]
}

__all__ = ["ADAPTERS", "Adapter"]
