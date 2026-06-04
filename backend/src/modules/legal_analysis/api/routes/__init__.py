from fastapi import APIRouter

from .audit_by_graph import router as audit_by_graph_router
from .audit_legal_basis import router as audit_legal_basis_router
from .document_relations import router as document_relations_router
from .extract_legal_basis import router as extract_legal_basis_router
from .query_article_status import router as query_article_status_router

legal_basis_router = APIRouter(prefix="/legal-analysis")

legal_basis_router.include_router(extract_legal_basis_router, tags=["legal-basis"])
legal_basis_router.include_router(audit_legal_basis_router, tags=["legal-basis"])
legal_basis_router.include_router(audit_by_graph_router, tags=["legal-basis"])
legal_basis_router.include_router(document_relations_router, tags=["legal-basis"])
legal_basis_router.include_router(query_article_status_router, tags=["legal-basis"])
