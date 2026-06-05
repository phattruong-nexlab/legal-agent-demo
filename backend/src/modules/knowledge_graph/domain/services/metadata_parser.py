"""Step 2 — Raw text → DocumentMetadata (regex-first, section 2)."""

from __future__ import annotations

import re

from ..entity.document import DocumentMetadata, LegalBasisRef, RawDocument
from ..entity.enums import DOC_TYPE_LABEL
from .text_normalizer import (
    detect_doc_type,
    normalize_nfc,
    parse_vietnamese_date,
)

# --- Số hiệu ---------------------------------------------------------------

_SO_HIEU_PATTERNS = [
    re.compile(r"Số:\s*(\d+\s*/\s*\d{4}\s*/\s*TT-[A-ZĐ]+)", re.I),
    re.compile(r"Số:\s*(\d+\s*/\s*\d{4}\s*/\s*NĐ-CP)", re.I),
    re.compile(r"Số:\s*(\d+\s*/\s*\d{4}\s*/\s*QĐ-[A-ZĐ]+)", re.I),
    re.compile(r"Số:\s*(\d+\s*/\s*\d{4}\s*/\s*NQ-[A-ZĐ]+)", re.I),
    re.compile(r"Luật\s+số:?\s*(\d+\s*/\s*\d{4}\s*/\s*QH\d+)", re.I),
    re.compile(r"Số:\s*(\d+\s*/\s*\d{4}\s*/\s*[A-ZĐ]+-[A-ZĐ]+)", re.I),
    re.compile(r"Số:\s*(\d+\s*/\s*[A-ZĐ]+-[A-ZĐa-zđ]+)", re.I),
    # Without colon: "Số 06/2025/TT-BTTTT"
    re.compile(r"Số\s+(\d+\s*/\s*\d{4}\s*/\s*[A-ZĐ]+-[A-ZĐ]+)", re.I),
    # "Số hiệu: 06/2025/TT-BTTTT"
    re.compile(r"Số\s+hiệu\s*:?\s*(\d+\s*/\s*\d{4}\s*/\s*[A-ZĐ]+-[A-ZĐ]+)", re.I),
    # No year — old-style số hiệu, e.g. "Số: 518-TTg", "Số: 666/TTg", "Số: 123/CP".
    # Anchored to start-of-line + a MANDATORY colon so it matches the header số hiệu
    # and NOT inline references such as "Tờ trình số 2564/TCCB" in the body (lowercase
    # "số", mid-line, no colon). Accepts both "-" and "/" separators.
    # Kept last so the more specific year/hyphen patterns above win first.
    re.compile(r"(?m)^\s*Số\s*hiệu\s*:\s*(\d+\s*[-/]\s*[A-ZĐ][A-Za-zĐđ]+)", re.I),
    re.compile(r"(?m)^\s*Số\s*:\s*(\d+\s*[-/]\s*[A-ZĐ][A-Za-zĐđ]+)", re.I),
]

# Filename patterns like "TT_06_2025.pdf", "ND-12-2024.pdf"
_FILENAME_SO_HIEU = re.compile(
    r"^(TT|ND|NĐ|QĐ|QD|NQ|CT|PL|LUAT|BL|L)[-_](\d+)[-_](\d{4})",
    re.I,
)
_FILENAME_TYPE_SUFFIX: dict[str, str] = {
    "TT": "TT-UNKNOWN",
    "ND": "NĐ-CP",
    "NĐ": "NĐ-CP",
    "QD": "QĐ-UNKNOWN",
    "QĐ": "QĐ-UNKNOWN",
    "NQ": "NQ-UNKNOWN",
    "CT": "CT-UNKNOWN",
    "PL": "PL-UNKNOWN",
    "L": "QH00",
    "LUAT": "QH00",
    "BL": "QH00",
}


def _so_hieu_from_filename(filename: str) -> str | None:
    """Derive a synthetic số hiệu from filenames like TT_06_2025.pdf."""
    # Strip path separators and extension
    stem = filename.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    m = _FILENAME_SO_HIEU.match(stem)
    if not m:
        return None
    doc_type = m.group(1).upper()
    number, year = m.group(2), m.group(3)
    suffix = _FILENAME_TYPE_SUFFIX.get(doc_type, f"{doc_type}-UNKNOWN")
    return f"{number}/{year}/{suffix}"

_NGAY_BH = re.compile(
    r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I
)
_NGAY_HL = re.compile(
    r"có\s+hiệu\s+lực\s+(?:thi\s+hành\s+)?(?:kể\s+)?từ\s+ngày\s+"
    r"(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    re.I,
)
_NGUOI_KY = re.compile(
    r"(?:THỨ TRƯỞNG|BỘ TRƯỞNG|CHỦ TỊCH|THỦ TƯỚNG|TỔNG\s+\S+|"
    r"KT\.\s*BỘ TRƯỞNG)\s*\n+\s*"
    r"([A-ZĐÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ"
    r"ÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ][A-ZĐÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌ"
    r"ÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ\s]{2,40})",
)
_CO_QUAN = re.compile(
    r"(BỘ\s+[A-ZĐÀ-Ỹ\s]+|CHÍNH PHỦ|QUỐC HỘI|"
    r"ỦY BAN[A-ZĐÀ-Ỹ\s]+|THỦ TƯỚNG CHÍNH PHỦ)"
)
_CHUC_VU = re.compile(r"(THỨ TRƯỞNG|BỘ TRƯỞNG|CHỦ TỊCH|THỦ TƯỚNG|KT\.\s*BỘ TRƯỞNG)")

# `Căn cứ <name> ... [ngày dd tháng mm năm yyyy];`
_CAN_CU = re.compile(
    r"Căn cứ\s+(.+?)(?:;|\n(?=Căn cứ)|\nTheo|\nXét)",
    re.S | re.I,
)
_SO_HIEU_IN_TEXT = re.compile(r"\d+\s*/\s*\d{4}\s*/\s*[A-ZĐ]+(?:-[A-ZĐ]+)?")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def parse_metadata(raw: RawDocument) -> DocumentMetadata:
    """Scan the WHOLE document (số hiệu/ngày BH on page 1, ngày HL in the last
    Điều) and build a DocumentMetadata. Sets `incomplete=True` when a mandatory
    field cannot be parsed instead of raising.
    """
    text = normalize_nfc(raw.full_text)
    first_page = normalize_nfc(raw.pages[0].text) if raw.pages else text

    meta = DocumentMetadata()

    # Số hiệu — try text patterns first, then fall back to filename
    for pat in _SO_HIEU_PATTERNS:
        m = pat.search(text)
        if m:
            meta.so_hieu = re.sub(r"\s+", "", m.group(1))
            break
    if not meta.so_hieu:
        meta.so_hieu = _so_hieu_from_filename(raw.source_file) or ""

    meta.loai_code = detect_doc_type(meta.so_hieu)
    meta.loai = DOC_TYPE_LABEL.get(meta.loai_code, "")

    # Tên: first ALL-CAPS title block after the document type line.
    title_match = re.search(
        r"(?:THÔNG TƯ|NGHỊ ĐỊNH|QUYẾT ĐỊNH|LUẬT|NGHỊ QUYẾT|"
        r"BỘ LUẬT|PHÁP LỆNH|CHỈ THỊ)\s*\n+\s*(.+?)(?:\n\s*\n|Căn cứ)",
        first_page,
        re.S | re.I,
    )
    if title_match:
        meta.ten = _clean(title_match.group(1))

    # Ngày ban hành (first occurrence, normally page 1).
    m = _NGAY_BH.search(first_page) or _NGAY_BH.search(text)
    if m:
        meta.ngay_ban_hanh = parse_vietnamese_date(m.group(0))

    # Ngày hiệu lực (typically in the final Điều).
    m = _NGAY_HL.search(text)
    if m:
        meta.ngay_hieu_luc = parse_vietnamese_date(m.group(0))

    # Cơ quan ban hành / người ký / chức vụ.
    m = _CO_QUAN.search(first_page)
    if m:
        meta.co_quan_ban_hanh = _clean(m.group(1)).title()
    m = _CHUC_VU.search(text)
    if m:
        meta.chuc_vu_nguoi_ky = _clean(m.group(1))
    m = _NGUOI_KY.search(text)
    if m:
        meta.nguoi_ky = _clean(m.group(1))

    # Căn cứ pháp lý.
    for cc in _CAN_CU.finditer(text):
        block = _clean(cc.group(1))
        sh = _SO_HIEU_IN_TEXT.search(block)
        ref = LegalBasisRef(
            so_hieu=re.sub(r"\s+", "", sh.group(0)) if sh else block[:120],
            ngay=parse_vietnamese_date(block),
        )
        meta.can_cu_phap_ly.append(ref)

    meta.incomplete = not (meta.so_hieu and meta.ngay_ban_hanh)
    return meta
