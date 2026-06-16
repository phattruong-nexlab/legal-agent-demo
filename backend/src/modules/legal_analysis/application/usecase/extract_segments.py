"""Trích đơn vị cấu trúc lớn nhất của văn bản đầu vào (Chương → Điều → Toàn văn).

Mục tiêu: chuyển PDF → markdown ĐÚNG 1 LẦN, parse cấu trúc một cách KHOAN DUNG
(không raise khi đánh số không liên tục), rồi cắt văn bản thành các "segment" theo
đơn vị cao nhất hiện diện. Các segment này vừa hiển thị trên UI, vừa được dùng lại
trực tiếp ở bước audit (không cần convert lại).
"""

import logging
import re

from src.modules.document_processing.application.usecase.convert_to_markdown import (
    ConvertToMarkdownUseCase,
)
from src.modules.knowledge_graph.domain.entity.document import Article, Chapter
from src.modules.knowledge_graph.domain.services.structure_parser import parse_structure
from src.shared.infrastructure.llm_engine.interfaces import LLMEngine
from src.shared.infrastructure.ocr_engine.interfaces import OCREngine

logger = logging.getLogger(__name__)

# Giới hạn độ dài nội dung mỗi segment đưa vào prompt (kiểm soát token/độ trễ).
_MAX_SEGMENT_CHARS = 12000


def _markdown_to_plain(md: str) -> str:
    """Bỏ cú pháp markdown ở đầu dòng để regex của parse_structure khớp được.

    Ví dụ '## Chương I' → 'Chương I', '> nội dung' → 'nội dung',
    '**Điều 1.**' → 'Điều 1.'.
    """
    out: list[str] = []
    for line in md.split("\n"):
        s = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)  # ATX heading
        s = re.sub(r"^\s{0,3}>\s?", "", s)  # blockquote
        s = s.strip()
        if s.startswith("**") and s.endswith("**") and len(s) > 4:
            s = s[2:-2].strip()
        out.append(s)
    return "\n".join(out)


def _article_text(a: Article) -> str:
    parts: list[str] = [f"Điều {a.so}." + (f" {a.tieu_de}" if a.tieu_de else "")]
    if a.noi_dung_full:
        parts.append(a.noi_dung_full)
    for cl in a.clauses:
        parts.append(f"{cl.so}. {cl.noi_dung}".strip())
        for pt in cl.points:
            parts.append(f"{pt.ky_hieu}) {pt.noi_dung}".strip())
    return "\n".join(p for p in parts if p)


def _chapter_articles(ch: Chapter) -> list[Article]:
    arts = list(ch.articles)
    for sec in ch.sections:
        arts.extend(sec.articles)
    return sorted(arts, key=lambda x: x.thu_tu)


def _chapter_text(ch: Chapter) -> str:
    head = f"Chương {ch.so}" + (f" - {ch.tieu_de}" if ch.tieu_de else "")
    body = "\n\n".join(_article_text(a) for a in _chapter_articles(ch))
    return (head + "\n\n" + body).strip()


def _clip(text: str) -> str:
    return text if len(text) <= _MAX_SEGMENT_CHARS else text[:_MAX_SEGMENT_CHARS] + "\n[...]"


class ExtractSegmentsUseCase:
    """Use case: PDF → markdown → các segment theo đơn vị cấu trúc lớn nhất."""

    def __init__(self, llm_engine: LLMEngine, ocr_engine: OCREngine) -> None:
        self._llm_engine = llm_engine
        self._ocr_engine = ocr_engine
        self._convert_usecase = ConvertToMarkdownUseCase(llm_engine, ocr_engine)

    async def execute(self, file_bytes: bytes) -> dict:
        if not file_bytes:
            raise ValueError("Empty PDF bytes")

        logger.info("[extract-segments] Converting PDF to markdown")
        markdown = await self._convert_usecase.execute(file_bytes, None, None)

        plain = _markdown_to_plain(markdown)
        try:
            structure = parse_structure(plain, validate=False)
        except Exception:
            logger.exception("[extract-segments] parse_structure failed; fallback to full text")
            structure = None

        segments: list[dict] = []
        unit_type = "Toàn văn"

        if structure and structure.chapters:
            unit_type = "Chương"
            for i, ch in enumerate(structure.chapters, start=1):
                label = f"Chương {ch.so}" + (f" — {ch.tieu_de}" if ch.tieu_de else "")
                segments.append(
                    {"unit_type": unit_type, "index": i, "label": label,
                     "content": _clip(_chapter_text(ch))}
                )
        elif structure and structure.iter_articles():
            unit_type = "Điều"
            for i, a in enumerate(structure.iter_articles(), start=1):
                label = f"Điều {a.so}" + (f" — {a.tieu_de}" if a.tieu_de else "")
                segments.append(
                    {"unit_type": unit_type, "index": i, "label": label,
                     "content": _clip(_article_text(a))}
                )

        # Fallback: không parse được Chương/Điều → coi toàn văn là 1 segment.
        if not segments:
            unit_type = "Toàn văn"
            segments.append(
                {"unit_type": unit_type, "index": 1, "label": "Toàn văn bản",
                 "content": _clip(markdown)}
            )

        logger.info("[extract-segments] unit=%s, segments=%d", unit_type, len(segments))
        return {"unit_type": unit_type, "segments": segments}
