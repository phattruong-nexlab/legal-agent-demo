import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.config import get_settings

from ..dependencies import get_document_relations_usecase
from ..schemas import DocumentRelationsResponse, LegalDocumentRelation
from ...application.usecase.get_document_relations import GetDocumentRelationsUseCase

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/document-relations", response_model=DocumentRelationsResponse)
async def document_relations(
    file: UploadFile = File(..., description="A Vietnamese legal document PDF"),
    usecase: GetDocumentRelationsUseCase = Depends(get_document_relations_usecase),
) -> DocumentRelationsResponse:
    """Identify the document from the first page of a PDF, then lookup its Neo4j relationships."""
    settings = get_settings()
    if not settings.NEO4J_URI:
        raise HTTPException(status_code=503, detail="Neo4j is not configured")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=422, detail="Empty file")

    logger.info("[document-relations] start - file: %s", file.filename)
    document, relations = await usecase.execute(file_bytes)

    if not document.get("law_number") and not document.get("law_name"):
        raise HTTPException(
            status_code=422,
            detail="Could not identify the document from the first page of the PDF.",
        )

    return DocumentRelationsResponse(
        document=document,
        relations=[LegalDocumentRelation(**r) for r in relations],
    )
