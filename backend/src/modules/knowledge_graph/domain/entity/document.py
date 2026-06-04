"""Core legal-document entities.

Code identifiers are English; the Vietnamese domain tokens (Điều/Khoản/Điểm)
are preserved verbatim inside the canonical node-id strings because the Neo4j
schema in LEGAL_KG_PIPELINE.md mandates them exactly.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .enums import DocClass, DocStatus, DocTypeCode


# --- Node-id builders (canonical formats, section 3.2 / 3.3) ----------------


def make_article_id(doc_id: str, so: int) -> str:
    return f"{doc_id}#điều-{so}"


def make_clause_id(article_id: str, so: int) -> str:
    return f"{article_id}#khoản-{so}"


def make_point_id(clause_id: str, ky_hieu: str) -> str:
    return f"{clause_id}#điểm-{ky_hieu}"


# --- Raw extraction ---------------------------------------------------------


class RawPage(BaseModel):
    page_num: int
    text: str


class RawDocument(BaseModel):
    """Output of step 1 (PDF → raw text)."""

    source_file: str
    extracted_at: datetime
    pages: list[RawPage]
    total_pages: int

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)


# --- Metadata (step 2) ------------------------------------------------------


class LegalBasisRef(BaseModel):
    """One entry of `căn cứ pháp lý` cited in the preamble."""

    so_hieu: str = ""
    ngay: date | None = None


class DocumentMetadata(BaseModel):
    so_hieu: str = ""
    loai_code: DocTypeCode = DocTypeCode.UNKNOWN
    loai: str = ""
    ten: str = ""
    ten_ngan: str | None = None
    aliases: list[str] = Field(default_factory=list)
    ngay_ban_hanh: date | None = None
    ngay_hieu_luc: date | None = None
    ngay_het_hieu_luc: date | None = None
    co_quan_ban_hanh: str = ""
    nguoi_ky: str = ""
    chuc_vu_nguoi_ky: str = ""
    linh_vuc: list[str] = Field(default_factory=list)
    can_cu_phap_ly: list[LegalBasisRef] = Field(default_factory=list)
    incomplete: bool = False


# --- Structure (step 3) -----------------------------------------------------


class Point(BaseModel):
    """Điểm (a, b, c...)."""

    ky_hieu: str
    noi_dung: str = ""
    thu_tu: int


class Clause(BaseModel):
    """Khoản (1, 2, 3...)."""

    so: int
    noi_dung: str = ""
    thu_tu: int
    points: list[Point] = Field(default_factory=list)


class Article(BaseModel):
    """Điều."""

    so: int
    tieu_de: str | None = None
    noi_dung_full: str = ""
    thu_tu: int
    clauses: list[Clause] = Field(default_factory=list)


class Section(BaseModel):
    """Mục."""

    so: int
    tieu_de: str | None = None
    articles: list[Article] = Field(default_factory=list)


class Chapter(BaseModel):
    """Chương."""

    so: int
    tieu_de: str | None = None
    sections: list[Section] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)


class ParsedStructure(BaseModel):
    """Output of step 3. `articles` is the root list when there is no chapter."""

    chapters: list[Chapter] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)

    def iter_articles(self) -> list[Article]:
        """Flatten every Article regardless of nesting depth."""
        out: list[Article] = list(self.articles)
        for ch in self.chapters:
            out.extend(ch.articles)
            for sec in ch.sections:
                out.extend(sec.articles)
        return sorted(out, key=lambda a: a.thu_tu)


# --- Aggregate --------------------------------------------------------------


class KGDocument(BaseModel):
    """Fully parsed document ready to be loaded into Neo4j."""

    doc_id: str
    metadata: DocumentMetadata
    structure: ParsedStructure
    doc_class: DocClass = DocClass.GOC
    trang_thai: DocStatus = DocStatus.HIEU_LUC
    content_hash: str = ""
    source_file: str = ""
    nguon_url: str | None = None
    ngon_ngu: str = "vi"
    version: int = 1
