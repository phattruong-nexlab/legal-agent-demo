"""Step 6 — citation (dẫn chiếu) extraction (section 6).

Citations are *references*, not modifications. Internal references point at
"... Quy chế/Luật này"; external ones name another số hiệu.
"""

from __future__ import annotations

import re

from ..entity.amendment import Citation
from ..entity.document import ParsedStructure, make_clause_id

_INTERNAL = re.compile(
    r"(?:tại\s+)?(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)\s+(?:của\s+)?"
    r"(?:Quy chế|Luật|Nghị định|Thông tư|Quy định)\s+này",
    re.I,
)
_EXTERNAL = re.compile(
    r"(?:Thông tư|Nghị định|Luật|Quyết định|Nghị quyết|Pháp lệnh)\s+số\s+"
    r"(\d+\s*/\s*\d{4}\s*/\s*[A-ZĐ]+(?:-[A-ZĐ]+)?)",
    re.I,
)


def _scan(text: str, source_id: str) -> list[Citation]:
    out: list[Citation] = []
    for m in _INTERNAL.finditer(text):
        out.append(
            Citation(
                source_id=source_id,
                is_internal=True,
                target_article=int(m.group(2)),
                target_clause=int(m.group(1)) if m.group(1) else None,
                raw_text=m.group(0).strip(),
            )
        )
    for m in _EXTERNAL.finditer(text):
        out.append(
            Citation(
                source_id=source_id,
                is_internal=False,
                target_so_hieu=re.sub(r"\s+", "", m.group(1)),
                raw_text=m.group(0).strip(),
            )
        )
    return out


def extract_citations(doc_id: str, structure: ParsedStructure) -> list[Citation]:
    citations: list[Citation] = []
    for art in structure.iter_articles():
        art_id = f"{doc_id}#điều-{art.so}"
        citations.extend(_scan(art.noi_dung_full, art_id))
        for clause in art.clauses:
            clause_id = make_clause_id(art_id, clause.so)
            citations.extend(_scan(clause.noi_dung, clause_id))
            for pt in clause.points:
                citations.extend(_scan(pt.noi_dung, clause_id))
    return citations
