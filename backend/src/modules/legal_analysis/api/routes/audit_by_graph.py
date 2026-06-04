import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ...application.usecase.audit_by_graph import AuditByGraphUseCase
from ..dependencies import get_audit_by_graph_usecase
from ..schemas import AuditByGraphResult, LegalBasisItem

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


@router.post("/audit-by-graph", response_model=list[AuditByGraphResult])
async def audit_by_graph(
    file: UploadFile = File(...),
    audited_document: str = Form(
        ..., description="JSON object of {law_number, law_name, date} for the audited document"
    ),
    legal_bases: str = Form(..., description="JSON array of {law_number, law_name, date}"),
    usecase: AuditByGraphUseCase = Depends(get_audit_by_graph_usecase),
) -> list[AuditByGraphResult]:
    """
    Audit compliance using the Knowledge Graph as reference.

    For each legal basis, fetches all Article nodes from Neo4j and checks compliance
    per article in parallel. Returns per-article breakdown and an aggregated overall status.

    Overall status rules:
    - "Không tuân thủ" if any applicable article is non-compliant
    - "Cần kiểm tra" if any applicable article needs review (and none are non-compliant)
    - "Tuân thủ" if all applicable articles are compliant
    """
    logger.info(f"[audit-by-graph] Start - file: {file.filename}")
    file_bytes = await file.read()
    audited_item = _parse_legal_basis_item(audited_document)
    legal_items = _parse_legal_bases(legal_bases)
    result = await usecase.execute(
        file_bytes,
        [item.model_dump() for item in legal_items],
        audited_item.model_dump(),
    )
    logger.info(f"[audit-by-graph] Done - items: {len(result)}")
    return result
