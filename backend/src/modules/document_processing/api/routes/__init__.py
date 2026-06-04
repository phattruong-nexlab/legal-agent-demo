from fastapi import APIRouter

from .convert import router as convert_markdown_router

document_processing_router = APIRouter(prefix="/legal-analysis")

document_processing_router.include_router(convert_markdown_router, tags=["convert-markdown"])
