"""Neo4j adapter implementing `GraphRepository` (steps 7-9).

Reuses the same credentials as the rest of the service (src.config.get_settings:
NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE). All Cypher lives
in .cypher files; this module only builds parameters and maps English entity
fields onto the canonical Vietnamese graph properties.
"""

from __future__ import annotations

import logging

from neo4j import AsyncGraphDatabase

from src.config import get_settings

from ...domain.entity.amendment import Amendment, Citation, ResolvedTarget
from ...domain.entity.document import KGDocument, make_clause_id, make_point_id
from ...domain.entity.enums import RelationType
from ...domain.errors import Neo4jLoadError
from ...domain.services.text_normalizer import so_hieu_to_doc_id
from .cypher_loader import load_sections, load_statements

logger = logging.getLogger(__name__)


class Neo4jKGRepository:
    """Concrete `GraphRepository`. Lifecycle managed by the API dependency
    (connect() on enter, aclose() on exit)."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._driver = None

    # --- lifecycle ---------------------------------------------------------

    async def connect(self) -> "Neo4jKGRepository":
        if self._settings.NEO4J_URI and self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self._settings.NEO4J_URI,
                auth=(self._settings.NEO4J_USERNAME, self._settings.NEO4J_PASSWORD),
            )
        return self

    async def aclose(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    @property
    def enabled(self) -> bool:
        return self._driver is not None

    @property
    def _database(self) -> str | None:
        return self._settings.NEO4J_DATABASE or None

    # --- mapping helpers ---------------------------------------------------

    @staticmethod
    def _doc_props(doc: KGDocument) -> dict:
        m = doc.metadata
        return {
            "số_hiệu": m.so_hieu,
            "tên": m.ten,
            "tên_ngắn": m.ten_ngan,
            "aliases": m.aliases,
            "loại_code": m.loai_code.value,
            "loại": m.loai,
            "ngày_ban_hành": m.ngay_ban_hanh,
            "ngày_hiệu_lực": m.ngay_hieu_luc,
            "ngày_hết_hiệu_lực": m.ngay_het_hieu_luc,
            "trạng_thái": doc.trang_thai.value,
            "phân_loại_vb": doc.doc_class.value,
            "lĩnh_vực": m.linh_vuc,
            "ngôn_ngữ": doc.ngon_ngu,
            "nguồn_file": doc.source_file,
            "nguồn_url": doc.nguon_url,
            "hash_nội_dung": doc.content_hash,
            "người_ký": m.nguoi_ky,
            "chức_vụ_người_ký": m.chuc_vu_nguoi_ky,
            "cơ_quan_ban_hành": m.co_quan_ban_hanh,
        }

    @staticmethod
    def _structure_rows(doc: KGDocument) -> tuple[list, list, list, list]:
        chapters, articles, clauses, points = [], [], [], []
        for ch in doc.structure.chapters:
            chapters.append(
                {
                    "id": f"{doc.doc_id}#chương-{ch.so}",
                    "số": ch.so,
                    "tiêu_đề": ch.tieu_de,
                }
            )
        for art in doc.structure.iter_articles():
            art_id = f"{doc.doc_id}#điều-{art.so}"
            articles.append(
                {
                    "id": art_id,
                    "props": {
                        "số": art.so,
                        "tiêu_đề": art.tieu_de,
                        "nội_dung": art.noi_dung_full,
                        "thứ_tự": art.thu_tu,
                    },
                }
            )
            for cl in art.clauses:
                cl_id = make_clause_id(art_id, cl.so)
                clauses.append(
                    {
                        "id": cl_id,
                        "article_id": art_id,
                        "props": {
                            "số": cl.so,
                            "nội_dung": cl.noi_dung,
                            "thứ_tự": cl.thu_tu,
                        },
                    }
                )
                for pt in cl.points:
                    points.append(
                        {
                            "id": make_point_id(cl_id, pt.ky_hieu),
                            "clause_id": cl_id,
                            "props": {
                                "ký_hiệu": pt.ky_hieu,
                                "nội_dung": pt.noi_dung,
                                "thứ_tự": pt.thu_tu,
                            },
                        }
                    )
        return chapters, articles, clauses, points

    def _based_on_rows(self, doc: KGDocument) -> list[dict]:
        year = doc.metadata.ngay_ban_hanh.year if doc.metadata.ngay_ban_hanh else None
        rows = []
        for ref in doc.metadata.can_cu_phap_ly:
            tid = so_hieu_to_doc_id(ref.so_hieu, year)
            if tid:
                rows.append({"số_hiệu": ref.so_hieu, "doc_id": tid})
        return rows

    def _amend_rows(self, doc: KGDocument, amendments: list[Amendment]) -> dict:
        buckets: dict[str, list[dict]] = {"amends": [], "repeals": [], "replaces": []}
        year = doc.metadata.ngay_ban_hanh.year if doc.metadata.ngay_ban_hanh else None
        for am in amendments:
            target_id = am.target_doc_id or so_hieu_to_doc_id(
                am.target_doc_so_hieu, year
            )
            if not (am.target_doc_so_hieu and target_id):
                continue
            row = {
                "target_so_hieu": am.target_doc_so_hieu,
                "target_doc_id": target_id,
                "source_clause_id": am.source_clause_id,
                "scope": am.scope,
                "props": {
                    "scope_type": am.scope_type.value,
                    "target_article": am.target_article,
                    "target_clause": am.target_clause,
                    "target_point": am.target_point,
                    "effective_from": am.effective_from,
                    "from_llm": am.from_llm,
                },
            }
            if am.type == RelationType.REPEALS:
                buckets["repeals"].append(row)
            elif am.type == RelationType.REPLACES:
                buckets["replaces"].append(row)
            else:
                buckets["amends"].append(row)
        return buckets

    def _citation_rows(
        self, doc: KGDocument, citations: list[Citation]
    ) -> tuple[list, list]:
        year = doc.metadata.ngay_ban_hanh.year if doc.metadata.ngay_ban_hanh else None
        internal, external = [], []
        for ct in citations:
            if ct.is_internal and ct.target_article is not None:
                internal.append(
                    {
                        "source_id": ct.source_id,
                        "target_article_id": f"{doc.doc_id}#điều-{ct.target_article}",
                    }
                )
            elif ct.target_so_hieu:
                tid = so_hieu_to_doc_id(ct.target_so_hieu, year)
                if tid:
                    external.append(
                        {
                            "source_id": ct.source_id,
                            "target_so_hieu": ct.target_so_hieu,
                            "target_doc_id": tid,
                        }
                    )
        return internal, external

    # --- GraphRepository ---------------------------------------------------

    async def init_schema(self) -> None:
        async with self._driver.session(database=self._database) as session:
            for stmt in load_statements("schema.cypher"):
                await session.run(stmt)

    async def resolve_target(self, so_hieu: str) -> ResolvedTarget | None:
        if not so_hieu:
            return None
        query = (
            "MATCH (d:Document {số_hiệu: $sh}) "
            "RETURN d.id AS id, d.trạng_thái AS st"
        )
        async with self._driver.session(database=self._database) as session:
            rec = await (await session.run(query, {"sh": so_hieu})).single()
        if not rec:
            return None
        return ResolvedTarget(
            so_hieu=so_hieu,
            doc_id=rec["id"],
            is_placeholder=rec["st"] == "PLACEHOLDER",
        )

    async def load_document(
        self,
        document: KGDocument,
        amendments: list[Amendment],
        citations: list[Citation],
    ) -> None:
        sections = load_sections("load_document.cypher")
        chapters, articles, clauses, points = self._structure_rows(document)
        amend_buckets = self._amend_rows(document, amendments)
        cit_internal, cit_external = self._citation_rows(document, citations)

        params = {
            "id": document.doc_id,
            "doc_id": document.doc_id,
            "so_hieu": document.metadata.so_hieu,
            "props": self._doc_props(document),
            "authority_name": document.metadata.co_quan_ban_hanh or "Không xác định",
            "doc_type_code": document.metadata.loai_code.value,
            "doc_type_label": document.metadata.loai or "Không xác định",
            "chapters": chapters,
            "articles": articles,
            "clauses": clauses,
            "points": points,
            "based_on": self._based_on_rows(document),
            "amends": amend_buckets["amends"],
            "repeals": amend_buckets["repeals"],
            "replaces": amend_buckets["replaces"],
            "citations_internal": cit_internal,
            "citations_external": cit_external,
        }

        order = [
            "document",
            "chapters",
            "articles",
            "clauses",
            "points",
            "based_on",
            "amends",
            "repeals",
            "replaces",
            "citations_external",
            "citations_internal",
        ]

        async def _tx(tx) -> None:
            for name in order:
                await tx.run(sections[name], params)

        try:
            async with self._driver.session(database=self._database) as session:
                await session.execute_write(_tx)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Neo4j load failed for %s", document.doc_id)
            raise Neo4jLoadError(str(exc)) from exc

    async def validate(self) -> dict:
        sections = load_sections("validate.cypher")
        report: dict = {"errors": {}, "warnings": {}, "ok": True}
        async with self._driver.session(database=self._database) as session:
            for name, query in sections.items():
                rows = await (await session.run(query)).data()
                if name == "placeholder_count":
                    report["warnings"]["placeholder_count"] = (
                        rows[0]["placeholder_count"] if rows else 0
                    )
                elif rows:
                    report["errors"][name] = rows
                    report["ok"] = False
        return report

    async def resolve_placeholders(self) -> int:
        query = load_sections("resolve_placeholders.cypher")["unresolved"]
        async with self._driver.session(database=self._database) as session:
            rows = await (await session.run(query)).data()
        logger.info("[kg] %d placeholder(s) awaiting ingestion", len(rows))
        return len(rows)

    async def stats(self) -> dict:
        query = load_sections("stats.cypher")["counts"]
        async with self._driver.session(database=self._database) as session:
            rec = await (await session.run(query)).single()
        return dict(rec) if rec else {}
