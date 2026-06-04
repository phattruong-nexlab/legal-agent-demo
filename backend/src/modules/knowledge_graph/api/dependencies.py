"""FastAPI DI wiring — composes ports + use cases (clean-architecture seam).

The Neo4j repository is request-scoped: connected on entry, closed on exit via
an async-generator dependency.
"""

from collections.abc import AsyncIterator

from fastapi import Depends

from src.shared.infrastructure.llm_engine.gemini_engine import GeminiEngine
from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine
from src.shared.infrastructure.ocr_engine.pytesseract_engine import PyTesseractEngine

from ..application.usecase.graph_stats import GraphStatsUseCase
from ..application.usecase.ingest_document import IngestDocumentUseCase
from ..application.usecase.init_graph_schema import InitGraphSchemaUseCase
from ..application.usecase.resolve_placeholders import ResolvePlaceholdersUseCase
from ..application.usecase.validate_graph import ValidateGraphUseCase
from ..infrastructure.pdf.ocr_extractor import SmartPdfExtractor
from ..infrastructure.persistence.neo4j_kg_repository import Neo4jKGRepository


def get_llm_engine() -> LLMEngine:
    return GeminiEngine()


def get_ocr_engine() -> OCREngine:
    return PyTesseractEngine()


def get_pdf_extractor(
    llm_engine: LLMEngine = Depends(get_llm_engine),
    ocr_engine: OCREngine = Depends(get_ocr_engine),
) -> SmartPdfExtractor:
    return SmartPdfExtractor(llm_engine=llm_engine, ocr_engine=ocr_engine)


async def get_graph_repository() -> AsyncIterator[Neo4jKGRepository]:
    repo = Neo4jKGRepository()
    await repo.connect()
    try:
        yield repo
    finally:
        await repo.aclose()


def get_ingest_usecase(
    pdf_extractor: SmartPdfExtractor = Depends(get_pdf_extractor),
    graph_repo: Neo4jKGRepository = Depends(get_graph_repository),
    llm_engine: LLMEngine = Depends(get_llm_engine),
) -> IngestDocumentUseCase:
    return IngestDocumentUseCase(
        pdf_extractor=pdf_extractor,
        graph_repo=graph_repo,
        llm_engine=llm_engine,
    )


def get_init_schema_usecase(
    graph_repo: Neo4jKGRepository = Depends(get_graph_repository),
) -> InitGraphSchemaUseCase:
    return InitGraphSchemaUseCase(graph_repo=graph_repo)


def get_validate_usecase(
    graph_repo: Neo4jKGRepository = Depends(get_graph_repository),
) -> ValidateGraphUseCase:
    return ValidateGraphUseCase(graph_repo=graph_repo)


def get_resolve_placeholders_usecase(
    graph_repo: Neo4jKGRepository = Depends(get_graph_repository),
) -> ResolvePlaceholdersUseCase:
    return ResolvePlaceholdersUseCase(graph_repo=graph_repo)


def get_stats_usecase(
    graph_repo: Neo4jKGRepository = Depends(get_graph_repository),
) -> GraphStatsUseCase:
    return GraphStatsUseCase(graph_repo=graph_repo)
