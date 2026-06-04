from pydantic import BaseModel, Field


class LegalBasisItem(BaseModel):
	"""One legal basis cited on the first page."""

	law_number: str = Field("", description="Document number/identifier, e.g. 58/2023/NĐ-CP")
	law_name: str = Field("", description="Official title/name of the legal document")
	date: str = Field("", description="Promulgation date or empty if unknown")


class ExtractLegalBasisResponse(BaseModel):
	"""Extraction result with the queried document and its legal bases."""

	document: LegalBasisItem = Field(
		..., description="Document being analyzed, if identifiable on the first page"
	)
	legal_bases: list[LegalBasisItem] = Field(
		..., description="Legal bases cited on the first page"
	)


class AuditLegalBasisResult(BaseModel):
	"""Audit result for one legal basis item."""

	audited_law: str = Field(..., description="law_number if both fields provided, otherwise whichever field was given")
	date: str = Field(..., description="Promulgation date or empty if unknown")
	status: str = Field(
		...,
		description=(
			"Tuân thủ | Không tuân thủ | Cần kiểm tra | Không tìm thấy trong hệ thống"
		),
	)
	explanation: str = Field(
		"", description="Explanation of the compliance status"
	)
	matched_blob: str | None = Field(
		None, description="Matched blob name in GCS, if any"
	)


class ArticleComplianceResult(BaseModel):
    """Compliance result for a single Article node from the Knowledge Graph."""

    article_id: str = Field(..., description="Canonical article node ID in the KG")
    article_number: int = Field(..., description="Article number (Điều số)")
    article_title: str = Field("", description="Article title (tiêu đề)")
    applicable: bool = Field(..., description="Whether this article applies to the audited document")
    status: str = Field(
        ...,
        description="Tuân thủ | Không tuân thủ | Cần kiểm tra | Không liên quan",
    )
    explanation: str = Field("", description="LLM explanation for the compliance decision")


class AuditByGraphResult(BaseModel):
    """Audit result for one legal basis, with per-article breakdown."""

    audited_law: str = Field(..., description="law_number if present, else law_name")
    date: str = Field(..., description="Promulgation date or empty")
    matched_doc_id: str | None = Field(None, description="Matched KG Document node ID")
    overall_status: str = Field(
        ...,
        description=(
            "Aggregated status: Tuân thủ | Không tuân thủ | Cần kiểm tra | "
            "Không liên quan | Không tìm thấy trong hệ thống"
        ),
    )
    explanation: str = Field("", description="Top-level explanation (populated on error or no-match cases)")
    articles: list[ArticleComplianceResult] = Field(
        default_factory=list, description="Per-article compliance results"
    )


class LegalDocumentRelation(BaseModel):
	"""Relationship between a document and a related legal document."""

	relationship: str = Field(..., description="Neo4j relationship type")
	direction: str = Field(..., description="Direction relative to the input document")
	law_number: str = Field("", description="Related document number/identifier")
	law_name: str = Field("", description="Related document title/name")
	date: str = Field("", description="Related document promulgation date")


class DocumentRelationsResponse(BaseModel):
	"""Response for the document-relations endpoint."""

	document: LegalBasisItem = Field(..., description="Identified document from the first page")
	relations: list[LegalDocumentRelation] = Field(..., description="Neo4j relations for the document")


class QueryArticleStatusRequest(BaseModel):
    """Natural-language reverse-query request."""

    question: str = Field(
        ...,
        description="A free-text question, e.g. 'Điều 18 Thông tư 08/2022 còn hiệu lực không?'",
        min_length=1,
    )


class QueryParseResult(BaseModel):
    """Structured parameters parsed from the natural-language question."""

    law_number: str = Field("", description="Document số hiệu extracted from the question")
    law_name: str = Field("", description="Document name/type extracted from the question")
    article_so: int | None = Field(None, description="Article number")
    clause_so: int | None = Field(None, description="Clause number, if mentioned")
    point_kyhieu: str = Field("", description="Point letter (a/b/c/...), if mentioned")
    intent: str = Field("other", description="status | content | amendments | other")


class QueryDocumentInfo(BaseModel):
    """Matched Document node summary."""

    doc_id: str
    so_hieu: str
    ten: str = ""
    loai: str = ""
    ngay_ban_hanh: str = ""
    ngay_hieu_luc: str = ""
    ngay_het_hieu_luc: str = ""
    trang_thai: str = ""


class QueryArticlePoint(BaseModel):
    ky_hieu: str = ""
    noi_dung: str = ""
    thu_tu: int | None = None


class QueryArticleClause(BaseModel):
    so: int | None = None
    noi_dung: str = ""
    thu_tu: int | None = None
    points: list[QueryArticlePoint] = Field(default_factory=list)


class QueryArticleInfo(BaseModel):
    id: str
    so: int
    tieu_de: str = ""
    noi_dung: str = ""
    clauses: list[QueryArticleClause] = Field(default_factory=list)


class QueryLifecycleRelation(BaseModel):
    """One inbound lifecycle relationship from another Document."""

    rel_type: str = Field(..., description="AMENDS | REPEALS | REPLACES")
    src_doc_id: str = ""
    src_so_hieu: str = ""
    src_ten: str = ""
    src_ngay_ban_hanh: str = ""
    src_trang_thai: str = ""
    scope: str = ""
    scope_type: str = ""
    target_article: int | None = None
    target_clause: int | None = None
    target_point: str | None = None
    effective_from: str = ""


class QueryArticleStatusResponse(BaseModel):
    """Response for the reverse-query endpoint."""

    question: str
    parsed: QueryParseResult
    document: QueryDocumentInfo | None = None
    article: QueryArticleInfo | None = None
    amendments: list[QueryLifecycleRelation] = Field(default_factory=list)
    answer: str = Field("", description="LLM-synthesized natural-language answer")
