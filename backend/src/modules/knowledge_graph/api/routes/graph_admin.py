import logging

from fastapi import APIRouter, Depends

from ...application.usecase.graph_stats import GraphStatsUseCase
from ...application.usecase.init_graph_schema import InitGraphSchemaUseCase
from ...application.usecase.resolve_placeholders import ResolvePlaceholdersUseCase
from ...application.usecase.validate_graph import ValidateGraphUseCase
from ..dependencies import (
    get_init_schema_usecase,
    get_resolve_placeholders_usecase,
    get_stats_usecase,
    get_validate_usecase,
)
from ..schemas import StatsResponse, StatusResponse, ValidationResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/init-schema", response_model=StatusResponse)
async def init_schema(
    usecase: InitGraphSchemaUseCase = Depends(get_init_schema_usecase),
) -> StatusResponse:
    """Create Neo4j constraints & indexes (idempotent, run once on setup)."""
    result = await usecase.execute()
    return StatusResponse(status=result.get("status", "ok"), detail=result)


@router.get("/validate", response_model=ValidationResponse)
async def validate_graph(
    usecase: ValidateGraphUseCase = Depends(get_validate_usecase),
) -> ValidationResponse:
    """Run post-load Cypher validation checks (section 9)."""
    report = await usecase.execute()
    return ValidationResponse(status=report.get("status", "ok"), report=report)


@router.post("/resolve-placeholders", response_model=StatusResponse)
async def resolve_placeholders(
    usecase: ResolvePlaceholdersUseCase = Depends(get_resolve_placeholders_usecase),
) -> StatusResponse:
    """Report PLACEHOLDER documents still awaiting ingestion (section 7.3)."""
    result = await usecase.execute()
    return StatusResponse(status=result.get("status", "ok"), detail=result)


@router.get("/stats", response_model=StatsResponse)
async def graph_stats(
    usecase: GraphStatsUseCase = Depends(get_stats_usecase),
) -> StatsResponse:
    """Node / relationship counts."""
    counts = await usecase.execute()
    return StatsResponse(status=counts.get("status", "ok"), counts=counts)
