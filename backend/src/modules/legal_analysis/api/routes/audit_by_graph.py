import json
import logging

from fastapi import APIRouter, Depends, Form, HTTPException

from ...application.usecase.audit_by_graph import AuditByGraphUseCase
from ..dependencies import get_audit_by_graph_usecase
from ..schemas import AuditByGraphResponse, DocumentSegment, LegalBasisItem

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_legal_bases(payload: str) -> list[LegalBasisItem]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid legal_bases JSON") from exc

    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="legal_bases must be a list")

    try:
        return [LegalBasisItem.model_validate(item) for item in data]
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid legal_bases items") from exc


def _parse_legal_basis_item(payload: str) -> LegalBasisItem:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid audited_document JSON") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="audited_document must be an object")

    try:
        return LegalBasisItem.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid audited_document fields") from exc


def _parse_segments(payload: str) -> list[DocumentSegment]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid segments JSON") from exc

    if not isinstance(data, list) or not data:
        raise HTTPException(status_code=400, detail="segments must be a non-empty list")

    try:
        return [DocumentSegment.model_validate(item) for item in data]
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid segments items") from exc


@router.post("/audit-by-graph", response_model=AuditByGraphResponse)
async def audit_by_graph(
    audited_document: str = Form(
        ..., description="JSON object of {law_number, law_name, date} for the audited document"
    ),
    legal_bases: str = Form(..., description="JSON array of {law_number, law_name, date}"),
    segments: str = Form(
        ..., description="JSON array of segments from /extract-segments (đơn vị cấu trúc input)"
    ),
    usecase: AuditByGraphUseCase = Depends(get_audit_by_graph_usecase),
) -> AuditByGraphResponse:
    """Audit tuân thủ dựa trên Knowledge Graph, đối chiếu theo từng đơn vị cấu trúc.

    Nhận sẵn các segment (Chương/Điều) đã trích từ /extract-segments — KHÔNG convert
    lại file. Với mỗi (segment × căn cứ) gọi 1 LLM call (chạy song song có giới hạn),
    đánh giá theo hướng khoan dung, rồi gom thành trạng thái tổng cho từng căn cứ.
    """
    audited_item = _parse_legal_basis_item(audited_document)
    legal_items = _parse_legal_bases(legal_bases)
    segment_items = _parse_segments(segments)
    logger.info(
        "[audit-by-graph] Start - %d segments, %d bases",
        len(segment_items), len(legal_items),
    )
    result = await usecase.execute(
        [s.model_dump() for s in segment_items],
        [item.model_dump() for item in legal_items],
        audited_item.model_dump(),
    )
    logger.info("[audit-by-graph] Done - items: %d", len(result.get("results", [])))
    return result
