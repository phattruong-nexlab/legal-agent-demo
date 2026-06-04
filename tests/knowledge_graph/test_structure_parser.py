import pytest

from src.modules.knowledge_graph.domain.errors import StructureValidationError
from src.modules.knowledge_graph.domain.services.structure_parser import (
    parse_structure,
)

DOC = """Điều 1. Sửa đổi, bổ sung một số điều
1. Sửa đổi khoản 18 Điều 2 như sau:
"18. Mã trường trong tuyển sinh là một mã quy ước.
2. Dòng này nằm trong dấu nháy nên không tạo Khoản mới."
2. Bổ sung khoản 20 Điều 2.
Điều 2. Hiệu lực thi hành
1. Thông tư này có hiệu lực thi hành kể từ ngày 05 tháng 5 năm 2025.
"""


def test_parse_structure_basic():
    s = parse_structure(DOC)
    articles = s.iter_articles()
    assert [a.so for a in articles] == [1, 2]

    art1 = articles[0]
    # The "2." line inside the quoted block must NOT become a Khoản.
    assert [c.so for c in art1.clauses] == [1, 2]
    assert "không tạo Khoản mới" in art1.clauses[0].noi_dung


def test_non_continuous_dieu_raises():
    bad = "Điều 1. A\nĐiều 3. C\n"
    with pytest.raises(StructureValidationError):
        parse_structure(bad)


def test_point_order_validation():
    bad = "Điều 1. A\n1. khoản\na) điểm a\nc) điểm c sai thứ tự\n"
    with pytest.raises(StructureValidationError):
        parse_structure(bad)
