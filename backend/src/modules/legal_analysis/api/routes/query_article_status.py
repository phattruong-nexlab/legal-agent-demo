import logging

from fastapi import APIRouter, Depends, HTTPException

from src.config import get_settings

from ...application.usecase.query_article_status import QueryArticleStatusUseCase
from ..dependencies import get_query_article_status_usecase
from ..schemas import QueryArticleStatusRequest, QueryArticleStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query-article-status", response_model=QueryArticleStatusResponse)
async def query_article_status(
    payload: QueryArticleStatusRequest,
    usecase: QueryArticleStatusUseCase = Depends(get_query_article_status_usecase),
) -> QueryArticleStatusResponse:
    """Natural-language reverse query against the Legal Knowledge Graph.

    Example: "Điều 18 Thông tư 08/2022 còn hiệu lực không?".

    Pipeline: LLM parses question → Neo4j fuzzy-match + article lookup +
    inbound AMENDS/REPEALS/REPLACES → LLM synthesizes an answer.
    """
    settings = get_settings()
    if not settings.NEO4J_URI:
        raise HTTPException(status_code=503, detail="Neo4j is not configured")

    logger.info("[query-article-status] question=%s", payload.question)
    result = await usecase.execute(payload.question)
    return QueryArticleStatusResponse(**result)
