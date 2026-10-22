"""pydantic-graph BaseNode classes: edges come from the return annotations of run()."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext


@dataclass
class Ask(BaseNode[None, None, str]):
    """Ask a question."""

    async def run(self, ctx: GraphRunContext) -> Check:
        return Check()


@dataclass
class Check(BaseNode[None, None, str]):
    async def run(self, ctx: GraphRunContext) -> Ask | End[str]:
        return End("ok")
