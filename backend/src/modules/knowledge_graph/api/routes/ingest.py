import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ...application.usecase.ingest_document import IngestDocumentUseCase
from ...domain.errors import (
    MetadataParseError,
    Neo4jLoadError,
    PDFParseError,
    ScannedPDFError,
    StructureValidationError,
)
from ..dependencies import get_ingest_usecase
from ..schemas import BatchIngestReport, FileIngestResult

logger = logging.getLogger(__name__)
router = APIRouter()

_KNOWN_ERRORS = (
    ScannedPDFError,
    StructureValidationError,
    MetadataParseError,
    PDFParseError,
    Neo4jLoadError,
)


@router.post("/ingest", response_model=BatchIngestReport)
async def ingest_documents(
    files: list[UploadFile] = File(..., description="Vietnamese legal document PDFs"),
    usecase: IngestDocumentUseCase = Depends(get_ingest_usecase),
) -> BatchIngestReport:
    """Parse one or more legal PDFs and load them into the Neo4j knowledge graph.

    Idempotent: re-ingesting the same document MERGEs onto the same nodes.
    Files that fail are reported individually; other files in the batch still proceed.
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one file is required.")

    results: list[FileIngestResult] = []

    for upload in files:
        filename = upload.filename or "uploaded.pdf"
        logger.info("[kg.ingest] start - file: %s", filename)
        file_bytes = await upload.read()

        try:
            report = await usecase.execute(file_bytes, filename)
            logger.info("[kg.ingest] done - %s (loaded=%s)", report.doc_id, report.loaded)
            results.append(FileIngestResult(filename=filename, success=True, report=report))
        except _KNOWN_ERRORS as exc:
            logger.warning("[kg.ingest] failed - %s: %s", filename, exc)
            results.append(FileIngestResult(filename=filename, success=False, error=str(exc)))

    succeeded = sum(1 for r in results if r.success)
    return BatchIngestReport(
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=results,
    )
