import logging

from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine

logger = logging.getLogger(__name__)

EXTRACT_LEGAL_BASIS_PROMPT = """
You are a legal document extraction engine.

Task:
- Identify the legal bases (laws, codes, decrees, circulars, resolutions, decisions, etc.)
    cited on the FIRST PAGE of the document.
- Identify the document being analyzed, if it is explicitly named on the FIRST PAGE.

Rules (STRICT):
- Only extract items explicitly cited on the first page.
- Do NOT infer missing items.
- Do NOT add commentary.
- If none are found, return an empty list.
- Preserve original Vietnamese characters.
- Do NOT change or translate abbreviations.
- Normalize date to D-M-YYYY using hyphens (no zero padding). Example: 27-5-2009.

Field rules (STRICT):
- law_number: the document number/identifier only (e.g., "666/QĐ-TTg", "58/2023/NĐ-CP").
  Keep original slashes. If not present in the citation, return "".
- law_name: the official title/name of the legal document as stated in the citation
  (e.g., "Luật Doanh nghiệp", "Nghị định quy định về chế độ tiền lương của công ty nhà nước").
  If the law name isn't appropriate, just return "", don't make things up.
  Example of a wrong entry: "law_name": "của Thủ tướng Chính phủ về việc thành lập Trường Đại học Dân lập Hồng Bàng"
- date: promulgation date. If not present, return "".

Return JSON only as an object with this shape:
{
    "document": {"law_number": "...", "law_name": "...", "date": "..."},
    "legal_bases": [
        {"law_number": "...", "law_name": "...", "date": "..."}
    ]
}
If the document name is not explicitly stated on the first page, return empty strings
for all fields in "document".
"""

LEGAL_BASIS_SCHEMA = {
    "type": "object",
    "properties": {
        "document": {
            "type": "object",
            "properties": {
                "law_number": {"type": "string"},
                "law_name": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["law_number", "law_name", "date"],
        },
        "legal_bases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "law_number": {"type": "string"},
                    "law_name": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["law_number", "law_name", "date"],
            },
        },
    },
    "required": ["document", "legal_bases"],
}


class ExtractLegalBasisUseCase:
    """Use case: Extract legal bases cited on the first page of a PDF."""

    def __init__(self, llm_engine: LLMEngine, ocr_engine: OCREngine):
        self._llm_engine = llm_engine
        self._ocr_engine = ocr_engine

    async def execute(self, file_bytes: bytes) -> dict:
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        logger.info("Extracting first page for legal basis detection")
        first_page_pdf = await self._ocr_engine.extract_pages(file_bytes, (1, 1))

        logger.info("LLM: Extracting legal bases from first page")
        result = await self._llm_engine.generate_structured_response_with_pdf(
            first_page_pdf,
            EXTRACT_LEGAL_BASIS_PROMPT,
            LEGAL_BASIS_SCHEMA,
        )

        candidates = []
        document = result.get("document") or {}
        if isinstance(document, dict):
            candidates.append(document)
        legal_bases = result.get("legal_bases") or []
        if isinstance(legal_bases, list):
            candidates.extend(item for item in legal_bases if isinstance(item, dict))

        missing = [item for item in candidates if not item.get("law_number")]
        if missing:
            logger.info(f"Fallback web search for {len(missing)} items with missing law_number")
            for item in missing:
                law_name = item.get("law_name", "")
                if not law_name:
                    continue
                resolved = await self._llm_engine.search_for_document_name(law_name)
                if resolved:
                    logger.info(f"Resolved law_number via web search: '{resolved}' for '{law_name[:60]}'")
                    item["law_number"] = resolved

        return result
