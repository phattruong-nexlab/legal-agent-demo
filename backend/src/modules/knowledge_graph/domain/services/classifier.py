"""Step 4 — classify a document as gốc / sửa đổi / hợp nhất / bãi bỏ."""

from __future__ import annotations

from ..entity.document import DocumentMetadata, ParsedStructure
from ..entity.enums import DocClass


def classify(metadata: DocumentMetadata, structure: ParsedStructure) -> DocClass:
    name = (metadata.ten or "").lower()

    if "hợp nhất" in name:
        return DocClass.HOP_NHAT
    if "bãi bỏ" in name and "sửa đổi" not in name:
        return DocClass.BAI_BO
    if "sửa đổi" in name or "bổ sung" in name:
        return DocClass.SUA_DOI

    articles = structure.iter_articles()
    if articles:
        head = (articles[0].tieu_de or "") + " " + articles[0].noi_dung_full[:200]
        head = head.lower()
        if "sửa đổi" in head or "bổ sung" in head:
            return DocClass.SUA_DOI
        if "bãi bỏ" in head:
            return DocClass.BAI_BO

    return DocClass.GOC
