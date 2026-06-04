import asyncio
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.shared.infrastructure.persistence.gcs_storage import upload_text_to_bucket

from ...application.usecase.convert_to_markdown import ConvertToMarkdownUseCase
from ..dependencies import get_convert_to_markdown_usecase

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/convert-to-markdown")
async def convert_to_markdown(
    files: List[UploadFile] = File(...),
    max_concurrent: int = Query(default=3, ge=1, le=20, description="Maximum number of files processed concurrently"),
    usecase: ConvertToMarkdownUseCase = Depends(get_convert_to_markdown_usecase),
) -> JSONResponse:
    """
    Convert one or more PDF files to Markdown content.

    Uses OCR engine to extract the full file, then LLM to generate clean Markdown.
    Use `max_concurrent` to control how many files are processed at the same time.
    """
    settings = get_settings()
    semaphore = asyncio.Semaphore(max_concurrent)

    logger.info(
        f"[convert-to-markdown] Start - {len(files)} file(s), max_concurrent={max_concurrent}"
    )

    async def _process_file(file: UploadFile) -> dict:
        async with semaphore:
            logger.info(f"[convert-to-markdown] Processing: {file.filename}")
            try:
                file_bytes = await file.read()

                markdown_content, doc_metadata = await asyncio.gather(
                    usecase.execute(file_bytes, None, None),
                    usecase.extract_document_metadata(file_bytes),
                )

                blob_name = f"{uuid.uuid4()}.md"
                await asyncio.to_thread(
                    upload_text_to_bucket,
                    bucket_name=settings.LEGAL_BUCKET,
                    blob_name=blob_name,
                    content=markdown_content,
                    content_type="text/markdown; charset=utf-8",
                    project_id=settings.GCP_PROJECT_ID,
                    metadata={
                        "law_number": doc_metadata.get("law_number", ""),
                        "law_name": doc_metadata.get("law_name", ""),
                        "date": doc_metadata.get("date", ""),
                    },
                )
                logger.info(
                    f"[convert-to-markdown] Done: {file.filename} -> {settings.LEGAL_BUCKET}/{blob_name} ({len(markdown_content)} chars)"
                )
                return {
                    "filename": file.filename,
                    "blob_name": blob_name,
                    "status": "success",
                    "content": markdown_content,
                    "metadata": doc_metadata,
                }
            except Exception as exc:
                logger.error(
                    f"[convert-to-markdown] Failed: {file.filename} - {exc}", exc_info=True
                )
                return {
                    "filename": file.filename,
                    "status": "error",
                    "error": str(exc),
                }

    results = await asyncio.gather(*[_process_file(f) for f in files])

    logger.info(
        f"[convert-to-markdown] Finished - {sum(1 for r in results if r['status'] == 'success')}/{len(results)} succeeded"
    )
    return JSONResponse(content={"results": results})
