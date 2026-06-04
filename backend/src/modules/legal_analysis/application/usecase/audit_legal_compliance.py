import difflib
import logging
import re

from src.config import get_settings
from src.modules.document_processing.application.usecase.convert_to_markdown import (
    ConvertToMarkdownUseCase,
)
from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine
from src.shared.infrastructure.persistence.gcs_storage import (
    download_text_from_bucket,
    list_blobs_with_metadata,
)
from src.shared.infrastructure.persistence.neo4j_graph import Neo4jAuditGraph

logger = logging.getLogger(__name__)


def _normalize_key(s: str) -> str:
    """Lowercase and unify separators (/, \\, -, ., space) to hyphen."""
    return re.sub(r"[\s/\\\-\.]+", "-", (s or "").strip().lower())


def _find_best_blob(
    law_number: str,
    law_name: str,
    date: str,
    blobs: list[dict],
    threshold: float = 0.50,
) -> tuple[str | None, float]:
    """
    Score each blob and return the best match above threshold.

    Strategy (mutually exclusive branches):
      - law_number present → score = 0.70 * law_number_sim + 0.30 * date_match
      - law_number absent  → score = 0.70 * law_name_sim   + 0.30 * date_match

    Returns (blob_name, score); blob_name is None when score < threshold.
    """
    if not blobs:
        return None, 0.0

    use_law_number = bool(law_number)
    norm_input_law = _normalize_key(law_number) if use_law_number else ""
    norm_input_name = law_name.lower() if not use_law_number else ""

    best_blob: str | None = None
    best_score: float = 0.0

    for entry in blobs:
        meta = entry.get("metadata") or {}
        meta_date = (meta.get("date") or "").strip()
        date_match = 1.0 if (date and meta_date and date.strip() == meta_date) else 0.0

        if use_law_number:
            meta_law = _normalize_key(meta.get("law_number", ""))
            primary_sim = (
                difflib.SequenceMatcher(None, norm_input_law, meta_law).ratio()
                if norm_input_law and meta_law
                else 0.0
            )
        else:
            meta_law_name = (meta.get("law_name") or "").lower()
            primary_sim = (
                difflib.SequenceMatcher(None, norm_input_name, meta_law_name).ratio()
                if norm_input_name and meta_law_name
                else 0.0
            )

        score = 0.70 * primary_sim + 0.30 * date_match

        if score > best_score:
            best_score = score
            best_blob = entry["blob_name"]

    if best_score >= threshold:
        return best_blob, best_score
    return None, best_score

AUDIT_LEGAL_COMPLIANCE_PROMPT = """
You are a legal compliance evaluator.

Task:
- Compare the INPUT document content against the REFERENCE legal document content.
- Decide whether the INPUT complies with the REFERENCE.

Return JSON only with this shape:
{
  "status": "Tuân thủ" | "Không tuân thủ" | "Cần kiểm tra",
  "explanation": "An explanation of the reasoning behind the compliance status."
}

Rules (STRICT):
- Use ONLY the provided content.
- Do NOT guess missing information.
- If information is insufficient or ambiguous, return "Cần kiểm tra".
- No explanations, no extra keys, no markdown.
"""

AUDIT_LEGAL_COMPLIANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["Tuân thủ", "Không tuân thủ", "Cần kiểm tra"],
        },
        "explanation": {"type": "string"},
    },
    "required": ["status", "explanation"],
}


class AuditLegalComplianceUseCase:
    """Use case: Audit compliance of a document against legal bases."""

    def __init__(self, llm_engine: LLMEngine, ocr_engine: OCREngine):
        self._llm_engine = llm_engine
        self._ocr_engine = ocr_engine
        self._convert_usecase = ConvertToMarkdownUseCase(llm_engine, ocr_engine)

    async def execute(
        self,
        file_bytes: bytes,
        legal_bases: list[dict],
        audited_document: dict,
    ) -> list[dict]:
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        settings = get_settings()
        bucket_name = settings.LEGAL_BUCKET

        logger.info("Converting full file to markdown for audit")
        input_markdown = await self._convert_usecase.execute(file_bytes, None, None)

        logger.info("Listing legal documents with metadata from GCS")
        blobs = list_blobs_with_metadata(
            bucket_name=bucket_name, project_id=settings.GCP_PROJECT_ID
        )

        results: list[dict] = []
        async with Neo4jAuditGraph() as graph:
            for item in legal_bases:
                law_number = (item.get("law_number") or "").strip()
                law_name = (item.get("law_name") or "").strip()
                date = (item.get("date") or "").strip()

                audited_law = (
                    law_number if (law_number and law_name) else (law_number or law_name)
                )

                if not audited_law:
                    result = {
                        "audited_law": "",
                        "date": date,
                        "status": "Cần kiểm tra",
                        "explanation": "Thiếu số hiệu và tên văn bản.",
                        "matched_blob": None,
                    }
                    results.append(result)
                    await graph.upsert_audit_nodes_and_relation(
                        audited_document,
                        item,
                        result["status"],
                        create_relationship=False,
                    )
                    continue

                matched_blob, score = _find_best_blob(law_number, law_name, date, blobs)
                logger.info(
                    "Fuzzy match for '%s' (%s): blob=%s score=%.3f",
                    audited_law,
                    date,
                    matched_blob,
                    score,
                )

                if not matched_blob:
                    result = {
                        "audited_law": audited_law,
                        "date": date,
                        "status": "Không tìm thấy trong hệ thống",
                        "explanation": "",
                        "matched_blob": None,
                    }
                    results.append(result)
                    await graph.upsert_audit_nodes_and_relation(
                        audited_document,
                        item,
                        result["status"],
                        create_relationship=False,
                    )
                    continue

                reference_markdown = download_text_from_bucket(
                    bucket_name=bucket_name,
                    blob_name=matched_blob,
                    project_id=settings.GCP_PROJECT_ID,
                )

                prompt = (
                    f"INPUT DOCUMENT (Markdown):\n{input_markdown}\n\n"
                    f"REFERENCE LEGAL DOCUMENT (Markdown):\n{reference_markdown}\n"
                )

                response = await self._llm_engine.generate_structured_response(
                    prompt,
                    AUDIT_LEGAL_COMPLIANCE_SCHEMA,
                )
                status = (response or {}).get("status") or "Cần kiểm tra"
                explanation = (response or {}).get("explanation") or ""

                result = {
                    "audited_law": audited_law,
                    "date": date,
                    "status": status,
                    "explanation": explanation,
                    "matched_blob": matched_blob,
                }
                results.append(result)
                await graph.upsert_audit_nodes_and_relation(
                    audited_document,
                    item,
                    status,
                    create_relationship=True,
                )

        return results
