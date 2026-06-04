"""Promote PLACEHOLDER documents that now have a real counterpart (section 7.3)."""

from ..ports.graph_repository import GraphRepository


class ResolvePlaceholdersUseCase:
    def __init__(self, graph_repo: GraphRepository) -> None:
        self._repo = graph_repo

    async def execute(self) -> dict:
        if not self._repo.enabled:
            return {"status": "skipped", "reason": "Neo4j not configured"}
        resolved = await self._repo.resolve_placeholders()
        return {"status": "ok", "resolved": resolved}
