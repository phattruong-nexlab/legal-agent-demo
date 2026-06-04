"""Port: persistence of the legal knowledge graph (steps 7-9).

Implemented by the Neo4j adapter in the infrastructure layer. Keeping this a
Protocol lets the use cases stay framework/database agnostic.
"""

from typing import Protocol

from ...domain.entity.amendment import Amendment, Citation, ResolvedTarget
from ...domain.entity.document import KGDocument


class GraphRepository(Protocol):
    @property
    def enabled(self) -> bool:
        """False when Neo4j is not configured (NEO4J_URI empty)."""
        raise NotImplementedError

    async def init_schema(self) -> None:
        """Create constraints & indexes (idempotent, section 3.5)."""
        raise NotImplementedError

    async def resolve_target(self, so_hieu: str) -> ResolvedTarget | None:
        """Find a Document by số hiệu; None when absent."""
        raise NotImplementedError

    async def load_document(
        self,
        document: KGDocument,
        amendments: list[Amendment],
        citations: list[Citation],
    ) -> None:
        """Load the whole document in a single transaction (idempotent MERGE,
        section 8). Mints PLACEHOLDER nodes for unresolved targets."""
        raise NotImplementedError

    async def validate(self) -> dict:
        """Run the post-load Cypher checks (section 9). Returns a report."""
        raise NotImplementedError

    async def resolve_placeholders(self) -> int:
        """Promote PLACEHOLDER nodes that now have a real counterpart.
        Returns the number resolved."""
        raise NotImplementedError

    async def stats(self) -> dict:
        """Node/relationship counts (section 5 `stats`)."""
        raise NotImplementedError
