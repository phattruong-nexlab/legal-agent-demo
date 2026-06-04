"""Step 5 — extract AMENDS/REPEALS/REPLACES instructions (section 5).

Regex-first. Anything that does not match a pattern is left for the optional
LLM fallback wired in the use-case layer (and flagged for manual review).
"""

from __future__ import annotations

import re

from ..entity.amendment import Amendment
from ..entity.document import (
    DocumentMetadata,
    ParsedStructure,
    make_clause_id,
    make_point_id,
)
from ..entity.enums import DocClass, RelationType, ScopeType

# Document the amending text targets, e.g.
# "...ban hành kèm theo Thông tư số 08/2022/TT-BGDĐT ngày 06 tháng 6 năm 2022".
_TARGET_DOC = re.compile(
    r"(?:kèm theo\s+)?(?:Thông tư|Nghị định|Quyết định|Luật|Nghị quyết|Pháp lệnh)"
    r"\s+số\s+(\d+\s*/\s*\d{4}\s*/\s*[A-ZĐ]+(?:-[A-ZĐ]+)?)",
    re.I,
)

_NUM = r"(\d+)"
_AMEND_PATTERNS = [
    re.compile(
        r"Sửa đổi,?\s*bổ sung\s+(?:điểm\s+([a-zđ])\s+)?khoản\s+" + _NUM
        + r"\s+Điều\s+" + _NUM,
        re.I,
    ),
    re.compile(r"Sửa đổi\s+điểm\s+([a-zđ])\s+khoản\s+" + _NUM + r"\s+Điều\s+" + _NUM, re.I),
    re.compile(r"Sửa đổi,?\s*bổ sung\s+Điều\s+" + _NUM, re.I),
    re.compile(r"Bổ sung\s+khoản\s+" + _NUM + r"\s+Điều\s+" + _NUM, re.I),
    re.compile(r"Bổ sung\s+Điều\s+" + _NUM, re.I),
]
_REPEAL_PATTERNS = [
    re.compile(r"Bãi bỏ\s+khoản\s+" + _NUM + r"\s+Điều\s+" + _NUM, re.I),
    re.compile(r"Bãi bỏ\s+Điều\s+" + _NUM, re.I),
    re.compile(r'Bãi bỏ\s+cụm từ\s+"([^"]+)"', re.I),
]
_REPLACE_PATTERNS = [
    re.compile(r"Thay thế\s+Phụ lục\s+([IVXLC]+|\d+)", re.I),
    re.compile(r'Thay thế\s+cụm từ\s+"([^"]+)"\s+bằng\s+cụm từ\s+"([^"]+)"', re.I),
]
_QUOTED = re.compile(r'"([^"]{3,})"', re.S)


def _quoted_content(text: str) -> str:
    m = _QUOTED.search(text)
    return m.group(1).strip() if m else ""


def find_target_so_hieu(structure: ParsedStructure, metadata: DocumentMetadata) -> str:
    for art in structure.iter_articles():
        blob = (art.tieu_de or "") + "\n" + art.noi_dung_full
        for cl in art.clauses:
            blob += "\n" + cl.noi_dung
        m = _TARGET_DOC.search(blob)
        if m:
            return re.sub(r"\s+", "", m.group(1))
    m = _TARGET_DOC.search(metadata.ten or "")
    return re.sub(r"\s+", "", m.group(1)) if m else ""


def _emit(
    text: str, source_id: str, target_so_hieu: str
) -> list[Amendment]:
    out: list[Amendment] = []

    for pat in _AMEND_PATTERNS:
        for m in pat.finditer(text):
            g = m.groups()
            point = g[0] if len(g) == 3 else None
            nums = [x for x in g if x and x.isdigit()]
            article = int(nums[-1]) if nums else None
            clause = int(nums[-2]) if len(nums) >= 2 else None
            out.append(
                Amendment(
                    type=RelationType.AMENDS,
                    source_clause_id=source_id,
                    target_doc_so_hieu=target_so_hieu,
                    scope=m.group(0).strip(),
                    scope_type=(
                        ScopeType.POINT
                        if point
                        else ScopeType.CLAUSE
                        if clause
                        else ScopeType.ARTICLE
                    ),
                    target_article=article,
                    target_clause=clause,
                    target_point=point,
                    new_content=_quoted_content(text),
                )
            )

    for pat in _REPEAL_PATTERNS:
        for m in pat.finditer(text):
            g = [x for x in m.groups() if x]
            nums = [x for x in g if x.isdigit()]
            out.append(
                Amendment(
                    type=RelationType.REPEALS,
                    source_clause_id=source_id,
                    target_doc_so_hieu=target_so_hieu,
                    scope=m.group(0).strip(),
                    scope_type=(
                        ScopeType.CLAUSE
                        if len(nums) >= 2
                        else ScopeType.ARTICLE
                        if nums
                        else ScopeType.PHRASE
                    ),
                    target_article=int(nums[-1]) if nums else None,
                    target_clause=int(nums[0]) if len(nums) >= 2 else None,
                )
            )

    for pat in _REPLACE_PATTERNS:
        for m in pat.finditer(text):
            out.append(
                Amendment(
                    type=RelationType.REPLACES,
                    source_clause_id=source_id,
                    target_doc_so_hieu=target_so_hieu,
                    scope=m.group(0).strip(),
                    scope_type=ScopeType.APPENDIX
                    if "Phụ lục" in m.group(0)
                    else ScopeType.PHRASE,
                )
            )
    return out


def extract_amendments(
    doc_id: str,
    structure: ParsedStructure,
    metadata: DocumentMetadata,
    doc_class: DocClass,
) -> list[Amendment]:
    if doc_class != DocClass.SUA_DOI:
        return []

    target = find_target_so_hieu(structure, metadata)
    amendments: list[Amendment] = []

    for art in structure.iter_articles():
        art_id = f"{doc_id}#điều-{art.so}"
        if not art.clauses:
            amendments.extend(_emit(art.noi_dung_full, art_id, target))
            continue
        for clause in art.clauses:
            clause_id = make_clause_id(art_id, clause.so)
            if clause.points:
                for pt in clause.points:
                    amendments.extend(
                        _emit(pt.noi_dung, make_point_id(clause_id, pt.ky_hieu), target)
                    )
            else:
                amendments.extend(_emit(clause.noi_dung, clause_id, target))

    return amendments
