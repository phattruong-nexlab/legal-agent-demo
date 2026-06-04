import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ...application.usecase.audit_legal_compliance import AuditLegalComplianceUseCase
from ...application.usecase.extract_legal_basis import ExtractLegalBasisUseCase
from ..dependencies import (
    get_audit_legal_compliance_usecase,
    get_extract_legal_basis_usecase,
)
from ..schemas import AuditLegalBasisResult, ExtractLegalBasisResponse, LegalBasisItem

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/extract-legal-basis", response_model=ExtractLegalBasisResponse)
async def extract_legal_basis(
    file: UploadFile = File(...),
    usecase: ExtractLegalBasisUseCase = Depends(get_extract_legal_basis_usecase),
) -> ExtractLegalBasisResponse:
    """Extract legal bases cited on the first page of a PDF."""
    logger.info(f"[extract-legal-basis] Start - file: {file.filename}")
    file_bytes = await file.read()
    result = await usecase.execute(file_bytes)
    legal_bases = result.get("legal_bases") if isinstance(result, dict) else None
    count = len(legal_bases) if isinstance(legal_bases, list) else 0
    logger.info(f"[extract-legal-basis] Done - laws: {count}")
    return result


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
        raise HTTPException(
            status_code=400, detail="Invalid audited_document fields"
        ) from exc


@router.post("/audit-legal-basis", response_model=list[AuditLegalBasisResult])
async def audit_legal_basis(
    file: UploadFile = File(...),
    audited_document: str = Form(
        ..., description='JSON object of {law_number, law_name, date} for audited document'
    ),
    legal_bases: str = Form(..., description='JSON array of {law_number, law_name, date}'),
    usecase: AuditLegalComplianceUseCase = Depends(get_audit_legal_compliance_usecase),
) -> list[AuditLegalBasisResult]:
    """
    Audit compliance of a document against legal bases.

    `audited_document` must be a JSON string: object with law_number, law_name, date.
    `legal_bases` must be a JSON string: list of objects with law_number, law_name, date.
    Matching uses law_number (if present) or law_name as the primary fuzzy signal, with date as a confirming signal.
    """
    logger.info(f"[audit-legal-basis] Start - file: {file.filename}")
    file_bytes = await file.read()
    audited_item = _parse_legal_basis_item(audited_document)
    legal_items = _parse_legal_bases(legal_bases)
    result = await usecase.execute(
        file_bytes,
        [item.model_dump() for item in legal_items],
        audited_item.model_dump(),
    )
    logger.info(f"[audit-legal-basis] Done - items: {len(result)}")
    return result
