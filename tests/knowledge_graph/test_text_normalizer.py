from datetime import date

import pytest

from src.modules.knowledge_graph.domain.entity.enums import DocTypeCode
from src.modules.knowledge_graph.domain.services.text_normalizer import (
    detect_doc_type,
    parse_vietnamese_date,
    so_hieu_to_doc_id,
)


@pytest.mark.parametrize(
    "so_hieu,expected",
    [
        ("08/2022/TT-BGDĐT", "TT-2022-08"),
        ("06/2025/TT-BGDĐT", "TT-2025-06"),
        ("45/2019/QH14", "L-2019-45"),
        ("99/2019/NĐ-CP", "ND-2019-99"),
        ("37/2025/NĐ-CP", "ND-2025-37"),
    ],
)
def test_so_hieu_to_doc_id(so_hieu, expected):
    assert so_hieu_to_doc_id(so_hieu) == expected


def test_so_hieu_without_year_uses_fallback():
    assert so_hieu_to_doc_id("666/QĐ-TTg", fallback_year=2024) == "QD-2024-666"


def test_detect_doc_type():
    assert detect_doc_type("06/2025/TT-BGDĐT") == DocTypeCode.TT
    assert detect_doc_type("45/2019/QH14") == DocTypeCode.LUAT
    assert detect_doc_type("99/2019/NĐ-CP") == DocTypeCode.ND


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ngày 06 tháng 6 năm 2022", date(2022, 6, 6)),
        ("06/6/2022", date(2022, 6, 6)),
        ("27-5-2009", date(2009, 5, 27)),
    ],
)
def test_parse_vietnamese_date(text, expected):
    assert parse_vietnamese_date(text) == expected
