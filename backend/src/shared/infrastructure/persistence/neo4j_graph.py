import logging
from typing import Any

from neo4j import AsyncGraphDatabase

from src.config import get_settings

logger = logging.getLogger(__name__)

RELATIONSHIP_TYPES = {
    "Tuân thủ": "TUAN_THU",
    "Không tuân thủ": "KHONG_TUAN_THU",
    "Cần kiểm tra": "CAN_KIEM_TRA",
}


class Neo4jAuditGraph:
    """Lightweight helper to persist audit nodes/relationships in Neo4j."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._driver = None

    async def __aenter__(self) -> "Neo4jAuditGraph":
        if not self._settings.NEO4J_URI:
            logger.warning("Neo4j is not configured; skipping graph persistence")
            return self
        self._driver = AsyncGraphDatabase.driver(
            self._settings.NEO4J_URI,
            auth=(self._settings.NEO4J_USERNAME, self._settings.NEO4J_PASSWORD),
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._driver:
            await self._driver.close()

    async def upsert_audit_nodes_and_relation(
        self,
        audited_doc: dict[str, Any],
        basis_doc: dict[str, Any],
        status: str,
        create_relationship: bool,
    ) -> None:
        if not self._driver:
            return

        rel_type = RELATIONSHIP_TYPES.get(status) if create_relationship else None

        query = (
            "MERGE (audited:LegalDocument {law_number: $audited_law_number, "
            "law_name: $audited_law_name, date: $audited_date}) "
            "MERGE (basis:LegalDocument {law_number: $basis_law_number, "
            "law_name: $basis_law_name, date: $basis_date}) "
        )
        if rel_type:
            query += f"MERGE (audited)-[:{rel_type}]->(basis)"

        params = {
            "audited_law_number": (audited_doc.get("law_number") or "").strip(),
            "audited_law_name": (audited_doc.get("law_name") or "").strip(),
            "audited_date": (audited_doc.get("date") or "").strip(),
            "basis_law_number": (basis_doc.get("law_number") or "").strip(),
            "basis_law_name": (basis_doc.get("law_name") or "").strip(),
            "basis_date": (basis_doc.get("date") or "").strip(),
        }

        database = self._settings.NEO4J_DATABASE or None
        async def _write(tx) -> None:
            await tx.run(query, params)

        try:
            async with self._driver.session(database=database) as session:
                await session.execute_write(_write)
        except Exception:
            logger.exception("Neo4j write failed")

    async def fetch_related_documents(self, document: dict[str, Any]) -> list[dict]:
        if not self._driver:
            return []

        query = (
            "MATCH (doc:LegalDocument) "
            "WHERE ($law_number = '' OR doc.law_number = $law_number) "
            "AND ($law_name = '' OR doc.law_name = $law_name) "
            "AND ($date = '' OR doc.date = $date) "
            "MATCH (doc)-[r]->(other:LegalDocument) "
            "RETURN 'out' AS direction, type(r) AS relationship, "
            "other.law_number AS law_number, other.law_name AS law_name, other.date AS date "
            "UNION "
            "MATCH (doc:LegalDocument) "
            "WHERE ($law_number = '' OR doc.law_number = $law_number) "
            "AND ($law_name = '' OR doc.law_name = $law_name) "
            "AND ($date = '' OR doc.date = $date) "
            "MATCH (other:LegalDocument)-[r]->(doc) "
            "RETURN 'in' AS direction, type(r) AS relationship, "
            "other.law_number AS law_number, other.law_name AS law_name, other.date AS date"
        )

        params = {
            "law_number": (document.get("law_number") or "").strip(),
            "law_name": (document.get("law_name") or "").strip(),
            "date": (document.get("date") or "").strip(),
        }

        database = self._settings.NEO4J_DATABASE or None

        async def _read(tx) -> list[dict]:
            result = await tx.run(query, params)
            records = await result.data()
            return [
                {
                    "direction": record.get("direction") or "",
                    "relationship": record.get("relationship") or "",
                    "law_number": record.get("law_number") or "",
                    "law_name": record.get("law_name") or "",
                    "date": record.get("date") or "",
                }
                for record in records
            ]

        try:
            async with self._driver.session(database=database) as session:
                return await session.execute_read(_read)
        except Exception:
            logger.exception("Neo4j read failed")
            return []
