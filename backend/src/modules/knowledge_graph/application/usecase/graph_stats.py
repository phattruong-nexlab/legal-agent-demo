"""Node / relationship counts (section 5 `stats`)."""

from ..ports.graph_repository import GraphRepository


class GraphStatsUseCase:
    def __init__(self, graph_repo: GraphRepository) -> None:
        self._repo = graph_repo

    async def execute(self) -> dict:
        if not self._repo.enabled:
            return {"status": "skipped", "reason": "Neo4j not configured"}
        return await self._repo.stats()
