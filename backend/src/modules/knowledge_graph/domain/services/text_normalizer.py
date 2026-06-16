"""Pure text/identifier normalisation helpers (step 7.1 / 7.2).

No I/O — safe to live in the domain layer.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from ..entity.enums import DocTypeCode

# Prefix used in the canonical doc_id ("{prefix}-{year}-{number}").
# Note: this differs from DocTypeCode for Luật ("L", not "LUAT") because the
# spec examples (section 3.2) use "L-2019-45".
DOC_ID_PREFIX: dict[DocTypeCode, str] = {
    DocTypeCode.LUAT: "L",
    DocTypeCode.NQ: "NQ",
    DocTypeCode.ND: "ND",
    DocTypeCode.TT: "TT",
    DocTypeCode.QD: "QD",
    DocTypeCode.CT: "CT",
    DocTypeCode.PL: "PL",
    DocTypeCode.UNKNOWN: "VB",
}

# Suffix of the "số hiệu" → document type.
_SUFFIX_TYPE: list[tuple[re.Pattern[str], DocTypeCode]] = [
    (re.compile(r"/QH\d+$", re.I), DocTypeCode.LUAT),
    (re.compile(r"/UBTVQH\d+$", re.I), DocTypeCode.PL),
    (re.compile(r"/NĐ-CP$", re.I), DocTypeCode.ND),
    (re.compile(r"/TT-", re.I), DocTypeCode.TT),
    (re.compile(r"/TTLT-", re.I), DocTypeCode.TT),
    (re.compile(r"/NQ-", re.I), DocTypeCode.NQ),
    (re.compile(r"/QĐ-", re.I), DocTypeCode.QD),
    (re.compile(r"/CT-", re.I), DocTypeCode.CT),
]

_MONTHS = r"(\d{1,2})"
_DATE_VN = re.compile(
    r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I
)
_DATE_SLASH = re.compile(r"\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})\b")


def normalize_nfc(text: str) -> str:
    """Unicode-normalise to NFC and collapse Windows newlines.

    Many old Vietnamese legal PDFs ship combining/legacy code points; NFC makes
    downstream regex deterministic.
    """
    text = unicodedata.normalize("NFC", text or "")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def detect_doc_type(so_hieu: str) -> DocTypeCode:
    for pattern, code in _SUFFIX_TYPE:
        if pattern.search(so_hieu or ""):
            return code
    return DocTypeCode.UNKNOWN


def so_hieu_to_doc_id(so_hieu: str, fallback_year: int | None = None) -> str | None:
    """Normalise a "số hiệu" to the canonical doc_id.

    "08/2022/TT-BGDĐT" → "TT-2022-08"
    "45/2019/QH14"     → "L-2019-45"
    "99/2019/NĐ-CP"    → "ND-2019-99"
    "666/QĐ-TTg"       → "QD-{fallback_year}-666" (no year in số hiệu)

    Returns None when nothing parseable is found.
    """
    if not so_hieu:
        return None
    s = so_hieu.strip()
    code = detect_doc_type(s)
    prefix = DOC_ID_PREFIX[code]

    # The number token is kept verbatim (leading zeros preserved) per the
    # spec examples: "08/2022/TT-BGDĐT" → "TT-2022-08".
    m = re.match(r"\s*(\d+)\s*/\s*(\d{4})\s*/", s)
    if m:
        number, year = m.group(1), m.group(2)
        return f"{prefix}-{year}-{number}"

    # Forms without an embedded year, e.g. "666/QĐ-TTg", "518-TTg".
    m = re.match(r"\s*(\d+)\s*[-/]", s)
    if m and fallback_year:
        return f"{prefix}-{fallback_year}-{m.group(1)}"
    return None


def parse_vietnamese_date(text: str) -> date | None:
    """Parse the first date found in `text`.

    Accepts "ngày 06 tháng 6 năm 2022", "06/6/2022", "27-5-2009".
    """
    if not text:
        return None
    m = _DATE_VN.search(text)
    if not m:
        m = _DATE_SLASH.search(text)
    if not m:
        return None
    day, month, year = (int(g) for g in m.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None
