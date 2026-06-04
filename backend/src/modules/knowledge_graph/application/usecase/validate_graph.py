"""Run post-load Cypher validation checks (section 9)."""

from ..ports.graph_repository import GraphRepository


class ValidateGraphUseCase:
    def __init__(self, graph_repo: GraphRepository) -> None:
        self._repo = graph_repo

    async def execute(self) -> dict:
        if not self._repo.enabled:
            return {"status": "skipped", "reason": "Neo4j not configured"}
        return await self._repo.validate()
