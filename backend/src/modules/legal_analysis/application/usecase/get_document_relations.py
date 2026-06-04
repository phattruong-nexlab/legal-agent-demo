import logging

from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine
from src.shared.infrastructure.persistence.neo4j_graph import Neo4jAuditGraph

from .extract_legal_basis import EXTRACT_LEGAL_BASIS_PROMPT, LEGAL_BASIS_SCHEMA

logger = logging.getLogger(__name__)


class GetDocumentRelationsUseCase:
    """Use case: identify a legal document from the first page of a PDF, then fetch its Neo4j relations."""

    def __init__(self, llm_engine: LLMEngine, ocr_engine: OCREngine) -> None:
        self._llm_engine = llm_engine
        self._ocr_engine = ocr_engine

    async def execute(self, file_bytes: bytes) -> tuple[dict, list[dict]]:
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        logger.info("[doc-relations] extracting first page for document identification")
        first_page_pdf = await self._ocr_engine.extract_pages(file_bytes, (1, 1))

        logger.info("[doc-relations] LLM: identifying document from first page")
        result = await self._llm_engine.generate_structured_response_with_pdf(
            first_page_pdf,
            EXTRACT_LEGAL_BASIS_PROMPT,
            LEGAL_BASIS_SCHEMA,
        )

        document: dict = result.get("document") or {}
        law_number = (document.get("law_number") or "").strip()
        law_name = (document.get("law_name") or "").strip()

        if not law_number and not law_name:
            logger.warning("[doc-relations] could not identify document from first page")
            return document, []

        if not law_number and law_name:
            resolved = await self._llm_engine.search_for_document_name(law_name)
            if resolved:
                logger.info("[doc-relations] resolved law_number via web search: '%s'", resolved)
                document["law_number"] = resolved

        logger.info("[doc-relations] fetching Neo4j relations for document: %s", document)
        async with Neo4jAuditGraph() as graph:
            relations = await graph.fetch_related_documents(document)

        return document, relations
