import asyncio
import difflib
import logging
import re

from src.modules.document_processing.application.usecase.convert_to_markdown import (
    ConvertToMarkdownUseCase,
)
from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine
from src.shared.infrastructure.persistence.legal_kg_reader import LegalKGReader
# Tạm thời bỏ persistence audit graph vào Neo4j
# from src.shared.infrastructure.persistence.neo4j_graph import Neo4jAuditGraph

logger = logging.getLogger(__name__)


def _normalize_key(s: str) -> str:
    return re.sub(r"[\s/\\\-\.]+", "-", (s or "").strip().lower())


def _extract_year(date_str: str) -> str:
    """Extract 4-digit year from either 'D-M-YYYY' or 'YYYY-MM-DD' format."""
    if not date_str:
        return ""
    # YYYY-MM-DD (Neo4j toString output)
    if len(date_str) >= 4 and date_str[:4].isdigit() and (len(date_str) == 4 or date_str[4] == "-"):
        return date_str[:4]
    # D-M-YYYY or DD-MM-YYYY (request format)
    parts = re.split(r"[-/]", date_str.strip())
    for part in reversed(parts):
        if len(part) == 4 and part.isdigit():
            return part
    return ""


def _find_best_document(
    law_number: str,
    law_name: str,
    date: str,
    documents: list[dict],
    threshold: float = 0.50,
) -> tuple[str | None, float]:
    """Fuzzy-match a requested law against KG Document nodes.

    Strategy mirrors GCS blob matching:
      - law_number present → 0.70 * so_hieu_sim + 0.30 * year_match
      - law_number absent  → 0.70 * ten_sim     + 0.30 * year_match

    Returns (doc_id, score).
    """
    if not documents:
        return None, 0.0

    use_law_number = bool(law_number)
    norm_input_law = _normalize_key(law_number) if use_law_number else ""
    norm_input_name = law_name.lower() if not use_law_number else ""
    input_year = _extract_year(date)

    best_id: str | None = None
    best_score: float = 0.0

    for doc in documents:
        doc_year = _extract_year(doc.get("ngay_ban_hanh") or "")
        year_match = 1.0 if (input_year and doc_year and input_year == doc_year) else 0.0

        if use_law_number:
            meta_so_hieu = _normalize_key(doc.get("so_hieu") or "")
            primary_sim = (
                difflib.SequenceMatcher(None, norm_input_law, meta_so_hieu).ratio()
                if norm_input_law and meta_so_hieu
                else 0.0
            )
        else:
            meta_ten = (doc.get("ten") or "").lower()
            primary_sim = (
                difflib.SequenceMatcher(None, norm_input_name, meta_ten).ratio()
                if norm_input_name and meta_ten
                else 0.0
            )

        score = 0.70 * primary_sim + 0.30 * year_match
        if score > best_score:
            best_score = score
            best_id = doc["doc_id"]

    return (best_id, best_score) if best_score >= threshold else (None, best_score)


_ARTICLE_CHECK_PROMPT = """\
Bạn là hệ thống đánh giá tuân thủ pháp lý.

Nhiệm vụ:
1. Xác định điều luật dưới đây có liên quan đến tài liệu đầu vào không.
2. Nếu có liên quan, đánh giá tài liệu có tuân thủ điều luật đó không.

Quy tắc (BẮT BUỘC):
- Chỉ dùng nội dung được cung cấp, không suy đoán thông tin còn thiếu.
- Nếu điều luật không điều chỉnh nội dung của tài liệu, đặt applicable=false và status="Không liên quan".
- Nếu có liên quan nhưng không đủ thông tin để kết luận rõ ràng, trả về "Cần kiểm tra".
- Chỉ trả về JSON, không thêm markdown hay giải thích bên ngoài JSON.
"""

_ARTICLE_CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "applicable": {"type": "boolean"},
        "status": {
            "type": "string",
            "enum": ["Tuân thủ", "Không tuân thủ", "Cần kiểm tra", "Không liên quan"],
        },
        "explanation": {"type": "string"},
    },
    "required": ["applicable", "status", "explanation"],
}


def _aggregate_status(article_results: list[dict]) -> str:
    """Aggregate per-article statuses into an overall law-level status.

    Quy tắc (mới):
    - Chỉ cần 1 điều applicable đạt "Tuân thủ" → overall "Tuân thủ".
    - Ngược lại, nếu có điều applicable "Không tuân thủ" → overall "Không tuân thủ".
    - Ngược lại, nếu có điều applicable "Cần kiểm tra" → overall "Cần kiểm tra".
    - Không có điều nào liên quan → "Không liên quan".
    """
    applicable = [r for r in article_results if r.get("applicable")]
    if not applicable:
        return "Không liên quan"
    statuses = {r.get("status") for r in applicable}
    if "Tuân thủ" in statuses:
        return "Tuân thủ"
    if "Không tuân thủ" in statuses:
        return "Không tuân thủ"
    return "Cần kiểm tra"


class AuditByGraphUseCase:
    """Audit compliance by checking each KG article against the input document in parallel."""

    def __init__(self, llm_engine: LLMEngine, ocr_engine: OCREngine) -> None:
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

        logger.info("[audit-by-graph] Converting PDF to markdown")
        input_markdown = await self._convert_usecase.execute(file_bytes, None, None)

        results: list[dict] = []

        # Tạm thời bỏ Neo4jAuditGraph() as audit_graph
        async with LegalKGReader() as kg_reader:
            if not kg_reader.enabled:
                raise RuntimeError("Neo4j is not configured; cannot perform KG-based audit")

            logger.info("[audit-by-graph] Listing KG documents for fuzzy matching")
            documents = await kg_reader.list_documents()

            for item in legal_bases:
                law_number = (item.get("law_number") or "").strip()
                law_name = (item.get("law_name") or "").strip()
                date = (item.get("date") or "").strip()
                audited_law = law_number or law_name

                if not audited_law:
                    result = {
                        "audited_law": "",
                        "date": date,
                        "matched_doc_id": None,
                        "overall_status": "Cần kiểm tra",
                        "explanation": "Thiếu số hiệu và tên văn bản.",
                        "articles": [],
                    }
                    results.append(result)
                    # Tạm thời bỏ persistence vào audit graph
                    # await audit_graph.upsert_audit_nodes_and_relation(
                    #     audited_document, item, result["overall_status"],
                    #     create_relationship=False,
                    # )
                    continue

                matched_doc_id, score = _find_best_document(
                    law_number, law_name, date, documents
                )
                logger.info(
                    "[audit-by-graph] Fuzzy match '%s' (%s): doc_id=%s score=%.3f",
                    audited_law, date, matched_doc_id, score,
                )

                if not matched_doc_id:
                    result = {
                        "audited_law": audited_law,
                        "date": date,
                        "matched_doc_id": None,
                        "overall_status": "Không tìm thấy trong hệ thống",
                        "explanation": "",
                        "articles": [],
                    }
                    results.append(result)
                    # Tạm thời bỏ persistence vào audit graph
                    # await audit_graph.upsert_audit_nodes_and_relation(
                    #     audited_document, item, result["overall_status"],
                    #     create_relationship=False,
                    # )
                    continue

                articles = await kg_reader.get_articles(matched_doc_id)
                logger.info(
                    "[audit-by-graph] Found %d articles for doc_id=%s",
                    len(articles), matched_doc_id,
                )

                if not articles:
                    result = {
                        "audited_law": audited_law,
                        "date": date,
                        "matched_doc_id": matched_doc_id,
                        "overall_status": "Cần kiểm tra",
                        "explanation": "Văn bản chưa có điều khoản trong hệ thống.",
                        "articles": [],
                    }
                    results.append(result)
                    # Tạm thời bỏ persistence vào audit graph
                    # await audit_graph.upsert_audit_nodes_and_relation(
                    #     audited_document, item, result["overall_status"],
                    #     create_relationship=True,
                    # )
                    continue

                article_results = await asyncio.gather(*[
                    self._check_article(input_markdown, article)
                    for article in articles
                ])

                overall_status = _aggregate_status(list(article_results))
                result = {
                    "audited_law": audited_law,
                    "date": date,
                    "matched_doc_id": matched_doc_id,
                    "overall_status": overall_status,
                    "explanation": "",
                    "articles": list(article_results),
                }
                results.append(result)
                # Tạm thời bỏ persistence vào audit graph
                # await audit_graph.upsert_audit_nodes_and_relation(
                #     audited_document, item, overall_status,
                #     create_relationship=True,
                # )

        return results

    async def _check_article(self, input_markdown: str, article: dict) -> dict:
        so = article["so"]
        tieu_de = article["tieu_de"]
        noi_dung = article["noi_dung"]

        header = f"Điều {so}" + (f" - {tieu_de}" if tieu_de else "")
        prompt = (
            f"{_ARTICLE_CHECK_PROMPT}\n\n"
            f"TÀI LIỆU ĐẦU VÀO:\n{input_markdown}\n\n"
            f"ĐIỀU LUẬT CẦN KIỂM TRA ({header}):\n{noi_dung}"
        )

        try:
            response = await self._llm_engine.generate_structured_response(
                prompt, _ARTICLE_CHECK_SCHEMA
            )
            applicable = bool((response or {}).get("applicable"))
            status = (response or {}).get("status") or "Cần kiểm tra"
            explanation = (response or {}).get("explanation") or ""
        except Exception:
            logger.exception("[audit-by-graph] LLM check failed for article %d", so)
            applicable = False
            status = "Không liên quan"
            explanation = "Lỗi khi gọi LLM."

        # Không applicable → luôn coi là "Không liên quan", bất kể LLM trả gì
        if not applicable:
            status = "Không liên quan"

        return {
            "article_id": article["id"],
            "article_number": so,
            "article_title": tieu_de,
            "applicable": applicable,
            "status": status,
            "explanation": explanation,
        }
