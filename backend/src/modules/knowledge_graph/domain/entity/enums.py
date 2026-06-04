"""Fixed taxonomies for the legal knowledge graph.

These enums are part of the canonical Neo4j schema described in
LEGAL_KG_PIPELINE.md section 3 and MUST NOT be changed casually.
"""

from enum import Enum


class DocTypeCode(str, Enum):
    """Loại văn bản (document type) — stable code used in node ids."""

    LUAT = "LUAT"  # Luật / Bộ luật
    NQ = "NQ"  # Nghị quyết
    ND = "ND"  # Nghị định
    TT = "TT"  # Thông tư
    QD = "QD"  # Quyết định
    CT = "CT"  # Chỉ thị
    PL = "PL"  # Pháp lệnh
    UNKNOWN = "UNKNOWN"


# Human-readable Vietnamese label per document type, stored on :DocumentType.
DOC_TYPE_LABEL: dict[DocTypeCode, str] = {
    DocTypeCode.LUAT: "Luật",
    DocTypeCode.NQ: "Nghị quyết",
    DocTypeCode.ND: "Nghị định",
    DocTypeCode.TT: "Thông tư",
    DocTypeCode.QD: "Quyết định",
    DocTypeCode.CT: "Chỉ thị",
    DocTypeCode.PL: "Pháp lệnh",
    DocTypeCode.UNKNOWN: "Không xác định",
}


class DocStatus(str, Enum):
    """trạng_thái — lifecycle status of a document."""

    HIEU_LUC = "HIEU_LUC"
    HET_HIEU_LUC = "HET_HIEU_LUC"
    SUA_DOI = "SUA_DOI"
    CHUA_HIEU_LUC = "CHUA_HIEU_LUC"
    PLACEHOLDER = "PLACEHOLDER"


class DocClass(str, Enum):
    """phân_loại_vb — structural classification of a document."""

    GOC = "GOC"  # văn bản gốc
    SUA_DOI = "SUA_DOI"  # văn bản sửa đổi/bổ sung
    HOP_NHAT = "HOP_NHAT"  # văn bản hợp nhất
    BAI_BO = "BAI_BO"  # văn bản bãi bỏ


class ScopeType(str, Enum):
    """Granularity that a lifecycle relationship targets."""

    DOCUMENT = "DOCUMENT"
    ARTICLE = "ARTICLE"
    CLAUSE = "CLAUSE"
    POINT = "POINT"
    APPENDIX = "APPENDIX"
    PHRASE = "PHRASE"


class RelationType(str, Enum):
    """Lifecycle / citation relationship types (section 3.4)."""

    AMENDS = "AMENDS"
    REPEALS = "REPEALS"
    REPLACES = "REPLACES"
    SUPERSEDES = "SUPERSEDES"
    CONSOLIDATES = "CONSOLIDATES"
    GUIDED_BY = "GUIDED_BY"
    DETAILS = "DETAILS"
    BASED_ON = "BASED_ON"
    REFERENCES = "REFERENCES"
