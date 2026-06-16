import asyncio
import difflib
import logging
import re
import time
from collections import defaultdict

from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.persistence.legal_kg_reader import LegalKGReader

logger = logging.getLogger(__name__)

# Số LLM call chạy song song tối đa (tránh rate-limit). Mỗi cặp
# (segment input × đơn vị căn cứ) là 1 call.
_MAX_CONCURRENCY = 8
# Giới hạn độ dài nội dung mỗi đơn vị căn cứ đưa vào prompt.
_MAX_UNIT_CHARS = 12000


def _normalize_key(s: str) -> str:
    return re.sub(r"[\s/\\\-\.]+", "-", (s or "").strip().lower())


def _extract_year(date_str: str) -> str:
    """Extract 4-digit year from either 'D-M-YYYY' or 'YYYY-MM-DD' format."""
    if not date_str:
        return ""
    if len(date_str) >= 4 and date_str[:4].isdigit() and (len(date_str) == 4 or date_str[4] == "-"):
        return date_str[:4]
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

    Strategy:
      - law_number present → 0.70 * so_hieu_sim + 0.30 * year_match
      - law_number absent  → 0.70 * ten_sim     + 0.30 * year_match
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


def _clip(text: str) -> str:
    return text if len(text) <= _MAX_UNIT_CHARS else text[:_MAX_UNIT_CHARS] + "\n[...]"


def _article_block(a: dict) -> str:
    head = f"Điều {a.get('so')}" + (f" - {a['tieu_de']}" if a.get("tieu_de") else "")
    return f"{head}\n{a.get('noi_dung') or ''}".strip()


async def _build_reference_units(kg_reader: LegalKGReader, doc_id: str) -> tuple[str, list[dict]]:
    """Lấy 'đơn vị cơ bản lớn nhất' của văn bản căn cứ: Chương nếu có, không thì Điều.

    Trả về (unit_type, units), mỗi unit = {"label", "content"}.
    """
    chapters = await kg_reader.get_chapters(doc_id)
    if chapters:
        units = []
        for ch in chapters:
            label = f"Chương {ch['so']}" + (f" - {ch['tieu_de']}" if ch.get("tieu_de") else "")
            body = "\n\n".join(_article_block(a) for a in ch.get("articles", []))
            units.append({"label": label, "content": _clip(f"{label}\n\n{body}".strip())})
        return "Chương", units

    articles = await kg_reader.get_articles(doc_id)
    units = [
        {
            "label": f"Điều {a.get('so')}" + (f" - {a['tieu_de']}" if a.get("tieu_de") else ""),
            "content": _clip(_article_block(a)),
        }
        for a in articles
    ]
    return "Điều", units


_PAIR_CHECK_PROMPT = """\
Bạn là chuyên gia đánh giá tuân thủ pháp lý cho một bản DEMO, đánh giá theo hướng
RẤT KHOAN DUNG (lenient).

Nhiệm vụ: so sánh PHẦN VĂN BẢN ĐẦU VÀO với MỘT ĐƠN VỊ của văn bản tham chiếu.
1. Xác định phần đầu vào có liên quan tới đơn vị tham chiếu này không (applicable).
2. Nếu có liên quan, đánh giá mức độ tuân thủ.

Nguyên tắc chấm điểm (BẮT BUỘC, ưu tiên KHOAN DUNG):
- MẶC ĐỊNH là "Tuân thủ". Chỉ hạ xuống mức thấp hơn khi có bằng chứng rõ ràng.
- Chỉ trả "Không tuân thủ" khi có MÂU THUẪN HIỂN NHIÊN, TRỰC TIẾP và chỉ ra được
  chính xác câu/quy định bị vi phạm. Khác biệt nhỏ, diễn đạt khác, hay thiếu chi tiết
  KHÔNG phải là không tuân thủ.
- Nếu liên quan nhưng không chắc chắn / thiếu thông tin → vẫn để "Tuân thủ".
- Chỉ khi nội dung KHÔNG thuộc phạm vi điều chỉnh → applicable=false, status="Không liên quan".
- Hạn chế tối đa dùng "Cần kiểm tra"; chỉ dùng khi thật sự có dấu hiệu nghi vấn nhưng
  chưa đủ kết luận vi phạm.
- LUÔN nêu lý do ngắn gọn trong "reason", kể cả khi "Tuân thủ"
  (ví dụ: phù hợp ở điểm nào, không có nội dung trái quy định).
- Chỉ trả về JSON, không thêm markdown hay chữ ngoài JSON.
"""

_PAIR_CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "applicable": {"type": "boolean"},
        "status": {
            "type": "string",
            "enum": ["Tuân thủ", "Không tuân thủ", "Cần kiểm tra", "Không liên quan"],
        },
        "reason": {"type": "string"},
    },
    "required": ["applicable", "status", "reason"],
}


def _aggregate_pairs(pair_results: list[dict]) -> dict:
    """Gom kết quả của 1 segment input đối chiếu với NHIỀU đơn vị căn cứ (lenient).

    - Không cặp nào liên quan → "Không liên quan".
    - Có cặp "Không tuân thủ" → "Không tuân thủ" (kèm lý do từ cặp đó).
    - Ngược lại có cặp "Tuân thủ" → "Tuân thủ".
    - Còn lại → "Cần kiểm tra".
    """
    applicable = [p for p in pair_results if p.get("applicable")]
    if not applicable:
        return {"applicable": False, "status": "Không liên quan", "reason": ""}

    violations = [p for p in applicable if p.get("status") == "Không tuân thủ"]
    if violations:
        p = violations[0]
        return {
            "applicable": True,
            "status": "Không tuân thủ",
            "reason": f"(so với {p['ref_label']}) {p.get('reason') or ''}".strip(),
        }

    compliant = [p for p in applicable if p.get("status") == "Tuân thủ"]
    if compliant:
        p = compliant[0]
        return {
            "applicable": True,
            "status": "Tuân thủ",
            "reason": f"(so với {p['ref_label']}) {p.get('reason') or ''}".strip(),
        }

    p = applicable[0]
    return {
        "applicable": True,
        "status": "Cần kiểm tra",
        "reason": f"(so với {p['ref_label']}) {p.get('reason') or ''}".strip(),
    }


def _aggregate_status(segment_results: list[dict]) -> str:
    """Gom trạng thái các segment thành trạng thái tổng cho 1 căn cứ (lenient)."""
    applicable = [r for r in segment_results if r.get("applicable")]
    if not applicable:
        return "Không liên quan"
    statuses = {r.get("status") for r in applicable}
    if "Không tuân thủ" in statuses:
        return "Không tuân thủ"
    if "Tuân thủ" in statuses:
        return "Tuân thủ"
    return "Cần kiểm tra"


class AuditByGraphUseCase:
    """Audit tuân thủ: mỗi đơn vị input × mỗi đơn vị lớn nhất của văn bản căn cứ.

    Đơn vị input (Chương/Điều) lấy từ /extract-segments. Đơn vị căn cứ (Chương nếu
    có, không thì Điều) lấy từ Knowledge Graph. Mỗi cặp = 1 LLM call, chạy song song
    có giới hạn; chấm điểm theo hướng khoan dung cho demo.
    """

    def __init__(self, llm_engine: LLMEngine) -> None:
        self._llm_engine = llm_engine

    async def execute(
        self,
        segments: list[dict],
        legal_bases: list[dict],
        audited_document: dict,
    ) -> dict:
        if not segments:
            raise ValueError("Empty segments")

        unit_type = segments[0].get("unit_type") or "Chương"

        async with LegalKGReader() as kg_reader:
            if not kg_reader.enabled:
                raise RuntimeError("Neo4j is not configured; cannot perform KG-based audit")

            logger.info("[audit-by-graph] Listing KG documents for fuzzy matching")
            documents = await kg_reader.list_documents()

            # Bước 1: phân giải từng căn cứ → matched doc + các đơn vị căn cứ (no LLM).
            contexts: list[dict] = []
            for item in legal_bases:
                law_number = (item.get("law_number") or "").strip()
                law_name = (item.get("law_name") or "").strip()
                date = (item.get("date") or "").strip()
                audited_law = law_number or law_name

                ctx: dict = {
                    "audited_law": audited_law,
                    "date": date,
                    "matched_doc_id": None,
                    "reference_units": [],
                    "reference_unit_type": "",
                    "overall_status": None,
                    "explanation": "",
                }

                if not audited_law:
                    ctx["overall_status"] = "Cần kiểm tra"
                    ctx["explanation"] = "Thiếu số hiệu và tên văn bản."
                    contexts.append(ctx)
                    continue

                matched_doc_id, score = _find_best_document(
                    law_number, law_name, date, documents
                )
                logger.info(
                    "[audit-by-graph] Fuzzy match '%s' (%s): doc_id=%s score=%.3f",
                    audited_law, date, matched_doc_id, score,
                )

                if not matched_doc_id:
                    ctx["overall_status"] = "Không tìm thấy trong hệ thống"
                    contexts.append(ctx)
                    continue

                ctx["matched_doc_id"] = matched_doc_id
                ref_unit_type, ref_units = await _build_reference_units(
                    kg_reader, matched_doc_id
                )
                if not ref_units:
                    ctx["overall_status"] = "Cần kiểm tra"
                    ctx["explanation"] = "Văn bản chưa có điều khoản trong hệ thống."
                    contexts.append(ctx)
                    continue

                ctx["reference_unit_type"] = ref_unit_type
                ctx["reference_units"] = ref_units
                contexts.append(ctx)

        # Bước 2: dựng mọi cặp (segment input × đơn vị căn cứ), chạy song song.
        sem = asyncio.Semaphore(_MAX_CONCURRENCY)
        keys: list[tuple[int, int]] = []  # (context_index, segment_index_in_list)
        tasks = []
        for ci, ctx in enumerate(contexts):
            for si, seg in enumerate(segments):
                for unit in ctx["reference_units"]:
                    keys.append((ci, si))
                    tasks.append(self._check_pair(sem, seg, unit))

        logger.info(
            "[audit-by-graph] LLM calls: %d, concurrency=%d", len(tasks), _MAX_CONCURRENCY
        )
        t0 = time.perf_counter()
        flat_results = await asyncio.gather(*tasks) if tasks else []
        logger.info(
            "[audit-by-graph] %d LLM calls finished in %.1fs",
            len(tasks), time.perf_counter() - t0,
        )

        # Bước 3: gom theo (căn cứ, segment input) → 1 kết quả/segment; rồi gom theo căn cứ.
        pairs_by_ctx_seg: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for (ci, si), res in zip(keys, flat_results):
            pairs_by_ctx_seg[(ci, si)].append(res)

        results: list[dict] = []
        for ci, ctx in enumerate(contexts):
            seg_results: list[dict] = []
            if ctx["reference_units"]:
                for si, seg in enumerate(segments):
                    agg = _aggregate_pairs(pairs_by_ctx_seg.get((ci, si), []))
                    seg_results.append(
                        {
                            "segment_index": seg.get("index"),
                            "segment_label": seg.get("label")
                            or f"Phần {seg.get('index')}",
                            "applicable": agg["applicable"],
                            "status": agg["status"],
                            "reason": agg["reason"],
                        }
                    )

            overall = (
                ctx["overall_status"]
                if ctx["overall_status"] is not None
                else _aggregate_status(seg_results)
            )
            results.append(
                {
                    "audited_law": ctx["audited_law"],
                    "date": ctx["date"],
                    "matched_doc_id": ctx["matched_doc_id"],
                    "overall_status": overall,
                    "explanation": ctx["explanation"],
                    "segments": seg_results,
                }
            )

        return {"unit_type": unit_type, "results": results}

    async def _check_pair(
        self,
        sem: asyncio.Semaphore,
        segment: dict,
        ref_unit: dict,
    ) -> dict:
        in_label = segment.get("label") or f"Phần {segment.get('index')}"
        in_content = segment.get("content") or ""
        ref_label = ref_unit.get("label") or "đơn vị tham chiếu"
        ref_content = ref_unit.get("content") or ""

        prompt = (
            f"{_PAIR_CHECK_PROMPT}\n\n"
            f"PHẦN VĂN BẢN ĐẦU VÀO ({in_label}):\n{in_content}\n\n"
            f"ĐƠN VỊ THAM CHIẾU ({ref_label}):\n{ref_content}"
        )

        async with sem:
            try:
                response = await self._llm_engine.generate_structured_response(
                    prompt, _PAIR_CHECK_SCHEMA
                )
                applicable = bool((response or {}).get("applicable"))
                status = (response or {}).get("status") or "Tuân thủ"
                reason = (response or {}).get("reason") or ""
            except Exception:
                logger.exception(
                    "[audit-by-graph] LLM check failed: %s vs %s", in_label, ref_label
                )
                applicable = False
                status = "Không liên quan"
                reason = "Lỗi khi gọi LLM."

        if not applicable:
            status = "Không liên quan"

        return {
            "ref_label": ref_label,
            "applicable": applicable,
            "status": status,
            "reason": reason,
        }
