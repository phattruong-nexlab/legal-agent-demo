from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter,  FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.modules.legal_analysis.api.routes import legal_basis_router
from src.modules.document_processing.api.routes import document_processing_router
from src.modules.knowledge_graph.api.routes import knowledge_graph_router
from src.shared.infrastructure.persistence.bigquery import create_bigquery_client
settings = get_settings()

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    settings = get_settings()
    logger.info("Starting application with settings loaded")


    bq_client = create_bigquery_client(project_id=settings.GCP_PROJECT_ID)
    app.state.bq_client = bq_client
    logger.info("BigQuery Client connected")

    yield


    if hasattr(app.state, "bq_client"):
        app.state.bq_client.close()
        logger.info("BigQuery Client closed")

def create_app() -> FastAPI:
    app = FastAPI(title="Backend Service", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev only
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    v1_router = APIRouter(prefix="/api/v1")
    @v1_router.get("/health")
    async def health():
        return {"status": "healthy"}
    
    v1_router.include_router(legal_basis_router)
    v1_router.include_router(document_processing_router)
    v1_router.include_router(knowledge_graph_router)
    app.include_router(v1_router)

    logger.info("FastAPI App created and routers loaded successfully.")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
