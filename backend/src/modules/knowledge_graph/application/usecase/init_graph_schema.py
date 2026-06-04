"""Create Neo4j constraints & indexes (section 3.5). Idempotent."""

from ..ports.graph_repository import GraphRepository


class InitGraphSchemaUseCase:
    def __init__(self, graph_repo: GraphRepository) -> None:
        self._repo = graph_repo

    async def execute(self) -> dict:
        if not self._repo.enabled:
            return {"status": "skipped", "reason": "Neo4j not configured"}
        await self._repo.init_schema()
        return {"status": "ok"}
