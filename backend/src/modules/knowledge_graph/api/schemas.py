"""Pydantic I/O models for the knowledge_graph API."""

from pydantic import BaseModel, Field

# Re-exported so routes can use it as a response_model.
from ..application.usecase.ingest_document import IngestReport  # noqa: F401


class StatusResponse(BaseModel):
    status: str = Field(..., description="ok | skipped")
    detail: dict | None = None


class StatsResponse(BaseModel):
    status: str = "ok"
    counts: dict = Field(default_factory=dict)


class ValidationResponse(BaseModel):
    status: str = "ok"
    report: dict = Field(default_factory=dict)


class FileIngestResult(BaseModel):
    filename: str
    success: bool
    report: IngestReport | None = None
    error: str | None = None


class BatchIngestReport(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[FileIngestResult]
