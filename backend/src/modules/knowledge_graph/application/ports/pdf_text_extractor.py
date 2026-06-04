"""Port: PDF → raw text (step 1). Implemented in the infrastructure layer."""

from typing import Protocol

from ...domain.entity.document import RawDocument


class PDFTextExtractor(Protocol):
    """Extract a page-segmented raw-text document from PDF bytes.

    Implementations MUST raise `ScannedPDFError` when the PDF has no text
    layer (image scan) rather than returning empty pages — the pipeline does
    not auto-OCR in Phase 1.
    """

    async def extract(self, file_bytes: bytes, source_file: str) -> RawDocument:
        raise NotImplementedError
