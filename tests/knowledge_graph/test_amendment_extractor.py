from src.modules.knowledge_graph.domain.entity.enums import (
    DocClass,
    RelationType,
)
from src.modules.knowledge_graph.domain.services.amendment_extractor import (
    extract_amendments,
    find_target_so_hieu,
)
from src.modules.knowledge_graph.domain.services.metadata_parser import (
    parse_metadata,
)
from src.modules.knowledge_graph.domain.entity.document import (
    DocumentMetadata,
    RawDocument,
    RawPage,
)
from src.modules.knowledge_graph.domain.services.structure_parser import (
    parse_structure,
)

DOC = """Điều 1. Sửa đổi, bổ sung một số điều của Quy chế tuyển sinh ban hành kèm theo Thông tư số 08/2022/TT-BGDĐT ngày 06 tháng 6 năm 2022
1. Sửa đổi, bổ sung khoản 18 Điều 2 như sau:
"18. Nội dung mới của khoản 18."
2. Bãi bỏ Điều 18.
3. Thay thế Phụ lục II.
Điều 2. Hiệu lực thi hành
1. Thông tư này có hiệu lực thi hành kể từ ngày 05 tháng 5 năm 2025.
"""


def test_find_target_so_hieu():
    structure = parse_structure(DOC)
    target = find_target_so_hieu(structure, DocumentMetadata())
    assert target == "08/2022/TT-BGDĐT"


def test_extract_amendments_counts():
    structure = parse_structure(DOC)
    ams = extract_amendments("TT-2025-06", structure, DocumentMetadata(), DocClass.SUA_DOI)
    kinds = [a.type for a in ams]
    assert RelationType.AMENDS in kinds
    assert RelationType.REPEALS in kinds
    assert RelationType.REPLACES in kinds

    amends = [a for a in ams if a.type == RelationType.AMENDS][0]
    assert amends.target_article == 2
    assert amends.target_clause == 18
    assert amends.source_clause_id == "TT-2025-06#điều-1#khoản-1"


def test_extract_amendments_skipped_for_goc():
    structure = parse_structure(DOC)
    assert extract_amendments("L-2019-45", structure, DocumentMetadata(), DocClass.GOC) == []


def test_parse_metadata_smoke():
    raw = RawDocument(
        source_file="x.pdf",
        extracted_at="2025-05-05T00:00:00",
        pages=[RawPage(page_num=1, text="Số: 06/2025/TT-BGDĐT\nThông tư\nSửa đổi, bổ sung\nHà Nội, ngày 19 tháng 3 năm 2025")],
        total_pages=1,
    )
    meta = parse_metadata(raw)
    assert meta.so_hieu == "06/2025/TT-BGDĐT"
