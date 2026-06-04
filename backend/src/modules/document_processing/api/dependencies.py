from fastapi import Depends

from src.shared.infrastructure.llm_engine.gemini_engine import GeminiEngine
from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine
from src.shared.infrastructure.ocr_engine.pytesseract_engine import PyTesseractEngine

from ....config import get_settings
from ..application.usecase.convert_to_markdown import ConvertToMarkdownUseCase


def get_llm_engine() -> LLMEngine:
    settings = get_settings()
    return GeminiEngine()


def get_tesseract_ocr_engine() -> PyTesseractEngine:
    return PyTesseractEngine()


def get_convert_to_markdown_usecase(
    llm_engine: LLMEngine = Depends(get_llm_engine),
    ocr_engine: PyTesseractEngine = Depends(get_tesseract_ocr_engine),
) -> ConvertToMarkdownUseCase:
    return ConvertToMarkdownUseCase(llm_engine=llm_engine, ocr_engine=ocr_engine)
