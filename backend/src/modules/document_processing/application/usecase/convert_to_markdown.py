import logging
import re

from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine

logger = logging.getLogger(__name__)

# General-purpose prompt for converting PDF content to Markdown
CONVERT_TO_MARKDOWN_PROMPT = """
    You are a document extraction engine. Your task is to convert the PDF pages of a given file into clean Markdown.
    
    Rules (STRICT):
    - Preserve the original reading order exactly as in the document
    - Do NOT summarize, paraphrase, or explain
    - Do NOT add any text that does not exist in the PDF
    - Keep original wording, punctuation, and casing
    - If content is unclear or unreadable, output "[UNREADABLE]"
    - Do NOT infer missing data

    Formatting rules:
    - Headings: USE Markdown headings (#, ##, ###) if clearly present
    - Paragraphs: keep original paragraph breaks
    - Lists: use "-" or numbered lists only if they exist in the PDF

    Tables:
    - Convert ALL tables to Markdown table format (only use `:---` for separating header row)
    - For Markdown tables, use minimal separators.
    - The header separator MUST use exactly `---` or `:---`.
    - Do NOT extend dashes to match column width.
    - Preserve original row and column order
    - Do NOT merge or split cells unless explicitly shown in the PDF
    - If a cell is empty, leave it empty
    - If a table spans multiple pages, merge it into one table
    - If multiple tables exist, separate them with:
        ---
        <markdown table>
        ---

    Output:
    - Return ONLY the extracted Markdown content
    - No explanations
    - No commentary
    - No additional text
    """

EXTRACT_DOCUMENT_METADATA_PROMPT = """
You are extracting metadata from the FIRST PAGE of a Vietnamese legal document.

Return a JSON object with exactly three fields:

1. "law_number": The official document number/identifier as written (e.g., "58/2023/NĐ-CP", "666/QĐ-TTg", "15/2020/QH14").
   - Keep original slashes and abbreviations (do NOT replace "/" with "-").
   - If not found, return "".

2. "law_name": The full official title/name of the document as it appears on the page
   (e.g., "Nghị định quy định về chế độ tiền lương...", "Luật An ninh mạng").
   - Preserve original Vietnamese characters.
   - If not found, return "".

3. "date": Promulgation date in D-M-YYYY format with no zero padding (e.g., "27-5-2009", "1-1-2024").
   - If not found, return "".

STRICT RULES:
- Use ONLY information from the first page.
- Do NOT guess, infer, or add commentary.
- Preserve original Vietnamese characters and abbreviations.
"""

EXTRACT_DOCUMENT_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "law_number": {"type": "string"},
        "law_name": {"type": "string"},
        "date": {"type": "string"},
    },
    "required": ["law_number", "law_name", "date"],
}


class ConvertToMarkdownUseCase:
    """Use case: Convert a PDF file (or page range) to Markdown content."""

    def __init__(self, llm_engine: LLMEngine, ocr_engine: OCREngine):
        self._llm_engine = llm_engine
        self._ocr_engine = ocr_engine

    async def extract_document_metadata(self, file_bytes: bytes) -> dict[str, str]:
        """Extract law_number, law_name, and date from the first page using LLM."""
        first_page_pdf = await self._ocr_engine.extract_pages(file_bytes, (1, 1))
        result = await self._llm_engine.generate_structured_response_with_pdf(
            first_page_pdf,
            EXTRACT_DOCUMENT_METADATA_PROMPT,
            EXTRACT_DOCUMENT_METADATA_SCHEMA,
        )
        return {
            "law_number": (result or {}).get("law_number", "").strip(),
            "law_name": (result or {}).get("law_name", "").strip(),
            "date": (result or {}).get("date", "").strip(),
        }

    async def execute(self, file_bytes: bytes, start_page: int | None, end_page: int | None) -> str:
        # Determine the page range based on start_page and end_page
        if start_page == 0: 
            start_page = None
        if end_page == 0: 
            end_page = None
            
        if start_page is None and end_page is None:
            # No start or end: process entire file
            logger.info("Extracting entire file")
            selected_pdf = file_bytes
        else:
            # Get total page count
            total_pages = await self._ocr_engine.get_page_count(file_bytes)
            # Determine actual start and end pages
            actual_start = start_page if start_page is not None else 1
            actual_end = end_page if end_page is not None else total_pages

            logger.info(f"Extracting pages {actual_start} to {actual_end}")
            selected_pdf = await self._ocr_engine.extract_pages(
                file_bytes, (actual_start, actual_end)
            )

        logger.info("LLM: Generating markdown from PDF...")
        response = await self._llm_engine.generate_response_with_pdf(
            CONVERT_TO_MARKDOWN_PROMPT, selected_pdf
        )

        content = re.sub(r"```markdown\s*", "", response)
        content = re.sub(r"```\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        return content


