from fastapi import APIRouter

from .graph_admin import router as graph_admin_router
from .ingest import router as ingest_router

knowledge_graph_router = APIRouter(prefix="/knowledge-graph")

knowledge_graph_router.include_router(ingest_router, tags=["knowledge-graph"])
knowledge_graph_router.include_router(graph_admin_router, tags=["knowledge-graph"])
