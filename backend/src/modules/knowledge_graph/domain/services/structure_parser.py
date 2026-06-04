"""Step 3 — Raw text → Chương/Điều/Khoản/Điểm (state machine, section 3)."""

from __future__ import annotations

import re

from ..entity.document import (
    Article,
    Chapter,
    Clause,
    ParsedStructure,
    Point,
)
from ..errors import StructureValidationError
from .text_normalizer import normalize_nfc

_CHUONG = re.compile(r"^\s*Chương\s+([IVXLCDM]+|\d+)\b\s*(.*)$", re.I)
_DIEU = re.compile(r"^\s*Điều\s+(\d+)\s*\.\s*(.*)$")
_KHOAN = re.compile(r"^\s*(\d+)\s*\.\s+(\S.*)$")
_DIEM = re.compile(r"^\s*([a-zđ])\s*\)\s+(\S.*)$", re.I)

# Vietnamese ordered point alphabet (legal drafting convention).
POINT_SEQUENCE = list("abcdeghiklmnopqrstuvxy")
POINT_SEQUENCE.insert(POINT_SEQUENCE.index("d") + 1, "đ")

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_to_int(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        val = _ROMAN.get(ch, 0)
        total += -val if val < prev else val
        prev = max(prev, val)
    return total


def _to_int(token: str) -> int:
    return int(token) if token.isdigit() else _roman_to_int(token)


def _count_quote_marks(line: str) -> int:
    """Number of straight/curly double-quote marks (used to track quoted
    blocks — quoted content must NOT spawn new nodes, section 3 note)."""
    return sum(line.count(q) for q in ('"', "“", "”", "„"))


def parse_structure(raw_text: str) -> ParsedStructure:
    text = normalize_nfc(raw_text)
    lines = text.split("\n")

    chapters: list[Chapter] = []
    root_articles: list[Article] = []

    cur_chapter: Chapter | None = None
    cur_article: Article | None = None
    cur_clause: Clause | None = None
    cur_point: Point | None = None

    art_order = 0
    in_quote = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # While inside a quoted block, every line is verbatim content.
        if in_quote:
            if cur_point is not None:
                cur_point.noi_dung += "\n" + stripped
            elif cur_clause is not None:
                cur_clause.noi_dung += "\n" + stripped
            elif cur_article is not None:
                cur_article.noi_dung_full += "\n" + stripped
            if _count_quote_marks(line) % 2 == 1:
                in_quote = False
            continue

        opens_quote = _count_quote_marks(line) % 2 == 1

        m = _CHUONG.match(stripped)
        if m:
            cur_chapter = Chapter(
                so=_to_int(m.group(1)), tieu_de=(m.group(2) or "").strip() or None
            )
            chapters.append(cur_chapter)
            cur_article = cur_clause = cur_point = None
            continue

        m = _DIEU.match(stripped)
        if m:
            art_order += 1
            cur_article = Article(
                so=int(m.group(1)),
                tieu_de=(m.group(2) or "").strip() or None,
                noi_dung_full="",
                thu_tu=art_order,
            )
            (cur_chapter.articles if cur_chapter else root_articles).append(
                cur_article
            )
            cur_clause = cur_point = None
            if opens_quote:
                in_quote = True
            continue

        m = _KHOAN.match(stripped)
        if m and cur_article is not None:
            cur_clause = Clause(
                so=int(m.group(1)),
                noi_dung=m.group(2).strip(),
                thu_tu=len(cur_article.clauses) + 1,
            )
            cur_article.clauses.append(cur_clause)
            cur_point = None
            if opens_quote:
                in_quote = True
            continue

        m = _DIEM.match(stripped)
        if m and cur_clause is not None:
            cur_point = Point(
                ky_hieu=m.group(1).lower(),
                noi_dung=m.group(2).strip(),
                thu_tu=len(cur_clause.points) + 1,
            )
            cur_clause.points.append(cur_point)
            if opens_quote:
                in_quote = True
            continue

        # Plain content line — append to the innermost open element.
        if cur_point is not None:
            cur_point.noi_dung += "\n" + stripped
        elif cur_clause is not None:
            cur_clause.noi_dung += "\n" + stripped
        elif cur_article is not None:
            cur_article.noi_dung_full += (
                ("\n" if cur_article.noi_dung_full else "") + stripped
            )
        if opens_quote:
            in_quote = True

    structure = ParsedStructure(chapters=chapters, articles=root_articles)
    _validate(structure)
    return structure


def _validate(structure: ParsedStructure) -> None:
    """Section 3 validation: Điều continuous from 1, Khoản continuous from 1,
    Điểm in canonical Vietnamese order."""
    articles = structure.iter_articles()
    if not articles:
        raise StructureValidationError("No Điều found in document")

    so_list = [a.so for a in articles]
    if so_list != list(range(1, len(so_list) + 1)):
        raise StructureValidationError(
            f"Điều numbers not continuous from 1: {so_list}"
        )

    for art in articles:
        if art.clauses:
            cl = [c.so for c in art.clauses]
            if cl != list(range(1, len(cl) + 1)):
                raise StructureValidationError(
                    f"Khoản not continuous in Điều {art.so}: {cl}"
                )
        for clause in art.clauses:
            for idx, pt in enumerate(clause.points):
                expected = POINT_SEQUENCE[idx] if idx < len(POINT_SEQUENCE) else "?"
                if pt.ky_hieu != expected:
                    raise StructureValidationError(
                        f"Điểm out of order in Điều {art.so} khoản "
                        f"{clause.so}: got '{pt.ky_hieu}', expected '{expected}'"
                    )
