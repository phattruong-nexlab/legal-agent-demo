"""Lifecycle (amendment) and citation entities — steps 5 & 6."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .enums import RelationType, ScopeType


class Amendment(BaseModel):
    """One lifecycle instruction emitted by an amending document.

    `target_doc_id` is filled in step 7 once the target số hiệu is resolved
    (or a PLACEHOLDER node is minted).
    """

    type: RelationType
    source_clause_id: str
    target_doc_so_hieu: str
    target_doc_id: str | None = None
    scope: str = ""
    scope_type: ScopeType = ScopeType.DOCUMENT
    target_article: int | None = None
    target_clause: int | None = None
    target_point: str | None = None
    new_content: str = ""
    effective_from: date | None = None
    from_llm: bool = False  # flagged for manual review when True


class Citation(BaseModel):
    """A reference (not a modification) from one element to another doc/article."""

    source_id: str  # Article/Clause id that contains the citation
    target_so_hieu: str = ""  # external document, if any
    target_doc_id: str | None = None
    target_article: int | None = None
    target_clause: int | None = None
    is_internal: bool = False  # "... Quy chế này"
    raw_text: str = ""


class ResolvedTarget(BaseModel):
    """Result of resolving a citation/amendment target against the graph."""

    so_hieu: str
    doc_id: str
    is_placeholder: bool = False
