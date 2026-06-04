"""Reverse query against the Legal Knowledge Graph.

Given a natural-language question like "Điều 18 Thông tư 08/2022 còn hiệu lực
không?", this use case:
  1. Asks the LLM to extract the target (so_hieu / law_name / article / clause).
  2. Fuzzy-matches the document to a Neo4j :Document node.
  3. Reads the article node + parent doc status + inbound AMENDS/REPEALS/
     REPLACES relationships from other Documents.
  4. Asks the LLM to synthesize a natural-language answer from the graph facts.
"""

from __future__ import annotations

import logging

from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.persistence.legal_kg_reader import LegalKGReader

from .audit_by_graph import _find_best_document

logger = logging.getLogger(__name__)

_PARSE_PROMPT = """\
Bạn là hệ thống phân tích câu hỏi pháp lý tiếng Việt.

Nhiệm vụ: Trích xuất tham số truy vấn từ câu hỏi người dùng về một văn bản pháp luật Việt Nam.

Quy tắc:
- law_number: số hiệu văn bản (vd: "08/2022/TT-BGDĐT", "58/2023/NĐ-CP"). Nếu câu hỏi chỉ ghi
  "Thông tư 08/2022" thì điền "08/2022" (KHÔNG tự suy đoán cơ quan ban hành).
- law_name: tên/loại văn bản dạng ngắn (vd: "Thông tư 08/2022", "Luật Giáo dục 2019"). Nếu
  không xác định được, để rỗng.
- article_so: số Điều (số nguyên). Bắt buộc khi câu hỏi nhắc đến "Điều X".
- clause_so: số Khoản (số nguyên) hoặc null.
- point_kyhieu: ký hiệu Điểm (vd: "a", "b", "đ") hoặc rỗng.
- intent: ý định truy vấn — "status" (còn hiệu lực không), "content" (nội dung điều luật là gì),
  "amendments" (đã sửa đổi/bãi bỏ chưa), hoặc "other".
- Nếu câu hỏi KHÔNG đề cập một văn bản pháp lý cụ thể, đặt article_so = null và intent = "other".
"""

_PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "law_number": {"type": "string"},
        "law_name": {"type": "string"},
        "article_so": {"type": ["integer", "null"]},
        "clause_so": {"type": ["integer", "null"]},
        "point_kyhieu": {"type": "string"},
        "intent": {
            "type": "string",
            "enum": ["status", "content", "amendments", "other"],
        },
    },
    "required": ["law_number", "law_name", "article_so", "intent"],
}

_ANSWER_SYSTEM_PROMPT = """\
Bạn là trợ lý pháp lý. Trả lời câu hỏi người dùng dựa CHỈ trên dữ liệu Knowledge Graph được cung cấp.

Quy tắc:
- Trả lời ngắn gọn, chính xác, bằng tiếng Việt.
- Nếu trạng thái văn bản là HIEU_LUC và không có amendment liên quan → khẳng định "vẫn còn hiệu lực".
- Nếu có AMENDS/REPEALS/REPLACES nhắm vào Điều/Khoản đang hỏi → nêu rõ văn bản nào, số hiệu, ngày ban hành.
- Nếu document_status là HET_HIEU_LUC → khẳng định "đã hết hiệu lực".
- KHÔNG suy đoán thông tin ngoài dữ liệu. Nếu thiếu dữ liệu, nói rõ "không đủ dữ liệu trong hệ thống".
- KHÔNG kèm markdown, KHÔNG kèm tiêu đề, chỉ trả 1 đoạn văn ngắn (2-5 câu).
"""

_DOC_STATUS_LABEL = {
    "HIEU_LUC": "Còn hiệu lực",
    "HET_HIEU_LUC": "Hết hiệu lực",
    "SUA_DOI": "Đã được sửa đổi",
    "CHUA_HIEU_LUC": "Chưa có hiệu lực",
    "PLACEHOLDER": "Chưa được nạp đầy đủ vào hệ thống",
}

_REL_LABEL = {
    "AMENDS": "sửa đổi/bổ sung",
    "REPEALS": "bãi bỏ",
    "REPLACES": "thay thế",
}


def _build_answer_prompt(
    question: str,
    parsed: dict,
    document: dict | None,
    article: dict | None,
    amendments: list[dict],
) -> str:
    lines: list[str] = [f"CÂU HỎI NGƯỜI DÙNG: {question}"]
    lines.append("")
    lines.append(f"PARSED: {parsed}")
    lines.append("")
    if document:
        lines.append("DOCUMENT:")
        lines.append(
            f"- số hiệu: {document.get('so_hieu') or '-'}\n"
            f"- tên: {document.get('ten') or '-'}\n"
            f"- loại: {document.get('loai') or '-'}\n"
            f"- ngày ban hành: {document.get('ngay_ban_hanh') or '-'}\n"
            f"- ngày hiệu lực: {document.get('ngay_hieu_luc') or '-'}\n"
            f"- ngày hết hiệu lực: {document.get('ngay_het_hieu_luc') or '-'}\n"
            f"- trạng thái: {document.get('trang_thai') or '-'} "
            f"({_DOC_STATUS_LABEL.get(document.get('trang_thai') or '', '?')})"
        )
    else:
        lines.append("DOCUMENT: không tìm thấy trong Knowledge Graph")
    lines.append("")
    if article:
        lines.append(
            f"ARTICLE: Điều {article.get('so')} "
            f"- {article.get('tieu_de') or ''}\nNội dung: {article.get('noi_dung') or ''}"
        )
    else:
        lines.append("ARTICLE: không tìm thấy Điều này trong văn bản")
    lines.append("")
    if amendments:
        lines.append("INBOUND LIFECYCLE (các văn bản tác động lên văn bản này):")
        for a in amendments:
            label = _REL_LABEL.get(a.get("rel_type") or "", a.get("rel_type") or "")
            lines.append(
                f"- {a.get('src_so_hieu') or '?'} ({a.get('src_ngay_ban_hanh') or '?'}) "
                f"{label} — scope: {a.get('scope') or '?'} "
                f"[scope_type={a.get('scope_type') or '?'}, "
                f"target_article={a.get('target_article')}, "
                f"target_clause={a.get('target_clause')}, "
                f"target_point={a.get('target_point') or '-'}]"
            )
    else:
        lines.append("INBOUND LIFECYCLE: không có")
    return "\n".join(lines)


class QueryArticleStatusUseCase:
    """Reverse-query Use Case: natural language → KG facts → natural language answer."""

    def __init__(self, llm_engine: LLMEngine) -> None:
        self._llm = llm_engine

    async def execute(self, question: str) -> dict:
        if not question or not question.strip():
            raise ValueError("Empty question")

        # Step 1 — parse the question.
        logger.info("[query-article-status] parsing question via LLM")
        parsed = await self._llm.generate_structured_response(
            prompt=f"{_PARSE_PROMPT}\n\nCÂU HỎI: {question.strip()}",
            response_schema=_PARSE_SCHEMA,
        )
        parsed = parsed or {}
        law_number = (parsed.get("law_number") or "").strip()
        law_name = (parsed.get("law_name") or "").strip()
        article_so = parsed.get("article_so")
        intent = parsed.get("intent") or "other"

        if not law_number and not law_name:
            return {
                "question": question,
                "parsed": parsed,
                "document": None,
                "article": None,
                "amendments": [],
                "answer": (
                    "Câu hỏi không đề cập đến một văn bản pháp lý cụ thể nên hệ thống "
                    "không thể truy vấn graph. Vui lòng nêu rõ số hiệu hoặc tên văn bản."
                ),
            }

        # Step 2 — fuzzy-match the document in the KG.
        async with LegalKGReader() as kg:
            if not kg.enabled:
                raise RuntimeError("Neo4j is not configured; cannot perform reverse query")

            documents = await kg.list_documents()
            matched_doc_id, score = _find_best_document(
                law_number, law_name, "", documents
            )
            logger.info(
                "[query-article-status] fuzzy match law='%s' name='%s' → doc_id=%s score=%.3f",
                law_number, law_name, matched_doc_id, score,
            )

            if not matched_doc_id:
                return {
                    "question": question,
                    "parsed": parsed,
                    "document": None,
                    "article": None,
                    "amendments": [],
                    "answer": (
                        f"Không tìm thấy văn bản tương ứng với '{law_number or law_name}' "
                        "trong Knowledge Graph."
                    ),
                }

            doc_summary = await kg.get_document_summary(matched_doc_id)
            article_node = (
                await kg.get_article_node(matched_doc_id, int(article_so))
                if isinstance(article_so, int)
                else None
            )
            inbound = await kg.get_inbound_lifecycle(
                matched_doc_id,
                int(article_so) if isinstance(article_so, int) else None,
            )

        # Step 3 — LLM synthesizes a natural-language answer.
        logger.info("[query-article-status] synthesizing answer via LLM (intent=%s)", intent)
        answer_prompt = _build_answer_prompt(
            question, parsed, doc_summary, article_node, inbound
        )
        try:
            response = await self._llm.generate_response(
                prompt=answer_prompt,
                system_prompt=_ANSWER_SYSTEM_PROMPT,
                temperature=0.2,
            )
            answer = (response or {}).get("content") or ""
        except Exception:
            logger.exception("[query-article-status] LLM answer synthesis failed")
            answer = ""

        return {
            "question": question,
            "parsed": parsed,
            "document": doc_summary,
            "article": article_node,
            "amendments": inbound,
            "answer": answer.strip(),
        }
