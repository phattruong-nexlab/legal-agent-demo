from typing import Protocol


class OCREngine(Protocol):
    """Interface for OCR engines that extract text from PDF files."""

    async def extract_text(self, file_bytes: bytes) -> str:
        raise NotImplementedError

    async def ocr_to_pdf(
        self, file_bytes: bytes, language: str = "vie", dpi: int = 300
    ) -> bytes:
        raise NotImplementedError

    async def search_pages_by_keyword(
        self,
        file_bytes: bytes,
        keyword: str,
        threshold: int = 70,
        skip_pages: list[int] | None = None,
    ) -> list[tuple[int, int]]:
        raise NotImplementedError

    async def extract_pages(
        self, file_bytes: bytes, page_range: tuple[int, int]
    ) -> bytes:
        raise NotImplementedError

    async def get_page_count(self, file_bytes: bytes) -> int:
        raise NotImplementedError
