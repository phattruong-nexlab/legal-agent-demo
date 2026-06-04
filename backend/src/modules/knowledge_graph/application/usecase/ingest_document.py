"""Ingest one PDF into the knowledge graph — orchestrates steps 1→8.

Each step is a pure domain service; this use case only wires them and talks to
the two ports (PDF extractor + graph repository). No framework imports.
"""

from __future__ import annotations

import hashlib
import logging

from pydantic import BaseModel

from src.shared.infrastructure.llm_engine.interfaces import LLMEngine

from ...domain.entity.document import (
    Article,
    Chapter,
    Clause,
    KGDocument,
    ParsedStructure,
    Point,
)
from ...domain.entity.enums import DocClass, DocStatus
from ...domain.errors import MetadataParseError
from ...domain.services.amendment_extractor import extract_amendments
from ...domain.services.citation_extractor import extract_citations
from ...domain.services.classifier import classify
from ...domain.services.metadata_parser import parse_metadata
from ...domain.services.text_normalizer import normalize_nfc, so_hieu_to_doc_id
from ..ports.graph_repository import GraphRepository
from ..ports.pdf_text_extractor import PDFTextExtractor

_ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "so": {"type": "integer"},
        "tieu_de": {"type": "string"},
        "noi_dung_full": {
            "type": "string",
            "description": "CHỈ điền khi Điều không có Khoản. Nếu có clauses thì để rỗng.",
        },
        "clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "so": {"type": "integer"},
                    "noi_dung": {"type": "string"},
                    "points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ky_hieu": {"type": "string"},
                                "noi_dung": {"type": "string"},
                            },
                            "required": ["ky_hieu", "noi_dung"],
                        },
                    },
                },
                "required": ["so", "noi_dung"],
            },
        },
    },
    "required": ["so"],
}

_STRUCTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "so": {"type": "integer"},
                    "tieu_de": {"type": "string"},
                    "articles": {"type": "array", "items": _ARTICLE_SCHEMA},
                },
                "required": ["so", "articles"],
            },
        },
        "articles": {"type": "array", "items": _ARTICLE_SCHEMA},
    },
    "required": ["chapters", "articles"],
}

_STRUCTURE_SYSTEM_PROMPT = """Bạn là hệ thống phân tích cấu trúc văn bản pháp luật Việt Nam.

Nhiệm vụ: Trích xuất cấu trúc phân cấp (Chương/Điều/Khoản/Điểm) thành JSON.

Quy tắc:
- chapters: danh sách Chương theo thứ tự. Nếu không có Chương → mảng rỗng [].
- articles: danh sách Điều không thuộc Chương nào. Nếu mọi Điều đều nằm trong Chương → mảng rỗng [].
- Mỗi Điều: so (số nguyên), tieu_de (tiêu đề hoặc chuỗi rỗng), clauses, và noi_dung_full.
- QUY TẮC noi_dung_full — TUYỆT ĐỐI KHÔNG LẶP LẠI nội dung Khoản:
  + Nếu Điều có đoạn DẪN NHẬP (lead-in) đứng TRƯỚC Khoản 1 (VD: "Trong Nghị định này, các từ ngữ dưới đây được hiểu như sau:"): đặt CHỈ phần lead-in đó vào noi_dung_full. KHÔNG kèm theo nội dung của các Khoản.
  + Nếu Điều bắt đầu ngay bằng Khoản 1, không có lead-in: noi_dung_full = "" (chuỗi rỗng).
  + Nếu Điều KHÔNG có Khoản nào (chỉ là 1 đoạn văn duy nhất): đặt toàn bộ nội dung vào noi_dung_full, clauses = [].
- Mỗi Khoản: so (số nguyên), noi_dung (nội dung đầy đủ của Khoản — có thể chứa text Điểm inline), points.
- Mỗi Điểm: ky_hieu (ký hiệu chữ cái: a, b, c, đ...), noi_dung.
- Giữ NGUYÊN VĂN nội dung, không tóm tắt, không diễn giải."""


def _stitch_article_text(intro: str, clauses: list[Clause]) -> str:
    """Stitch a flat Article.noi_dung_full from its lead-in + clauses.

    LLM no longer emits the full duplicated blob — it returns only the lead-in
    text (if any) and the structured clauses. Downstream services
    (citation/amendment extractors, Neo4j Article.nội_dung, classifier) still
    expect a flat blob, so we rebuild it here. clause.noi_dung is used as-is
    because the LLM already inlines point text inside it.
    """
    parts: list[str] = []
    if intro and intro.strip():
        parts.append(intro.rstrip())
    parts.extend(f"{c.so}. {c.noi_dung}".rstrip() for c in clauses)
    return "\n".join(parts)


def _build_structure(data: dict) -> ParsedStructure:
    art_order = 0

    def _point(p: dict, idx: int) -> Point:
        return Point(ky_hieu=p["ky_hieu"], noi_dung=p.get("noi_dung", ""), thu_tu=idx + 1)

    def _clause(c: dict, idx: int) -> Clause:
        return Clause(
            so=c["so"],
            noi_dung=c.get("noi_dung", ""),
            thu_tu=idx + 1,
            points=[_point(p, i) for i, p in enumerate(c.get("points") or [])],
        )

    def _article(a: dict) -> Article:
        nonlocal art_order
        art_order += 1
        clauses = [_clause(c, i) for i, c in enumerate(a.get("clauses") or [])]
        intro = a.get("noi_dung_full") or ""
        noi_dung_full = _stitch_article_text(intro, clauses) if clauses else intro
        return Article(
            so=a["so"],
            tieu_de=a.get("tieu_de") or None,
            noi_dung_full=noi_dung_full,
            thu_tu=art_order,
            clauses=clauses,
        )

    def _chapter(ch: dict) -> Chapter:
        return Chapter(
            so=ch["so"],
            tieu_de=ch.get("tieu_de") or None,
            articles=[_article(a) for a in ch.get("articles") or []],
        )

    return ParsedStructure(
        chapters=[_chapter(ch) for ch in data.get("chapters") or []],
        articles=[_article(a) for a in data.get("articles") or []],
    )

logger = logging.getLogger(__name__)


class IngestReport(BaseModel):
    doc_id: str
    so_hieu: str
    doc_class: DocClass
    n_articles: int
    n_clauses: int
    n_points: int
    n_amendments: int
    n_citations: int
    metadata_incomplete: bool
    loaded: bool


class IngestDocumentUseCase:
    """Use case: parse a legal PDF and load it into Neo4j (idempotent)."""

    def __init__(
        self,
        pdf_extractor: PDFTextExtractor,
        graph_repo: GraphRepository,
        llm_engine: LLMEngine,
    ) -> None:
        self._pdf = pdf_extractor
        self._repo = graph_repo
        self._llm = llm_engine

    async def execute(self, file_bytes: bytes, source_file: str) -> IngestReport:
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        # Step 1 — PDF → raw text (raises ScannedPDFError on image scans).
        raw = await self._pdf.extract(file_bytes, source_file)
        logger.info("[kg.ingest] extracted %d pages from %s", raw.total_pages, source_file)

        # Step 2 — metadata.
        metadata = parse_metadata(raw)
        if not metadata.so_hieu:
            raise MetadataParseError(f"Could not parse số hiệu from {source_file}")

        # Step 3 — structure via LLM.
        raw_structure = await self._llm.generate_structured_response(
            prompt=raw.full_text,
            response_schema=_STRUCTURE_SCHEMA,
            system_prompt=_STRUCTURE_SYSTEM_PROMPT,
        )
        structure = _build_structure(raw_structure)

        # Step 4 — classification.
        doc_class = classify(metadata, structure)

        # Step 7.1 — canonical doc_id.
        fallback_year = metadata.ngay_ban_hanh.year if metadata.ngay_ban_hanh else None
        doc_id = so_hieu_to_doc_id(metadata.so_hieu, fallback_year)
        if not doc_id:
            raise MetadataParseError(
                f"Could not derive doc_id from số hiệu '{metadata.so_hieu}'"
            )

        # Steps 5 & 6 — amendments + citations.
        amendments = extract_amendments(doc_id, structure, metadata, doc_class)
        citations = extract_citations(doc_id, structure)

        trang_thai = (
            DocStatus.SUA_DOI if doc_class == DocClass.SUA_DOI else DocStatus.HIEU_LUC
        )
        content_hash = hashlib.sha256(
            normalize_nfc(raw.full_text).encode("utf-8")
        ).hexdigest()

        kg_doc = KGDocument(
            doc_id=doc_id,
            metadata=metadata,
            structure=structure,
            doc_class=doc_class,
            trang_thai=trang_thai,
            content_hash=content_hash,
            source_file=source_file,
        )

        articles = structure.iter_articles()
        report = IngestReport(
            doc_id=doc_id,
            so_hieu=metadata.so_hieu,
            doc_class=doc_class,
            n_articles=len(articles),
            n_clauses=sum(len(a.clauses) for a in articles),
            n_points=sum(len(c.points) for a in articles for c in a.clauses),
            n_amendments=len(amendments),
            n_citations=len(citations),
            metadata_incomplete=metadata.incomplete,
            loaded=False,
        )

        # Step 8 — load (single transaction; placeholders minted inside repo).
        if self._repo.enabled:
            await self._repo.load_document(kg_doc, amendments, citations)
            report.loaded = True
            logger.info("[kg.ingest] loaded %s into Neo4j", doc_id)
        else:
            logger.warning("[kg.ingest] Neo4j disabled — parsed only, not loaded")

        return report
