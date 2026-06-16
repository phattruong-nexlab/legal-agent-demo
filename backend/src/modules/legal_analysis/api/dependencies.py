from fastapi import Depends

from src.shared.infrastructure.llm_engine.gemini_engine import GeminiEngine
from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.pytesseract_engine import PyTesseractEngine

from ..application.usecase.audit_by_graph import AuditByGraphUseCase
from ..application.usecase.audit_legal_compliance import AuditLegalComplianceUseCase
from ..application.usecase.extract_legal_basis import ExtractLegalBasisUseCase
from ..application.usecase.extract_segments import ExtractSegmentsUseCase
from ..application.usecase.get_document_relations import GetDocumentRelationsUseCase
from ..application.usecase.query_article_status import QueryArticleStatusUseCase


def get_llm_engine() -> LLMEngine:
    return GeminiEngine()


def get_tesseract_ocr_engine() -> PyTesseractEngine:
    return PyTesseractEngine()


def get_extract_legal_basis_usecase(
    llm_engine: LLMEngine = Depends(get_llm_engine),
    ocr_engine: PyTesseractEngine = Depends(get_tesseract_ocr_engine),
) -> ExtractLegalBasisUseCase:
    return ExtractLegalBasisUseCase(llm_engine=llm_engine, ocr_engine=ocr_engine)


def get_audit_legal_compliance_usecase(
    llm_engine: LLMEngine = Depends(get_llm_engine),
    ocr_engine: PyTesseractEngine = Depends(get_tesseract_ocr_engine),
) -> AuditLegalComplianceUseCase:
    return AuditLegalComplianceUseCase(llm_engine=llm_engine, ocr_engine=ocr_engine)


def get_extract_segments_usecase(
    llm_engine: LLMEngine = Depends(get_llm_engine),
    ocr_engine: PyTesseractEngine = Depends(get_tesseract_ocr_engine),
) -> ExtractSegmentsUseCase:
    return ExtractSegmentsUseCase(llm_engine=llm_engine, ocr_engine=ocr_engine)


def get_audit_by_graph_usecase(
    llm_engine: LLMEngine = Depends(get_llm_engine),
) -> AuditByGraphUseCase:
    return AuditByGraphUseCase(llm_engine=llm_engine)


def get_document_relations_usecase(
    llm_engine: LLMEngine = Depends(get_llm_engine),
    ocr_engine: PyTesseractEngine = Depends(get_tesseract_ocr_engine),
) -> GetDocumentRelationsUseCase:
    return GetDocumentRelationsUseCase(llm_engine=llm_engine, ocr_engine=ocr_engine)


def get_query_article_status_usecase(
    llm_engine: LLMEngine = Depends(get_llm_engine),
) -> QueryArticleStatusUseCase:
    return QueryArticleStatusUseCase(llm_engine=llm_engine)
