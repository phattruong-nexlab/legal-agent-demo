import asyncio
import io
import logging

import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
from pypdf import PdfReader, PdfWriter
from rapidfuzz import fuzz

from .interfaces import OCREngine

logger = logging.getLogger(__name__)


class PyTesseractEngine(OCREngine):
    """OCR Engine using pytesseract. Useful for scanned PDFs."""

    def __init__(self, default_language: str = "vie", default_dpi: int = 300):
        self._default_language = default_language
        self._default_dpi = default_dpi

    def _convert_pdf_to_images(
        self, file_bytes: bytes, dpi: int = 300
    ) -> list[Image.Image]:
        return convert_from_bytes(file_bytes, dpi=dpi)
        
    def get_page_count(self, file_bytes: bytes) -> int:
        reader = PdfReader(io.BytesIO(file_bytes))
        return len(reader.pages)
    
    def _extract_text_sync(self, file_bytes: bytes) -> str:
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        pages = self._convert_pdf_to_images(file_bytes, dpi=self._default_dpi)
        texts = []

        for page_image in pages:
            text = pytesseract.image_to_string(page_image, lang=self._default_language)
            if text.strip():
                texts.append(text.strip())

        content = "\n".join(texts).strip()
        if not content:
            raise ValueError("PyTesseract returned empty content")

        return content

    def _ocr_to_pdf_sync(self, file_bytes: bytes, language: str, dpi: int) -> bytes:
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        pages = self._convert_pdf_to_images(file_bytes, dpi=dpi)
        pdf_pages = []

        for page_image in pages:
            pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                page_image, lang=language, extension="pdf"
            )
            pdf_pages.append(pdf_bytes)

        writer = PdfWriter()
        for pdf_bytes in pdf_pages:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def _search_pages_sync(
        self,
        file_bytes: bytes,
        keyword: str,
        threshold: int,
        skip_pages: list[int] | None,
    ) -> list[tuple[int, int]]:
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        skip_pages = skip_pages or []
        pages = self._convert_pdf_to_images(file_bytes, dpi=self._default_dpi)
        scores: list[tuple[int, int]] = []

        for i, page_image in enumerate(pages):
            page_num = i + 1
            if page_num in skip_pages:
                continue

            text = pytesseract.image_to_string(page_image, lang=self._default_language)
            score = fuzz.partial_ratio(keyword.upper(), text.upper())
            if score >= threshold:
                scores.append((page_num, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _search_sections_bottom_up_sync(
        self, file_bytes: bytes, keywords: list[str], header_char_limit: int = 1000
    ) -> dict[str, int]:
        """Search keywords from last page to first, return {keyword: page_num}."""
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        logger.info("Processing... Scanning backwards from the last page to save time.")
        pages = convert_from_bytes(file_bytes)
        total_pages = len(pages)

        found: dict[str, int] = {}

        for i in range(total_pages - 1, -1, -1):
            page_num = i + 1

            text = pytesseract.image_to_string(pages[i], lang=self._default_language)
            text_upper = text.upper()

            for kw in keywords:
                if kw not in found and kw.upper() in text_upper:
                    if text_upper.find(kw.upper()) < header_char_limit:
                        found[kw] = page_num
                        logger.info(f"-> Found '{kw}' at page {page_num}")

            if len(found) == len(keywords):
                logger.info("-> Found all required keywords. Stopping scan.")
                break

        return found

    def _get_pages_between_sections_sync(
        self,
        file_bytes: bytes,
        start_keyword: str,
        end_keyword: str,
        header_char_limit: int = 1000,
    ) -> tuple[int, int] | None:
        """Get page range between two section keywords (bottom-up search)."""
        found = self._search_sections_bottom_up_sync(
            file_bytes, [start_keyword, end_keyword], header_char_limit
        )

        start_page = found.get(start_keyword)
        end_page = found.get(end_keyword)

        if start_page and end_page and start_page < end_page:
            return (start_page, end_page - 1)
        return None

    def _extract_pages_sync(
        self, file_bytes: bytes, page_range: tuple[int, int]
    ) -> bytes:
        """Extract specific pages from PDF."""
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        start_page, end_page = page_range
        reader = PdfReader(io.BytesIO(file_bytes))
        writer = PdfWriter()

        for p in range(start_page - 1, end_page):
            if p < len(reader.pages):
                writer.add_page(reader.pages[p])

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    # Async interface methods

    async def extract_text(self, file_bytes: bytes) -> str:
        return await asyncio.to_thread(self._extract_text_sync, file_bytes)

    async def ocr_to_pdf(
        self, file_bytes: bytes, language: str = "vie", dpi: int = 300
    ) -> bytes:
        lang = language or self._default_language
        resolution = dpi or self._default_dpi
        return await asyncio.to_thread(
            self._ocr_to_pdf_sync, file_bytes, lang, resolution
        )

    async def search_pages_by_keyword(
        self,
        file_bytes: bytes,
        keyword: str,
        threshold: int = 70,
        skip_pages: list[int] | None = None,
    ) -> list[tuple[int, int]]:
        return await asyncio.to_thread(
            self._search_pages_sync, file_bytes, keyword, threshold, skip_pages
        )

    async def extract_pages(
        self, file_bytes: bytes, page_range: tuple[int, int]
    ) -> bytes:
        return await asyncio.to_thread(self._extract_pages_sync, file_bytes, page_range)

    async def get_page_count(self, file_bytes: bytes) -> int:
        reader = PdfReader(io.BytesIO(file_bytes))
        return len(reader.pages)

    async def get_total_pages(self, file_bytes: bytes) -> int:
        reader = PdfReader(io.BytesIO(file_bytes))
        return len(reader.pages)

    async def search_sections_bottom_up(
        self, file_bytes: bytes, keywords: list[str], header_char_limit: int = 1000
    ) -> dict[str, int]:
        return await asyncio.to_thread(
            self._search_sections_bottom_up_sync,
            file_bytes,
            keywords,
            header_char_limit,
        )

    async def get_pages_between_sections(
        self,
        file_bytes: bytes,
        start_keyword: str,
        end_keyword: str,
        header_char_limit: int = 1000,
    ) -> tuple[int, int] | None:
        return await asyncio.to_thread(
            self._get_pages_between_sections_sync,
            file_bytes,
            start_keyword,
            end_keyword,
            header_char_limit,
        )
