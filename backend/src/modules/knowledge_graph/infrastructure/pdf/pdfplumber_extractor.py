"""Step 1 adapter — PDF → RawDocument.

pdfplumber first (better reading order for Vietnamese legal layout); PyMuPDF
(fitz) as a fallback. Empty text on every page ⇒ image scan ⇒ ScannedPDFError
(no auto-OCR in Phase 1, section 0).
"""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import datetime

import pdfplumber

from ...domain.entity.document import RawDocument, RawPage
from ...domain.errors import PDFParseError, ScannedPDFError
from ...domain.services.text_normalizer import normalize_nfc

logger = logging.getLogger(__name__)


class PdfPlumberExtractor:
    """Concrete `PDFTextExtractor` (see application.ports.pdf_text_extractor)."""

    def _extract_sync(self, file_bytes: bytes) -> list[RawPage]:
        pages: list[RawPage] = []
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    pages.append(RawPage(page_num=i, text=normalize_nfc(text)))
        except Exception as exc:  # noqa: BLE001 — fall back to PyMuPDF
            logger.warning("pdfplumber failed (%s); trying PyMuPDF", exc)
            pages = self._extract_pymupdf(file_bytes)
        return pages

    def _extract_pymupdf(self, file_bytes: bytes) -> list[RawPage]:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover
            raise PDFParseError("PyMuPDF unavailable for fallback") from exc
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:  # noqa: BLE001
            raise PDFParseError(f"Cannot open PDF: {exc}") from exc
        pages = [
            RawPage(page_num=i + 1, text=normalize_nfc(doc[i].get_text()))
            for i in range(doc.page_count)
        ]
        doc.close()
        return pages

    async def extract(self, file_bytes: bytes, source_file: str) -> RawDocument:
        if not file_bytes:
            raise PDFParseError("Empty PDF bytes")

        pages = await asyncio.to_thread(self._extract_sync, file_bytes)
        if not pages:
            raise PDFParseError(f"No pages extracted from {source_file}")

        if not any(p.text.strip() for p in pages):
            raise ScannedPDFError(
                f"{source_file} has no text layer (likely a scanned image)"
            )

        return RawDocument(
            source_file=source_file,
            extracted_at=datetime.utcnow(),
            pages=pages,
            total_pages=len(pages),
        )
