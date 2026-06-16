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


class DocumentSegment(BaseModel):
    """Một đơn vị cấu trúc lớn nhất của văn bản đầu vào (Chương/Điều/Toàn văn)."""

    unit_type: str = Field(..., description="Loại đơn vị: Chương | Điều | Toàn văn")
    index: int = Field(..., description="Số thứ tự segment (1-based)")
    label: str = Field(..., description="Nhãn hiển thị, ví dụ 'Chương I — Quy định chung'")
    content: str = Field("", description="Nội dung text của segment (đưa vào audit)")


class ExtractSegmentsResponse(BaseModel):
    """Kết quả trích cấu trúc văn bản đầu vào."""

    unit_type: str = Field(..., description="Đơn vị cấu trúc lớn nhất được dùng")
    segments: list[DocumentSegment] = Field(default_factory=list)


class SegmentComplianceResult(BaseModel):
    """Kết quả tuân thủ của một segment input đối với một căn cứ."""

    segment_index: int | None = Field(None, description="Số thứ tự segment")
    segment_label: str = Field("", description="Nhãn segment")
    applicable: bool = Field(..., description="Segment có thuộc phạm vi điều chỉnh không")
    status: str = Field(
        ...,
        description="Tuân thủ | Không tuân thủ | Cần kiểm tra | Không liên quan",
    )
    reason: str = Field("", description="Lý do/giải thích ngắn cho kết luận")


class AuditByGraphResult(BaseModel):
    """Audit result for one legal basis, with per-segment breakdown."""

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
    segments: list[SegmentComplianceResult] = Field(
        default_factory=list, description="Per-segment compliance results"
    )


class AuditByGraphResponse(BaseModel):
    """Toàn bộ kết quả audit: đơn vị cấu trúc + kết quả theo từng căn cứ."""

    unit_type: str = Field(..., description="Đơn vị cấu trúc input được đối chiếu")
    results: list[AuditByGraphResult] = Field(default_factory=list)


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
