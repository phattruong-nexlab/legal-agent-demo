import logging

from neo4j import AsyncGraphDatabase

from src.config import get_settings

logger = logging.getLogger(__name__)


class LegalKGReader:
    """Read-only access to legal document content in the Knowledge Graph."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._driver = None

    async def __aenter__(self) -> "LegalKGReader":
        if not self._settings.NEO4J_URI:
            logger.warning("Neo4j not configured; LegalKGReader disabled")
            return self
        self._driver = AsyncGraphDatabase.driver(
            self._settings.NEO4J_URI,
            auth=(self._settings.NEO4J_USERNAME, self._settings.NEO4J_PASSWORD),
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    @property
    def enabled(self) -> bool:
        return self._driver is not None

    @property
    def _database(self) -> str | None:
        return self._settings.NEO4J_DATABASE or None

    async def list_documents(self) -> list[dict]:
        """Return {doc_id, so_hieu, ten, ngay_ban_hanh} for all non-placeholder Documents."""
        if not self._driver:
            return []

        query = (
            "MATCH (d:Document) "
            "WHERE d.trạng_thái <> 'PLACEHOLDER' "
            "RETURN d.id AS doc_id, d.số_hiệu AS so_hieu, "
            "d.tên AS ten, toString(d.ngày_ban_hành) AS ngay_ban_hanh"
        )

        async def _read(tx) -> list[dict]:
            result = await tx.run(query)
            return await result.data()

        try:
            async with self._driver.session(database=self._database) as session:
                rows = await session.execute_read(_read)
            return [
                {
                    "doc_id": r.get("doc_id") or "",
                    "so_hieu": r.get("so_hieu") or "",
                    "ten": r.get("ten") or "",
                    "ngay_ban_hanh": r.get("ngay_ban_hanh") or "",
                }
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to list KG documents")
            return []

    async def get_articles(self, doc_id: str) -> list[dict]:
        """Return all Article nodes for a document, sorted by article number.

        Handles both direct Document→Article and Document→Chapter→Article hierarchies.
        """
        if not self._driver:
            return []

        # Variable-length path traversal covers:
        #   1-hop: (Document)-[:HAS_ARTICLE]->(Article)
        #   2-hop: (Document)-[:HAS_CHAPTER]->(Chapter)-[:HAS_ARTICLE]->(Article)
        query = (
            "MATCH (d:Document {id: $doc_id})-[:HAS_CHAPTER|HAS_ARTICLE*1..2]->(a:Article) "
            "RETURN DISTINCT a.id AS id, a.số AS so, a.tiêu_đề AS tieu_de, "
            "a.nội_dung AS noi_dung, a.thứ_tự AS thu_tu "
            "ORDER BY a.thứ_tự"
        )

        async def _read(tx) -> list[dict]:
            result = await tx.run(query, {"doc_id": doc_id})
            return await result.data()

        try:
            async with self._driver.session(database=self._database) as session:
                rows = await session.execute_read(_read)
            return [
                {
                    "id": r.get("id") or "",
                    "so": r.get("so") or 0,
                    "tieu_de": r.get("tieu_de") or "",
                    "noi_dung": r.get("noi_dung") or "",
                }
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to get articles for doc_id=%s", doc_id)
            return []

    async def get_chapters(self, doc_id: str) -> list[dict]:
        """Return chapters of a document, each with its ordered articles.

        Only covers the Document→Chapter→Article hierarchy. Returns [] when the
        document has no chapters (caller should fall back to get_articles).
        """
        if not self._driver:
            return []

        query = (
            "MATCH (d:Document {id: $doc_id})-[:HAS_CHAPTER]->(c:Chapter) "
            "OPTIONAL MATCH (c)-[:HAS_ARTICLE]->(a:Article) "
            "WITH c, a ORDER BY a.thứ_tự "
            "WITH c, collect(CASE WHEN a IS NULL THEN NULL ELSE "
            "{so: a.số, tieu_de: a.tiêu_đề, noi_dung: a.nội_dung} END) AS arts "
            "RETURN c.số AS so, c.tiêu_đề AS tieu_de, "
            "[x IN arts WHERE x IS NOT NULL] AS articles "
            "ORDER BY c.số"
        )

        async def _read(tx) -> list[dict]:
            result = await tx.run(query, {"doc_id": doc_id})
            return await result.data()

        try:
            async with self._driver.session(database=self._database) as session:
                rows = await session.execute_read(_read)
            return [
                {
                    "so": r.get("so") or 0,
                    "tieu_de": r.get("tieu_de") or "",
                    "articles": [
                        {
                            "so": a.get("so") or 0,
                            "tieu_de": a.get("tieu_de") or "",
                            "noi_dung": a.get("noi_dung") or "",
                        }
                        for a in (r.get("articles") or [])
                    ],
                }
                for r in rows
            ]
        except Exception:
            logger.exception("Failed to get chapters for doc_id=%s", doc_id)
            return []

    async def get_document_summary(self, doc_id: str) -> dict | None:
        """Return {doc_id, so_hieu, ten, loai, ngay_ban_hanh, ngay_hieu_luc,
        ngay_het_hieu_luc, trang_thai} for a single Document."""
        if not self._driver:
            return None

        query = (
            "MATCH (d:Document {id: $doc_id}) "
            "RETURN d.id AS doc_id, d.số_hiệu AS so_hieu, d.tên AS ten, d.loại AS loai, "
            "toString(d.ngày_ban_hành) AS ngay_ban_hanh, "
            "toString(d.ngày_hiệu_lực) AS ngay_hieu_luc, "
            "toString(d.ngày_hết_hiệu_lực) AS ngay_het_hieu_luc, "
            "d.trạng_thái AS trang_thai"
        )

        async def _read(tx) -> dict | None:
            result = await tx.run(query, {"doc_id": doc_id})
            rec = await result.single()
            return dict(rec) if rec else None

        try:
            async with self._driver.session(database=self._database) as session:
                row = await session.execute_read(_read)
            if not row:
                return None
            return {
                "doc_id": row.get("doc_id") or "",
                "so_hieu": row.get("so_hieu") or "",
                "ten": row.get("ten") or "",
                "loai": row.get("loai") or "",
                "ngay_ban_hanh": row.get("ngay_ban_hanh") or "",
                "ngay_hieu_luc": row.get("ngay_hieu_luc") or "",
                "ngay_het_hieu_luc": row.get("ngay_het_hieu_luc") or "",
                "trang_thai": row.get("trang_thai") or "",
            }
        except Exception:
            logger.exception("Failed to get document summary for doc_id=%s", doc_id)
            return None

    async def get_article_node(
        self,
        doc_id: str,
        article_so: int,
    ) -> dict | None:
        """Return a single Article node (and its clauses/points) for the given doc + article number."""
        if not self._driver:
            return None

        query = (
            "MATCH (d:Document {id: $doc_id})-[:HAS_CHAPTER|HAS_ARTICLE*1..2]->(a:Article {số: $so}) "
            "OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(cl:Clause) "
            "OPTIONAL MATCH (cl)-[:HAS_POINT]->(pt:Point) "
            "WITH a, cl, collect(DISTINCT {ky_hieu: pt.ký_hiệu, noi_dung: pt.nội_dung, thu_tu: pt.thứ_tự}) AS points "
            "WITH a, collect(DISTINCT CASE WHEN cl IS NULL THEN NULL ELSE "
            "{so: cl.số, noi_dung: cl.nội_dung, thu_tu: cl.thứ_tự, points: points} END) AS clauses "
            "RETURN a.id AS id, a.số AS so, a.tiêu_đề AS tieu_de, a.nội_dung AS noi_dung, "
            "[c IN clauses WHERE c IS NOT NULL] AS clauses"
        )

        async def _read(tx) -> dict | None:
            result = await tx.run(query, {"doc_id": doc_id, "so": article_so})
            rec = await result.single()
            return dict(rec) if rec else None

        try:
            async with self._driver.session(database=self._database) as session:
                row = await session.execute_read(_read)
            if not row:
                return None
            clauses = sorted(row.get("clauses") or [], key=lambda c: c.get("thu_tu") or 0)
            for cl in clauses:
                cl["points"] = sorted(
                    [p for p in (cl.get("points") or []) if p.get("ky_hieu")],
                    key=lambda p: p.get("thu_tu") or 0,
                )
            return {
                "id": row.get("id") or "",
                "so": row.get("so") or 0,
                "tieu_de": row.get("tieu_de") or "",
                "noi_dung": row.get("noi_dung") or "",
                "clauses": clauses,
            }
        except Exception:
            logger.exception(
                "Failed to get article node doc_id=%s article=%s", doc_id, article_so
            )
            return None

    async def get_inbound_lifecycle(
        self,
        doc_id: str,
        article_so: int | None = None,
    ) -> list[dict]:
        """Return AMENDS/REPEALS/REPLACES relationships from other Documents into doc_id.

        If `article_so` is provided, filter to relationships whose `target_article`
        matches it OR whose scope is DOCUMENT-wide (which implicitly covers the article).
        """
        if not self._driver:
            return []

        query = (
            "MATCH (src:Document)-[r:AMENDS|REPEALS|REPLACES]->(target:Document {id: $doc_id}) "
            "WHERE $article_so IS NULL "
            "   OR r.target_article = $article_so "
            "   OR r.scope_type = 'DOCUMENT' "
            "RETURN type(r) AS rel_type, "
            "src.id AS src_doc_id, src.số_hiệu AS src_so_hieu, src.tên AS src_ten, "
            "toString(src.ngày_ban_hành) AS src_ngay_ban_hanh, "
            "src.trạng_thái AS src_trang_thai, "
            "r.scope AS scope, r.scope_type AS scope_type, "
            "r.target_article AS target_article, r.target_clause AS target_clause, "
            "r.target_point AS target_point, toString(r.effective_from) AS effective_from"
        )

        async def _read(tx) -> list[dict]:
            result = await tx.run(query, {"doc_id": doc_id, "article_so": article_so})
            return await result.data()

        try:
            async with self._driver.session(database=self._database) as session:
                rows = await session.execute_read(_read)
            return [
                {
                    "rel_type": r.get("rel_type") or "",
                    "src_doc_id": r.get("src_doc_id") or "",
                    "src_so_hieu": r.get("src_so_hieu") or "",
                    "src_ten": r.get("src_ten") or "",
                    "src_ngay_ban_hanh": r.get("src_ngay_ban_hanh") or "",
                    "src_trang_thai": r.get("src_trang_thai") or "",
                    "scope": r.get("scope") or "",
                    "scope_type": r.get("scope_type") or "",
                    "target_article": r.get("target_article"),
                    "target_clause": r.get("target_clause"),
                    "target_point": r.get("target_point"),
                    "effective_from": r.get("effective_from") or "",
                }
                for r in rows
            ]
        except Exception:
            logger.exception(
                "Failed to get inbound lifecycle for doc_id=%s article=%s",
                doc_id,
                article_so,
            )
            return []
