"""Gemini-based PDF extractor — handles scanned / image-only PDFs.

Follows the same pattern as ExtractLegalBasisUseCase: use OCREngine to
extract page bytes, then pass them to LLMEngine (Gemini vision) for text
extraction. Plain text output (no Markdown) is required so that the
regex-based domain services (structure_parser, metadata_parser) work correctly.
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine

from ...domain.entity.document import RawDocument, RawPage
from ...domain.errors import PDFParseError, ScannedPDFError
from ...domain.services.text_normalizer import normalize_nfc
from .pdfplumber_extractor import PdfPlumberExtractor

logger = logging.getLogger(__name__)

_KG_EXTRACT_PROMPT = """
You are a text extraction engine for Vietnamese legal documents.

Task: Extract the COMPLETE text of this PDF document exactly as written.

Rules (STRICT):
- Output the complete text preserving original Vietnamese characters (diacritics).
- Preserve all structural markers exactly: "Chương I", "Điều 1.", "Khoản 1.", "Điểm a)", etc.
- Keep original numbering and punctuation ("Điều 1.", not "Điều 1:").
- Preserve original line breaks and paragraph separations.
- Do NOT add any Markdown formatting (no #, ##, **, -, >, ```, etc.).
- Do NOT summarize, paraphrase, translate, or add commentary.
- If a portion is unreadable, output [UNREADABLE] in place of that text.
- Output ONLY the extracted plain text — nothing else.
"""


class GeminiPdfExtractor:
    """PDF text extractor using Gemini vision — works for scanned / image-only PDFs."""

    def __init__(self, llm_engine: LLMEngine, ocr_engine: OCREngine) -> None:
        self._llm = llm_engine
        self._ocr = ocr_engine

    async def extract(self, file_bytes: bytes, source_file: str) -> RawDocument:
        if not file_bytes:
            raise PDFParseError("Empty PDF bytes")

        total_pages = await self._ocr.get_page_count(file_bytes)

        # Page 1 separately — metadata_parser reads raw.pages[0].text as "first page".
        page1_bytes = await self._ocr.extract_pages(file_bytes, (1, 1))

        logger.info(
            "[gemini-extractor] sending PDF to Gemini (%d pages, source=%s)",
            total_pages,
            source_file,
        )
        page1_text, full_text = await _gather(
            self._llm.generate_response_with_pdf(_KG_EXTRACT_PROMPT, page1_bytes),
            self._llm.generate_response_with_pdf(_KG_EXTRACT_PROMPT, file_bytes),
        )

        page1_text = normalize_nfc(page1_text or "")
        full_text = normalize_nfc(full_text or "")

        if not full_text.strip():
            raise PDFParseError(
                f"{source_file}: Gemini returned no text — document may be unreadable"
            )

        # Store page 1 as pages[0] (used by metadata_parser) and full document as
        # pages[1] so that RawDocument.full_text contains the complete content.
        pages = [
            RawPage(page_num=1, text=page1_text),
            RawPage(page_num=2, text=full_text),
        ]

        return RawDocument(
            source_file=source_file,
            extracted_at=datetime.utcnow(),
            pages=pages,
            total_pages=total_pages,
        )


class SmartPdfExtractor:
    """Tries pdfplumber text extraction first; falls back to Gemini vision for scanned PDFs."""

    def __init__(self, llm_engine: LLMEngine, ocr_engine: OCREngine) -> None:
        self._text_extractor = PdfPlumberExtractor()
        self._gemini_extractor = GeminiPdfExtractor(llm_engine, ocr_engine)

    async def extract(self, file_bytes: bytes, source_file: str) -> RawDocument:
        try:
            return await self._text_extractor.extract(file_bytes, source_file)
        except ScannedPDFError:
            logger.info(
                "[smart-extractor] no text layer in '%s' — falling back to Gemini vision",
                source_file,
            )
            return await self._gemini_extractor.extract(file_bytes, source_file)


async def _gather(*coros):
    """Run coroutines concurrently and return results in order."""
    import asyncio
    return await asyncio.gather(*coros)
