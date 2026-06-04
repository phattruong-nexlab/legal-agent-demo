"""Legal Knowledge Graph Explorer — Streamlit UI.

Two pages:
  1. Knowledge Graph  — browse, search, visualize the Neo4j Aura graph.
  2. Audit (placeholder, coming soon).

Run:
  pip install -r requirements/fe.txt
  streamlit run fe/main.py
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from neo4j import GraphDatabase
from streamlit_agraph import Config, Edge, Node, agraph

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)


@dataclass(frozen=True)
class _FeSettings:
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str
    NEO4J_DATABASE: str
    BACKEND_URL: str


@lru_cache(maxsize=1)
def get_settings() -> _FeSettings:
    return _FeSettings(
        NEO4J_URI=os.getenv("NEO4J_URI", ""),
        NEO4J_USERNAME=os.getenv("NEO4J_USERNAME", ""),
        NEO4J_PASSWORD=os.getenv("NEO4J_PASSWORD", ""),
        NEO4J_DATABASE=os.getenv("NEO4J_DATABASE", ""),
        BACKEND_URL=os.getenv("BACKEND_URL", "http://localhost:8000"),
    )

st.set_page_config(
    page_title="Legal Knowledge Graph",
    page_icon="⚖️",
    layout="wide",
)


# ============================================================================
# Neo4j driver (cached for the session)
# ============================================================================


@st.cache_resource(show_spinner="Kết nối Neo4j Aura...")
def _get_driver():
    s = get_settings()
    if not s.NEO4J_URI:
        return None
    return GraphDatabase.driver(
        s.NEO4J_URI,
        auth=(s.NEO4J_USERNAME, s.NEO4J_PASSWORD),
    )


def run_records(cypher: str, params: dict | None = None) -> list[Any]:
    drv = _get_driver()
    if drv is None:
        return []
    s = get_settings()
    with drv.session(database=s.NEO4J_DATABASE or None) as sess:
        return list(sess.run(cypher, params or {}))


def run_dicts(cypher: str, params: dict | None = None) -> list[dict]:
    return [dict(r) for r in run_records(cypher, params)]


# ============================================================================
# Visual styling
# ============================================================================

LABEL_COLOR = {
    "Document": "#4F8EF7",
    "_Placeholder": "#B0BEC5",
    "Chapter": "#16A085",
    "Article": "#27AE60",
    "Clause": "#7DCEA0",
    "Point": "#A9DFBF",
    "Authority": "#E67E22",
    "DocumentType": "#9B59B6",
}

REL_COLOR = {
    # Lifecycle — warm, high-contrast palette
    "AMENDS": "#F77F00",      # vivid orange
    "REPEALS": "#D62828",     # vivid red
    "REPLACES": "#FF006E",    # hot pink / magenta
    # Provenance & citation — cool palette
    "BASED_ON": "#0077B6",    # deep blue
    "REFERENCES": "#2A9D8F",  # teal / emerald
    # Metadata — purple family
    "ISSUED_BY": "#6A4C93",   # royal purple
    "OF_TYPE": "#8338EC",     # violet
    # Structural — muted gray (kept low to not distract)
    "HAS_CHAPTER": "#B0BEC5",
    "HAS_ARTICLE": "#B0BEC5",
    "HAS_CLAUSE": "#CFD8DC",
    "HAS_POINT": "#ECEFF1",
}

REL_INFO: list[tuple[str, str, str]] = [
    ("AMENDS", "Sửa đổi", "VB hiện tại sửa đổi / bổ sung điều khoản của VB kia."),
    ("REPEALS", "Bãi bỏ", "VB hiện tại bãi bỏ Điều/Khoản hoặc cụm từ trong VB kia."),
    ("REPLACES", "Thay thế", "Thay thế phụ lục hoặc cụm từ bên trong VB kia."),
    ("BASED_ON", "Căn cứ pháp lý", "VB hiện tại được ban hành căn cứ vào VB kia (phần 'Căn cứ...')."),
    ("REFERENCES", "Dẫn chiếu", "Điều / Khoản của VB hiện tại dẫn chiếu nội dung trong VB kia."),
    ("ISSUED_BY", "Ban hành bởi", "Cơ quan ban hành văn bản (Bộ, Chính phủ, Quốc hội...)."),
    ("OF_TYPE", "Loại văn bản", "Phân loại văn bản (Luật / Nghị định / Thông tư...)."),
]

DOC_TYPE_LABEL = {
    "LUAT": "Luật",
    "NQ": "Nghị quyết",
    "ND": "Nghị định",
    "TT": "Thông tư",
    "QD": "Quyết định",
    "CT": "Chỉ thị",
    "PL": "Pháp lệnh",
    "UNKNOWN": "Khác",
}


def _kind(labels: list[str]) -> str:
    for k in ("Document", "Chapter", "Article", "Clause", "Point", "Authority", "DocumentType"):
        if k in labels:
            return k
    return "Unknown"


def _node_label(labels: list[str], props: dict) -> str:
    kind = _kind(labels)
    if kind == "Document":
        return props.get("tên_ngắn") or props.get("số_hiệu") or props.get("id") or "?"
    if kind == "Article":
        return f"Điều {props.get('số', '?')}"
    if kind == "Clause":
        return f"Khoản {props.get('số', '?')}"
    if kind == "Point":
        return f"Điểm {props.get('ký_hiệu', '?')}"
    if kind == "Chapter":
        return f"Chương {props.get('số', '?')}"
    if kind == "Authority":
        return props.get("tên", "?")
    if kind == "DocumentType":
        return props.get("tên") or props.get("code") or "?"
    return "?"


def _node_color(labels: list[str], props: dict) -> str:
    kind = _kind(labels)
    if kind == "Document" and props.get("trạng_thái") == "PLACEHOLDER":
        return LABEL_COLOR["_Placeholder"]
    return LABEL_COLOR.get(kind, "#7F8C8D")


def _node_size(labels: list[str]) -> int:
    kind = _kind(labels)
    return {
        "Document": 28,
        "Chapter": 22,
        "Article": 16,
        "Clause": 12,
        "Point": 8,
        "Authority": 24,
        "DocumentType": 20,
    }.get(kind, 10)


def _ag_id(labels: list[str], props: dict) -> str:
    kind = _kind(labels)
    if kind in ("Document", "Chapter", "Article", "Clause", "Point"):
        return f"{kind}::{props.get('id', '')}"
    if kind == "Authority":
        return f"Authority::{props.get('tên', '')}"
    if kind == "DocumentType":
        return f"DocumentType::{props.get('code', '')}"
    return f"Unknown::{props.get('id', id(props))}"


def _tooltip(labels: list[str], props: dict) -> str:
    lines = [f"<b>:{' :'.join(labels)}</b>"]
    for k, v in props.items():
        if v in (None, "", []):
            continue
        s = str(v)
        if len(s) > 250:
            s = s[:250] + "…"
        lines.append(f"<i>{k}</i>: {s}")
    return "<br>".join(lines)


# ============================================================================
# Graph extraction helpers
# ============================================================================


def _collect(records: list[Any]) -> tuple[list[Node], list[Edge]]:
    nodes: dict[str, Node] = {}
    edges_seen: set[tuple[str, str, str]] = set()
    edges: list[Edge] = []

    def _add_node(val: Any) -> str | None:
        if val is None or not hasattr(val, "labels"):
            return None
        labels = list(val.labels)
        props = dict(val)
        nid = _ag_id(labels, props)
        if nid not in nodes:
            nodes[nid] = Node(
                id=nid,
                label=_node_label(labels, props),
                size=_node_size(labels),
                color=_node_color(labels, props),
                title=_tooltip(labels, props),
            )
        return nid

    def _add_rel(val: Any) -> None:
        if val is None or not hasattr(val, "type"):
            return
        s_id = _add_node(val.start_node)
        e_id = _add_node(val.end_node)
        if not s_id or not e_id:
            return
        key = (s_id, e_id, val.type)
        if key in edges_seen:
            return
        edges_seen.add(key)
        edges.append(
            Edge(
                source=s_id,
                target=e_id,
                label="",
                title=val.type,  # hover tooltip
                color=REL_COLOR.get(val.type, "#999"),
                width=2.5,
            )
        )

    for rec in records:
        for key in rec.keys():
            val = rec[key]
            if isinstance(val, list):
                for item in val:
                    _add_node(item)
                    _add_rel(item)
            else:
                _add_node(val)
                _add_rel(val)

    return list(nodes.values()), edges


# ============================================================================
# Filter dimming — "focus + context" visualization
# ============================================================================


def _dim(hex_color: str, factor: float = 0.22) -> str:
    """Blend hex color toward white. factor=0.22 keeps ~22% of original color."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return "#E0E4E8"
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return "#E0E4E8"
    r2 = int(r * factor + 255 * (1 - factor))
    g2 = int(g * factor + 255 * (1 - factor))
    b2 = int(b * factor + 255 * (1 - factor))
    return f"#{r2:02X}{g2:02X}{b2:02X}"


def _doc_id_of_ag_node(ag_id: str) -> str | None:
    """Map an agraph node id back to the owning Document.id, or None if it
    isn't part of any Document (Authority, DocumentType, Unknown)."""
    if ag_id.startswith("Document::"):
        return ag_id.split("::", 1)[1] or None
    for prefix in ("Article::", "Clause::", "Point::", "Chapter::"):
        if ag_id.startswith(prefix):
            path = ag_id.split("::", 1)[1]
            return path.split("#", 1)[0] if "#" in path else None
    return None


def apply_filter_dim(
    nodes: list[Node],
    edges: list[Edge],
    matched_doc_ids: set[str] | None,
) -> tuple[list[Node], list[Edge], int, int]:
    """Mutate node/edge colors based on filter. Returns (nodes, edges, n_matched, n_total)."""
    doc_count = sum(1 for n in nodes if n.id.startswith("Document::"))
    if matched_doc_ids is None:
        return nodes, edges, doc_count, doc_count

    dimmed_ag_ids: set[str] = set()
    matched_count = 0
    for n in nodes:
        doc_id = _doc_id_of_ag_node(n.id)
        if doc_id is None:
            continue  # Authority / DocumentType — always bright
        if doc_id in matched_doc_ids:
            if n.id.startswith("Document::"):
                matched_count += 1
            continue
        # Dim
        cur = getattr(n, "color", "#888")
        n.color = _dim(cur)
        dimmed_ag_ids.add(n.id)

    for e in edges:
        if e.source in dimmed_ag_ids or e.to in dimmed_ag_ids:
            cur = getattr(e, "color", "#999")
            e.color = _dim(cur, factor=0.18)
    return nodes, edges, matched_count, doc_count


# ============================================================================
# Queries
# ============================================================================

STATS_Q = """
RETURN
  count { MATCH (d:Document) WHERE d.trạng_thái IS NULL OR d.trạng_thái <> "PLACEHOLDER" } AS documents,
  count { MATCH (d:Document {trạng_thái: "PLACEHOLDER"}) } AS placeholders,
  count { MATCH (:Article) } AS articles,
  count { MATCH (:Clause) } AS clauses,
  count { MATCH (:Point) } AS points,
  count { MATCH ()-[:AMENDS]->() } AS amends,
  count { MATCH ()-[:REPEALS]->() } AS repeals,
  count { MATCH ()-[:REPLACES]->() } AS replaces,
  count { MATCH ()-[:BASED_ON]->() } AS based_on,
  count { MATCH ()-[:REFERENCES]->() } AS refs
"""


def list_authorities() -> list[str]:
    rows = run_dicts(
        """
        MATCH (d:Document)
        WHERE d.cơ_quan_ban_hành IS NOT NULL AND d.cơ_quan_ban_hành <> ''
        RETURN DISTINCT d.cơ_quan_ban_hành AS val ORDER BY val
        """
    )
    return [r["val"] for r in rows]


def list_years() -> list[int]:
    rows = run_dicts(
        """
        MATCH (d:Document)
        WHERE d.ngày_ban_hành IS NOT NULL
        RETURN DISTINCT d.ngày_ban_hành.year AS val ORDER BY val DESC
        """
    )
    return [int(r["val"]) for r in rows if r.get("val") is not None]


def compute_matched_docs(
    auth: list[str], loai: list[str], year: list[int]
) -> set[str]:
    conds, params = [], {}
    if auth:
        conds.append("d.cơ_quan_ban_hành IN $auth")
        params["auth"] = auth
    if loai:
        conds.append("d.loại_code IN $loai")
        params["loai"] = loai
    if year:
        conds.append("d.ngày_ban_hành.year IN $year")
        params["year"] = year
    if not conds:
        return set()
    q = f"MATCH (d:Document) WHERE {' AND '.join(conds)} RETURN d.id AS id"
    return {r["id"] for r in run_dicts(q, params) if r.get("id")}


def list_documents(loai: list[str], only_real: bool, limit: int = 200) -> list[dict]:
    conds = []
    params: dict[str, Any] = {"limit": limit}
    if loai:
        conds.append("d.loại_code IN $loai")
        params["loai"] = loai
    if only_real:
        conds.append("(d.trạng_thái IS NULL OR d.trạng_thái <> 'PLACEHOLDER')")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    q = f"""
    MATCH (d:Document)
    {where}
    RETURN d.id AS id,
           d.số_hiệu AS so_hieu,
           coalesce(d.tên_ngắn, d.tên, d.số_hiệu, d.id) AS display,
           d.loại_code AS loai_code,
           d.ngày_ban_hành AS ngay_bh,
           d.trạng_thái AS trang_thai,
           d.cơ_quan_ban_hành AS co_quan
    ORDER BY (d.ngày_ban_hành IS NULL), d.ngày_ban_hành DESC, d.số_hiệu
    LIMIT $limit
    """
    return run_dicts(q, params)


def search_fulltext(text: str, limit: int = 30) -> list[dict]:
    """Search articles and clauses via the fulltext indexes created at init."""
    if not text or not text.strip():
        return []
    q = """
    CALL db.index.fulltext.queryNodes('article_fulltext', $q) YIELD node, score
    MATCH (d:Document)-[:HAS_ARTICLE]->(node)
    RETURN 'Article' AS kind,
           node.id AS id,
           node.số AS so,
           node.tiêu_đề AS tieu_de,
           substring(coalesce(node.nội_dung, ''), 0, 300) AS preview,
           d.id AS doc_id,
           coalesce(d.tên_ngắn, d.tên, d.số_hiệu) AS doc_display,
           d.số_hiệu AS doc_so_hieu,
           score
    ORDER BY score DESC
    LIMIT $limit
    """
    try:
        return run_dicts(q, {"q": text, "limit": limit})
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Fulltext index chưa sẵn sàng ({exc}). Fallback CONTAINS.")
        return run_dicts(
            """
            MATCH (d:Document)-[:HAS_ARTICLE]->(a:Article)
            WHERE toLower(a.nội_dung) CONTAINS toLower($q)
               OR toLower(coalesce(a.tiêu_đề, '')) CONTAINS toLower($q)
            RETURN 'Article' AS kind, a.id AS id, a.số AS so,
                   a.tiêu_đề AS tieu_de,
                   substring(coalesce(a.nội_dung, ''), 0, 300) AS preview,
                   d.id AS doc_id,
                   coalesce(d.tên_ngắn, d.tên, d.số_hiệu) AS doc_display,
                   d.số_hiệu AS doc_so_hieu,
                   1.0 AS score
            LIMIT $limit
            """,
            {"q": text, "limit": limit},
        )


def overview_graph(loai: list[str], only_real: bool, max_docs: int = 60):
    """Graph of all documents + lifecycle edges between them. Citations from
    Article/Clause levels are rolled up to Document→Document edges so placeholder
    nodes referenced only via Article do not appear isolated."""
    docs = list_documents(loai, only_real, limit=max_docs)
    ids = [d["id"] for d in docs if d.get("id")]
    if not ids:
        return [], []

    # 1) Direct lifecycle + REFERENCES between Documents.
    q_direct = """
    MATCH (d:Document) WHERE d.id IN $ids
    OPTIONAL MATCH (d)-[r:AMENDS|REPEALS|REPLACES|BASED_ON|REFERENCES]->(o:Document)
    WHERE o.id IN $ids
    RETURN d, r, o
    """
    nodes, edges = _collect(run_records(q_direct, {"ids": ids}))

    # 2) Citations from Article / Clause inside a Document rolled up to Doc→Doc.
    q_via_article = """
    MATCH (d:Document) WHERE d.id IN $ids
    MATCH (d)-[:HAS_ARTICLE]->(a:Article)
    OPTIONAL MATCH (a)-[:REFERENCES]->(o1:Document) WHERE o1.id IN $ids
    OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(c:Clause)-[:REFERENCES]->(o2:Document)
                   WHERE o2.id IN $ids
    WITH d.id AS src, collect(DISTINCT o1.id) + collect(DISTINCT o2.id) AS targets
    UNWIND targets AS dst
    WITH src, dst WHERE dst IS NOT NULL AND dst <> src
    RETURN src, dst, count(*) AS via_count
    """
    seen_edge_keys = {(e.source, e.to, e.label) for e in edges}  # vis.js: to/from
    for row in run_dicts(q_via_article, {"ids": ids}):
        s_id = f"Document::{row['src']}"
        e_id = f"Document::{row['dst']}"
        label = "REFERENCES"
        if (s_id, e_id, label) in seen_edge_keys:
            continue
        seen_edge_keys.add((s_id, e_id, label))
        n_via = row.get("via_count", 1)
        edges.append(
            Edge(
                source=s_id,
                target=e_id,
                label="",
                title=f"REFERENCES (×{n_via} citations)" if n_via > 1 else "REFERENCES",
                color=REL_COLOR["REFERENCES"],
                width=2.5,
            )
        )

    return nodes, edges


def doc_subgraph(doc_id: str, include_structure: bool):
    """Graph centered on one Document: lifecycle neighbors + Authority + Type
    (+ Articles if requested)."""
    queries: list[tuple[str, dict]] = [
        (
            """
            MATCH (d:Document {id: $id})
            OPTIONAL MATCH (d)-[r1:AMENDS|REPEALS|REPLACES|BASED_ON|REFERENCES]->(o:Document)
            RETURN d, r1, o
            """,
            {"id": doc_id},
        ),
        (
            """
            MATCH (d:Document {id: $id})
            OPTIONAL MATCH (s:Document)-[r2:AMENDS|REPEALS|REPLACES|BASED_ON|REFERENCES]->(d)
            RETURN d, r2, s
            """,
            {"id": doc_id},
        ),
        (
            """
            MATCH (d:Document {id: $id})
            OPTIONAL MATCH (d)-[r3:ISSUED_BY]->(a:Authority)
            OPTIONAL MATCH (d)-[r4:OF_TYPE]->(t:DocumentType)
            RETURN d, r3, a, r4, t
            """,
            {"id": doc_id},
        ),
    ]
    if include_structure:
        queries.append(
            (
                """
                MATCH (d:Document {id: $id})-[r:HAS_ARTICLE]->(a:Article)
                OPTIONAL MATCH (a)-[r2:HAS_CLAUSE]->(c:Clause)
                RETURN d, r, a, r2, c
                """,
                {"id": doc_id},
            )
        )

    all_records: list[Any] = []
    for q, p in queries:
        all_records.extend(run_records(q, p))
    return _collect(all_records)


def fetch_doc_details(doc_id: str) -> dict | None:
    rows = run_dicts(
        """
        MATCH (d:Document {id: $id})
        OPTIONAL MATCH (d)-[:HAS_ARTICLE]->(a:Article)
        RETURN d{.*} AS doc, collect({số: a.số, tiêu_đề: a.tiêu_đề}) AS arts
        """,
        {"id": doc_id},
    )
    if not rows:
        return None
    out = rows[0]
    out["arts"] = [a for a in (out.get("arts") or []) if a.get("số") is not None]
    return out


# ============================================================================
# UI helpers
# ============================================================================


def _connection_banner() -> bool:
    s = get_settings()
    if not s.NEO4J_URI:
        st.error("⚠️ NEO4J_URI chưa được cấu hình. Kiểm tra `.env`.")
        return False
    try:
        drv = _get_driver()
        with drv.session(database=s.NEO4J_DATABASE or None) as sess:
            sess.run("RETURN 1").consume()
    except Exception as exc:  # noqa: BLE001
        st.error(f"❌ Không kết nối được Neo4j: {exc}")
        return False
    return True


def _agraph_config(height: int = 620) -> Config:
    return Config(
        width="100%",
        height=height,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#F7DC6F",
        collapsible=False,
        node={"labelProperty": "label", "renderLabel": True},
        # renderLabel=False → mũi tên không hiện tên quan hệ; vẫn giữ tooltip khi hover
        link={"renderLabel": False, "labelProperty": "label"},
    )


def _legend_nodes_html() -> str:
    items = [
        ("Document", LABEL_COLOR["Document"]),
        ("Placeholder", LABEL_COLOR["_Placeholder"]),
        ("Article", LABEL_COLOR["Article"]),
        ("Clause", LABEL_COLOR["Clause"]),
        ("Authority", LABEL_COLOR["Authority"]),
        ("DocumentType", LABEL_COLOR["DocumentType"]),
    ]
    return " &nbsp; ".join(
        f"<span style='display:inline-block;width:11px;height:11px;background:{c};"
        f"border-radius:50%;margin-right:5px;vertical-align:middle;'></span>"
        f"<span style='font-size:13px;'>{name}</span>"
        for name, c in items
    )


def _render_rel_legend_content() -> None:
    """Render bảng mô tả chi tiết các loại quan hệ (đặt trong popover)."""
    # Build HTML as single-line strings — Markdown treats 4+ leading spaces as
    # a code block, so any indented multiline f-string would render as <pre>.
    rows = "".join(
        (
            "<tr>"
            "<td style='padding:6px 8px;white-space:nowrap;'>"
            f"<span style='display:inline-block;width:28px;height:5px;background:{REL_COLOR.get(code, '#999')};"
            "border-radius:3px;vertical-align:middle;margin-right:6px;'></span>"
            f"<span style='font-family:monospace;font-weight:600;color:{REL_COLOR.get(code, '#999')};font-size:12px;'>{code}</span>"
            "</td>"
            f"<td style='padding:6px 8px;white-space:nowrap;font-weight:600;font-size:13px;'>{vn}</td>"
            f"<td style='padding:6px 8px;color:#4a4a4a;font-size:12px;'>{desc}</td>"
            "</tr>"
        )
        for code, vn, desc in REL_INFO
    )
    table_html = (
        "<table style='border-collapse:collapse;width:100%;'>"
        "<thead>"
        "<tr style='color:#666;font-size:10px;text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid #E0E0E0;'>"
        "<th style='text-align:left;padding:4px 8px;'>Quan hệ</th>"
        "<th style='text-align:left;padding:4px 8px;'>VN</th>"
        "<th style='text-align:left;padding:4px 8px;'>Mô tả</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)
    st.caption("💡 Di chuột lên mũi tên trong graph để xem loại quan hệ.")


def _render_explore_panel(loai_filter: list[str], only_real: bool) -> None:
    """Render 3 tabs Tìm / Duyệt / Chi tiết (đặt trong popover)."""
    tab_search, tab_browse, tab_detail = st.tabs(
        ["🔍 Tìm trong nội dung", "📋 Duyệt văn bản", "📄 Chi tiết"]
    )

    with tab_search:
        query = st.text_input(
            "Từ khóa (Điều / Khoản)",
            placeholder='vd: "tuyển sinh", "mã trường"',
            key="search_q",
        )
        if query:
            with st.spinner("Đang tìm..."):
                hits = search_fulltext(query, limit=25)
            st.caption(f"{len(hits)} kết quả")
            for h in hits:
                with st.container(border=True):
                    st.markdown(f"**{h['doc_display']}** · `{h.get('doc_so_hieu','')}`")
                    st.markdown(f"Điều {h.get('so','?')} — *{h.get('tieu_de','') or ''}*")
                    st.caption(h.get("preview", ""))
                    if st.button(
                        "Xem trong graph →",
                        key=f"goto_{h['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.selected_doc_id = h["doc_id"]
                        st.rerun()

    with tab_browse:
        docs = list_documents(loai_filter, only_real, limit=300)
        st.caption(f"{len(docs)} văn bản")
        for d in docs:
            tag = "🟦" if (d.get("trang_thai") or "") != "PLACEHOLDER" else "⬜"
            label = f"{tag} {d['display']}  ·  `{d.get('so_hieu','')}`"
            if st.button(label, key=f"doc_{d['id']}", use_container_width=True):
                st.session_state.selected_doc_id = d["id"]
                st.rerun()

    with tab_detail:
        sel = st.session_state.get("selected_doc_id")
        if not sel:
            st.info("Chọn 1 văn bản để xem chi tiết.")
            return
        det = fetch_doc_details(sel)
        if not det:
            st.warning("Không tìm thấy.")
            return
        doc = det["doc"]
        st.markdown(
            f"### {doc.get('tên_ngắn') or doc.get('tên') or doc['id']}"
        )
        st.code(doc.get("số_hiệu") or "", language="text")
        meta_cols = st.columns(2)
        meta_cols[0].markdown(
            f"**Loại:** {DOC_TYPE_LABEL.get(doc.get('loại_code',''), doc.get('loại_code',''))}"
        )
        meta_cols[1].markdown(f"**Trạng thái:** {doc.get('trạng_thái') or '—'}")
        meta_cols[0].markdown(f"**Ngày BH:** {doc.get('ngày_ban_hành') or '—'}")
        meta_cols[1].markdown(f"**Hiệu lực:** {doc.get('ngày_hiệu_lực') or '—'}")
        if doc.get("cơ_quan_ban_hành"):
            st.markdown(f"**Cơ quan:** {doc['cơ_quan_ban_hành']}")
        if doc.get("người_ký"):
            st.markdown(
                f"**Người ký:** {doc['người_ký']} ({doc.get('chức_vụ_người_ký','')})"
            )
        if det["arts"]:
            st.markdown("**Mục lục Điều:**")
            for a in sorted(det["arts"], key=lambda x: x.get("số") or 0):
                st.markdown(f"- Điều {a['số']} — {a.get('tiêu_đề') or ''}")


# ============================================================================
# Page 1 — Knowledge Graph Explorer
# ============================================================================


def render_graph_page() -> None:
    st.title("⚖️ Legal Knowledge Graph Explorer")
    st.caption(
        "Khám phá đồ thị văn bản pháp luật trên Neo4j Aura — click vào node Document "
        "để mở rộng. Phần Audit nằm ở trang khác (sẽ làm sau)."
    )

    if not _connection_banner():
        return

    # ----- Sidebar: filter (top) | display | stats (bottom) -----
    with st.sidebar:
        st.header("🎯 Lọc & Highlight")
        st.caption(
            "Document khớp sẽ **sáng**, không khớp **mờ đi** — không xóa khỏi graph."
        )
        filter_auth = st.multiselect(
            "Cơ quan ban hành",
            options=list_authorities(),
            default=[],
            placeholder="Tất cả cơ quan",
        )
        filter_loai_dim = st.multiselect(
            "Loại văn bản",
            options=list(DOC_TYPE_LABEL.keys()),
            format_func=lambda c: f"{c} — {DOC_TYPE_LABEL[c]}",
            default=[],
            placeholder="Tất cả loại",
        )
        filter_year = st.multiselect(
            "Năm ban hành",
            options=list_years(),
            default=[],
            placeholder="Tất cả năm",
        )
        has_filter = bool(filter_auth or filter_loai_dim or filter_year)
        matched_doc_ids = (
            compute_matched_docs(filter_auth, filter_loai_dim, filter_year)
            if has_filter
            else None
        )

        st.divider()
        st.subheader("⚙️ Hiển thị")
        only_real = st.checkbox("Ẩn placeholder", value=False)
        include_structure = st.checkbox("Hiện Điều/Khoản", value=False)
        max_docs = st.slider("Tối đa Document (overview)", 10, 200, 60, step=10)

        st.divider()
        stats_rows = run_dicts(STATS_Q)
        stats = stats_rows[0] if stats_rows else {}
        with st.expander("📊 Thống kê graph", expanded=False):
            c1, c2 = st.columns(2)
            c1.metric("Documents", stats.get("documents", 0))
            c2.metric("Placeholders", stats.get("placeholders", 0))
            c1.metric("Articles", stats.get("articles", 0))
            c2.metric("Clauses", stats.get("clauses", 0))
            # Compact lifecycle list (markdown table — no big JSON box)
            lifecycle_md = "\n".join(
                f"- **{rel}**: {stats.get(key, 0)}"
                for rel, key in [
                    ("AMENDS", "amends"),
                    ("REPEALS", "repeals"),
                    ("REPLACES", "replaces"),
                    ("BASED_ON", "based_on"),
                    ("REFERENCES", "refs"),
                ]
            )
            st.markdown("**Quan hệ:**\n" + lifecycle_md)

        # Legacy: list_documents/overview_graph signature still takes loai filter
        # (used to be a scope filter). Now we always pass empty since filter dims.
        loai_filter: list[str] = []

    # ----- State -----
    if "selected_doc_id" not in st.session_state:
        st.session_state.selected_doc_id = None

    # ----- Action bar: 2 popover bên trái | chips ở phải (cùng hàng) -----
    st.markdown(
        """
        <style>
        /* Popover triggers: pill shape, subtle shadow, no wrap */
        div[data-testid="stPopover"] button {
            border-radius: 20px !important;
            font-weight: 500 !important;
            white-space: nowrap !important;
            border-color: #DCE3EA !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
            transition: all 0.15s ease !important;
        }
        div[data-testid="stPopover"] button:hover {
            background: #F0F4F9 !important;
            border-color: #4F8EF7 !important;
        }
        /* Vertically align the chips row with the buttons */
        .kg-chips {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            height: 100%;
            padding-right: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    bar_legend, bar_explore, bar_chips = st.columns([1.5, 1.5, 9], vertical_alignment="center")
    with bar_legend:
        with st.popover("📖 Chú thích", use_container_width=True):
            _render_rel_legend_content()
    with bar_explore:
        with st.popover("🔍 Khám phá", use_container_width=True):
            st.markdown(
                "<div style='min-width:360px;max-width:460px;'>",
                unsafe_allow_html=True,
            )
            _render_explore_panel(loai_filter, only_real)
            st.markdown("</div>", unsafe_allow_html=True)
    with bar_chips:
        st.markdown(
            f"<div class='kg-chips'>{_legend_nodes_html()}</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<hr style='margin:8px 0 12px 0;border:none;border-top:1px solid #ECEFF1;' />",
        unsafe_allow_html=True,
    )

    # ----- Title row + back button -----
    sel_id = st.session_state.selected_doc_id
    if sel_id:
        det = fetch_doc_details(sel_id)
        title = (
            (
                det["doc"].get("tên_ngắn")
                or det["doc"].get("tên")
                or det["doc"].get("số_hiệu")
                or sel_id
            )
            if det
            else sel_id
        )
        title_cols = st.columns([1, 11])
        if title_cols[0].button("← Overview", use_container_width=True):
            st.session_state.selected_doc_id = None
            st.rerun()
        title_cols[1].subheader(f"🎯 {title}")
        nodes, edges = doc_subgraph(sel_id, include_structure)
    else:
        st.subheader("🗺️ Overview — toàn bộ graph")
        nodes, edges = overview_graph(loai_filter, only_real, max_docs=max_docs)

    # ----- Apply filter dimming (focus + context) -----
    nodes, edges, n_matched, n_total = apply_filter_dim(nodes, edges, matched_doc_ids)

    # ----- Full-width graph -----
    if not nodes:
        st.info("Không có node nào để hiển thị.")
    else:
        if matched_doc_ids is not None:
            st.markdown(
                f"<div style='margin:4px 0 8px 0;padding:6px 12px;background:#FFF7E6;"
                f"border-left:3px solid #F77F00;border-radius:4px;font-size:13px;'>"
                f"🎯 <b>Bộ lọc đang bật</b> — khớp {n_matched}/{n_total} Document. "
                f"Các Document khác mờ đi để giữ ngữ cảnh."
                f"</div>",
                unsafe_allow_html=True,
            )
        clicked = agraph(nodes=nodes, edges=edges, config=_agraph_config(height=720))
        if clicked and isinstance(clicked, str) and clicked.startswith("Document::"):
            new_id = clicked.split("::", 1)[1]
            if new_id and new_id != st.session_state.selected_doc_id:
                st.session_state.selected_doc_id = new_id
                st.rerun()
        st.caption(
            f"📦 {len(nodes)} node · 🔗 {len(edges)} edge  ·  "
            "Click vào Document để zoom vào subgraph của nó."
        )


# ============================================================================
# Page 2 — Audit (extract legal bases → audit-by-graph per basis)
# ============================================================================

STATUS_META: dict[str, tuple[str, str]] = {
    "Tuân thủ": ("✅", "#16A34A"),
    "Không tuân thủ": ("❌", "#DC2626"),
    "Cần kiểm tra": ("⚠️", "#F59E0B"),
    "Không tìm thấy trong hệ thống": ("❓", "#6B7280"),
}


def _norm_status(s: str | None) -> str:
    """Gộp 'Không liên quan' vào 'Cần kiểm tra'."""
    s = (s or "").strip() or "Cần kiểm tra"
    if s == "Không liên quan":
        return "Cần kiểm tra"
    return s


def _api_base() -> str:
    return f"{get_settings().BACKEND_URL.rstrip('/')}/api/v1"


def _call_extract_legal_basis(pdf_bytes: bytes, filename: str) -> dict:
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    r = requests.post(
        f"{_api_base()}/legal-analysis/extract-legal-basis",
        files=files,
        timeout=180,
    )
    r.raise_for_status()
    return r.json()


def _call_audit_by_graph(
    pdf_bytes: bytes,
    filename: str,
    audited_doc: dict,
    legal_bases: list[dict],
) -> list[dict]:
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    data = {
        "audited_document": json.dumps(audited_doc, ensure_ascii=False),
        "legal_bases": json.dumps(legal_bases, ensure_ascii=False),
    }
    r = requests.post(
        f"{_api_base()}/legal-analysis/audit-by-graph",
        files=files,
        data=data,
        timeout=600,
    )
    r.raise_for_status()
    return r.json()


def _reset_audit_state() -> None:
    for k in (
        "audit_pdf",
        "audit_filename",
        "audit_extracted",
        "audit_results",
    ):
        st.session_state.pop(k, None)


def _basis_label(basis: dict) -> str:
    return (
        (basis.get("law_number") or "").strip()
        or (basis.get("law_name") or "").strip()
        or "?"
    )


def _render_extracted_section(extracted: dict) -> tuple[dict, list[dict]]:
    doc = extracted.get("document") or {}
    bases = extracted.get("legal_bases") or []

    with st.container(border=True):
        st.markdown("**📄 Văn bản được audit:**")
        st.markdown(
            f"- **Số hiệu:** `{doc.get('law_number') or '—'}`  \n"
            f"- **Tên:** {doc.get('law_name') or '—'}  \n"
            f"- **Ngày BH:** {doc.get('date') or '—'}"
        )

    if not bases:
        st.warning("⚠️ Không trích được căn cứ pháp lý nào từ trang đầu.")
        return doc, bases

    bases_df = pd.DataFrame(
        [
            {
                "#": i + 1,
                "Số hiệu": b.get("law_number") or "",
                "Tên": b.get("law_name") or "",
                "Ngày": b.get("date") or "",
            }
            for i, b in enumerate(bases)
        ]
    )
    st.markdown(f"**🔗 {len(bases)} căn cứ pháp lý trích được:**")
    st.dataframe(bases_df, hide_index=True, use_container_width=True)
    return doc, bases


def _run_audit_loop(
    pdf_bytes: bytes,
    filename: str,
    audited_doc: dict,
    bases: list[dict],
) -> list[dict]:
    """Gọi /audit-by-graph tuần tự cho từng basis để show progress thật."""
    results: list[dict] = []
    n = len(bases)

    progress = st.progress(0.0, text="Khởi tạo...")
    table_slot = st.empty()
    log_slot = st.container(border=True)

    def _refresh_table() -> None:
        if not results:
            return
        rows = []
        for j, r in enumerate(results, start=1):
            status = _norm_status(r.get("overall_status"))
            icon, _ = STATUS_META.get(status, ("•", "#888"))
            articles = r.get("articles") or []
            n_rel = sum(1 for a in articles if a.get("applicable"))
            rows.append(
                {
                    "#": j,
                    "Căn cứ pháp lý": r.get("audited_law") or "",
                    "Ngày": r.get("date") or "",
                    "Trạng thái": f"{icon} {status}",
                    "Khớp KG": "✓" if r.get("matched_doc_id") else "—",
                    "Điều liên quan": n_rel if articles else "—",
                }
            )
        table_slot.dataframe(
            pd.DataFrame(rows), hide_index=True, use_container_width=True
        )

    for i, basis in enumerate(bases, start=1):
        name = _basis_label(basis)
        progress.progress(
            (i - 1) / n,
            text=f"{i}/{n} — Đang đối chiếu với {name}...",
        )
        with log_slot:
            placeholder = st.empty()
            placeholder.markdown(f"⏳ **{i}/{n}** — {name} — đang chạy...")

        t0 = time.time()
        try:
            res = _call_audit_by_graph(pdf_bytes, filename, audited_doc, [basis])
            item = (res or [{}])[0]
        except Exception as exc:  # noqa: BLE001
            item = {
                "audited_law": name,
                "date": basis.get("date") or "",
                "matched_doc_id": None,
                "overall_status": "Cần kiểm tra",
                "explanation": f"Lỗi gọi API: {exc}",
                "articles": [],
            }
        dt = time.time() - t0
        results.append(item)

        status = _norm_status(item.get("overall_status"))
        icon, _ = STATUS_META.get(status, ("•", "#888"))
        articles = item.get("articles") or []
        n_rel = sum(1 for a in articles if a.get("applicable"))
        placeholder.markdown(
            f"{icon} **{i}/{n}** — {name} — `{status}` "
            f"({n_rel}/{len(articles)} điều liên quan, {dt:.1f}s)"
        )
        _refresh_table()

    progress.progress(1.0, text=f"Hoàn tất — đã audit {n} căn cứ.")
    return results


def _render_results(results: list[dict]) -> None:
    counts = {k: 0 for k in STATUS_META}
    for r in results:
        s = _norm_status(r.get("overall_status"))
        counts[s] = counts.get(s, 0) + 1

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("✅ Tuân thủ", counts.get("Tuân thủ", 0))
    m2.metric("❌ Không tuân thủ", counts.get("Không tuân thủ", 0))
    m3.metric("⚠️ Cần kiểm tra", counts.get("Cần kiểm tra", 0))
    m4.metric("❓ Không tìm thấy", counts.get("Không tìm thấy trong hệ thống", 0))

    rows = []
    for i, r in enumerate(results, start=1):
        status = _norm_status(r.get("overall_status"))
        icon, _ = STATUS_META.get(status, ("•", "#888"))
        articles = r.get("articles") or []
        n_rel = sum(1 for a in articles if a.get("applicable"))
        rows.append(
            {
                "#": i,
                "Căn cứ pháp lý": r.get("audited_law") or "",
                "Ngày": r.get("date") or "",
                "Trạng thái": f"{icon} {status}",
                "Khớp KG": "✓" if r.get("matched_doc_id") else "—",
                "Điều liên quan": n_rel if articles else "—",
            }
        )
    st.markdown("### 📋 Kết quả tổng hợp")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown("### 🔍 Chi tiết — chỉ các điều liên quan")
    st.caption("Các điều không liên quan đến văn bản đầu vào đã được lọc bỏ.")
    for i, r in enumerate(results, start=1):
        status = _norm_status(r.get("overall_status"))
        icon, _ = STATUS_META.get(status, ("•", "#888"))
        articles = r.get("articles") or []
        related = [a for a in articles if a.get("applicable")]
        title = (
            f"{icon} {i}. {r.get('audited_law') or '?'} — {status} "
            f"({len(related)}/{len(articles)} điều liên quan)"
        )
        with st.expander(title):
            if r.get("explanation"):
                st.info(r["explanation"])
            if not related:
                st.caption(
                    "Không có điều khoản nào liên quan đến nội dung văn bản đầu vào."
                )
                continue
            art_rows = []
            for a in related:
                a_status = _norm_status(a.get("status"))
                a_icon, _ = STATUS_META.get(a_status, ("•", "#888"))
                art_rows.append(
                    {
                        "Điều": a.get("article_number"),
                        "Tiêu đề": a.get("article_title") or "",
                        "Trạng thái": f"{a_icon} {a_status}",
                        "Giải thích": a.get("explanation") or "",
                    }
                )
            st.dataframe(
                pd.DataFrame(art_rows), hide_index=True, use_container_width=True
            )


def render_audit_page() -> None:
    st.title("🔎 Audit tuân thủ văn bản")
    st.caption(f"Backend: `{_api_base()}` (đổi qua env `BACKEND_URL`)")

    top_l, top_r = st.columns([7, 1])
    with top_r:
        if st.button("🔄 Reset", use_container_width=True):
            _reset_audit_state()
            st.rerun()

    uploaded = st.file_uploader(
        "Tải lên văn bản PDF cần audit",
        type=["pdf"],
        key="audit_uploader",
    )
    if uploaded is not None and st.session_state.get("audit_filename") != uploaded.name:
        _reset_audit_state()
        st.session_state.audit_pdf = uploaded.read()
        st.session_state.audit_filename = uploaded.name

    if "audit_pdf" not in st.session_state:
        st.info("⬆️ Tải file PDF để bắt đầu.")
        return

    st.success(
        f"📄 **{st.session_state.audit_filename}** "
        f"({len(st.session_state.audit_pdf) / 1024:.1f} KB)"
    )

    # ----- Bước 1: Extract -----
    st.divider()
    st.subheader("Bước 1 — Trích xuất căn cứ pháp lý")

    if "audit_extracted" not in st.session_state:
        if st.button("🔍 Trích xuất từ trang đầu", type="primary"):
            with st.spinner("Đang gọi /extract-legal-basis..."):
                try:
                    st.session_state.audit_extracted = _call_extract_legal_basis(
                        st.session_state.audit_pdf,
                        st.session_state.audit_filename,
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"❌ Extract thất bại: {exc}")
                    return
            st.rerun()
        return

    doc, bases = _render_extracted_section(st.session_state.audit_extracted)
    if not bases:
        return

    # ----- Bước 2: Audit -----
    st.divider()
    st.subheader("Bước 2 — Đối chiếu với Knowledge Graph")

    if "audit_results" not in st.session_state:
        st.caption(
            "Hệ thống sẽ gọi `/audit-by-graph` lần lượt cho từng căn cứ để hiển thị "
            "tiến trình thật. Có thể mất vài phút tùy số căn cứ và số điều."
        )
        if st.button("⚖️ Bắt đầu audit", type="primary"):
            results = _run_audit_loop(
                st.session_state.audit_pdf,
                st.session_state.audit_filename,
                doc,
                bases,
            )
            st.session_state.audit_results = results
            st.rerun()
        return

    # ----- Bước 3: Render results -----
    st.divider()
    _render_results(st.session_state.audit_results)


# ============================================================================
# Page 3 — Hỏi đáp Graph (reverse query / NL → KG facts → NL answer)
# ============================================================================

DOC_STATUS_BADGE: dict[str, tuple[str, str]] = {
    "HIEU_LUC": ("🟢 Còn hiệu lực", "#16A34A"),
    "HET_HIEU_LUC": ("🔴 Hết hiệu lực", "#DC2626"),
    "SUA_DOI": ("🟠 Đã được sửa đổi", "#F77F00"),
    "CHUA_HIEU_LUC": ("🟡 Chưa có hiệu lực", "#F59E0B"),
    "PLACEHOLDER": ("⚪ Chưa nạp đầy đủ", "#9CA3AF"),
}

REL_VN_LABEL = {
    "AMENDS": "Sửa đổi/bổ sung",
    "REPEALS": "Bãi bỏ",
    "REPLACES": "Thay thế",
}

SAMPLE_QUESTIONS = [
    "Điều 18 Thông tư 08/2022 còn hiệu lực không?",
    "Nội dung Điều 5 Nghị định 58/2023 là gì?",
    "Khoản 2 Điều 10 Luật Giáo dục 2019 đã bị sửa đổi chưa?",
]


def _call_query_article_status(question: str) -> dict:
    r = requests.post(
        f"{_api_base()}/legal-analysis/query-article-status",
        json={"question": question},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _reset_query_state() -> None:
    for k in ("query_question", "query_result", "query_error"):
        st.session_state.pop(k, None)


def _render_query_doc_card(doc: dict | None) -> None:
    if not doc:
        st.warning("Không tìm thấy văn bản tương ứng trong Knowledge Graph.")
        return
    badge, color = DOC_STATUS_BADGE.get(
        doc.get("trang_thai") or "", (doc.get("trang_thai") or "—", "#6B7280")
    )
    with st.container(border=True):
        st.markdown(f"**📄 {doc.get('ten') or doc.get('so_hieu') or doc.get('doc_id')}**")
        st.markdown(
            f"<span style='display:inline-block;padding:2px 10px;border-radius:10px;"
            f"background:{color}1A;color:{color};font-weight:600;font-size:13px;'>{badge}</span>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        c1.markdown(f"**Số hiệu:** `{doc.get('so_hieu') or '—'}`")
        c2.markdown(f"**Loại:** {doc.get('loai') or '—'}")
        c1.markdown(f"**Ngày BH:** {doc.get('ngay_ban_hanh') or '—'}")
        c2.markdown(f"**Hiệu lực:** {doc.get('ngay_hieu_luc') or '—'}")
        if doc.get("ngay_het_hieu_luc"):
            st.markdown(f"**Ngày hết hiệu lực:** {doc['ngay_het_hieu_luc']}")


def _render_query_article(article: dict | None) -> None:
    if not article:
        st.info("Câu hỏi không nhắc đến Điều cụ thể, hoặc Điều không tồn tại trong văn bản.")
        return
    with st.container(border=True):
        head = f"**Điều {article.get('so')}**"
        if article.get("tieu_de"):
            head += f" — *{article['tieu_de']}*"
        st.markdown(head)
        if article.get("noi_dung"):
            st.markdown(article["noi_dung"])
        clauses = article.get("clauses") or []
        if clauses:
            with st.expander(f"📋 {len(clauses)} khoản"):
                for cl in clauses:
                    st.markdown(f"**Khoản {cl.get('so')}.** {cl.get('noi_dung') or ''}")
                    for pt in cl.get("points") or []:
                        st.markdown(
                            f"&nbsp;&nbsp;&nbsp;&nbsp;**{pt.get('ky_hieu')})** "
                            f"{pt.get('noi_dung') or ''}",
                            unsafe_allow_html=True,
                        )


def _render_query_amendments(amendments: list[dict]) -> None:
    if not amendments:
        st.success("✅ Không có văn bản nào sửa đổi / bãi bỏ / thay thế ở phạm vi này.")
        return
    rows = []
    for a in amendments:
        rel = a.get("rel_type") or ""
        scope_bits = []
        if a.get("target_article") is not None:
            scope_bits.append(f"Điều {a['target_article']}")
        if a.get("target_clause") is not None:
            scope_bits.append(f"Khoản {a['target_clause']}")
        if a.get("target_point"):
            scope_bits.append(f"Điểm {a['target_point']}")
        scope_short = " · ".join(scope_bits) or (a.get("scope_type") or "—")
        rows.append(
            {
                "Quan hệ": f"{REL_VN_LABEL.get(rel, rel)}",
                "Văn bản nguồn": a.get("src_so_hieu") or a.get("src_doc_id") or "—",
                "Ngày BH": a.get("src_ngay_ban_hanh") or "—",
                "Phạm vi": scope_short,
                "Mô tả gốc": (a.get("scope") or "")[:120],
            }
        )
    st.markdown(f"**⚠️ {len(amendments)} văn bản tác động đến phạm vi đang hỏi:**")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_query_page() -> None:
    st.title("🤖 Hỏi đáp Knowledge Graph")
    st.caption(
        "Đặt câu hỏi tự nhiên về một Điều/Khoản — hệ thống dùng LLM để hiểu câu hỏi, "
        "truy vấn ngược graph, rồi sinh câu trả lời. Backend: "
        f"`{_api_base()}/legal-analysis/query-article-status`"
    )

    top_l, top_r = st.columns([7, 1])
    with top_r:
        if st.button("🔄 Xóa", use_container_width=True, key="query_reset"):
            _reset_query_state()
            st.rerun()

    st.markdown("**Câu hỏi mẫu:**")
    sample_cols = st.columns(len(SAMPLE_QUESTIONS))
    for i, q in enumerate(SAMPLE_QUESTIONS):
        if sample_cols[i].button(q, key=f"sample_q_{i}", use_container_width=True):
            st.session_state.query_question = q
            st.session_state.pop("query_result", None)
            st.session_state.pop("query_error", None)
            st.rerun()

    question = st.text_area(
        "Câu hỏi của bạn",
        value=st.session_state.get("query_question", ""),
        height=80,
        placeholder='vd: "Điều 18 Thông tư 08/2022 còn hiệu lực không?"',
        key="query_input",
    )

    if st.button("🔍 Tra cứu", type="primary", disabled=not question.strip()):
        st.session_state.query_question = question.strip()
        st.session_state.pop("query_result", None)
        st.session_state.pop("query_error", None)
        with st.spinner("LLM đang phân tích câu hỏi và truy vấn graph..."):
            try:
                st.session_state.query_result = _call_query_article_status(
                    question.strip()
                )
            except requests.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.response.json().get("detail", "")
                except Exception:  # noqa: BLE001
                    detail = exc.response.text if exc.response is not None else ""
                st.session_state.query_error = f"HTTP {exc.response.status_code}: {detail or exc}"
            except Exception as exc:  # noqa: BLE001
                st.session_state.query_error = f"Lỗi gọi API: {exc}"
        st.rerun()

    if st.session_state.get("query_error"):
        st.error(f"❌ {st.session_state.query_error}")
        return

    result = st.session_state.get("query_result")
    if not result:
        st.info("⬆️ Nhập câu hỏi rồi nhấn **Tra cứu**.")
        return

    answer = (result.get("answer") or "").strip()
    if answer:
        st.markdown("### 💬 Trả lời")
        st.markdown(
            f"<div style='padding:14px 18px;background:#F0F7FF;border-left:4px solid #4F8EF7;"
            f"border-radius:6px;font-size:15px;line-height:1.55;'>{answer}</div>",
            unsafe_allow_html=True,
        )

    parsed = result.get("parsed") or {}
    with st.expander("🧠 LLM đã hiểu câu hỏi như thế nào", expanded=False):
        parse_rows = [
            ("Số hiệu", parsed.get("law_number") or "—"),
            ("Tên VB", parsed.get("law_name") or "—"),
            ("Điều", parsed.get("article_so") if parsed.get("article_so") is not None else "—"),
            ("Khoản", parsed.get("clause_so") if parsed.get("clause_so") is not None else "—"),
            ("Điểm", parsed.get("point_kyhieu") or "—"),
            ("Ý định", parsed.get("intent") or "—"),
        ]
        st.dataframe(
            pd.DataFrame(parse_rows, columns=["Trường", "Giá trị"]),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown("### 📚 Dữ liệu graph")
    _render_query_doc_card(result.get("document"))
    _render_query_article(result.get("article"))
    _render_query_amendments(result.get("amendments") or [])


# ============================================================================
# Page 4 — Ingest tài liệu vào Knowledge Graph
# ============================================================================


def _call_ingest_documents(files: list[tuple[str, bytes]]) -> dict:
    """POST nhiều PDF tới backend để parse & nạp vào Neo4j."""
    payload = [("files", (name, data, "application/pdf")) for name, data in files]
    r = requests.post(
        f"{_api_base()}/knowledge-graph/ingest",
        files=payload,
        timeout=600,
    )
    r.raise_for_status()
    return r.json()


def _render_ingest_report(report: dict) -> None:
    """Hiển thị IngestReport của một file đã ingest thành công."""
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Số hiệu:** {report.get('so_hieu') or '—'}")
    c2.markdown(f"**Loại:** {report.get('doc_class') or '—'}")
    c3.markdown(f"**Doc ID:** `{report.get('doc_id') or '—'}`")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Điều", report.get("n_articles", 0))
    m2.metric("Khoản", report.get("n_clauses", 0))
    m3.metric("Điểm", report.get("n_points", 0))
    m4.metric("Sửa đổi", report.get("n_amendments", 0))
    m5.metric("Trích dẫn", report.get("n_citations", 0))

    flags = ["✅ Đã nạp vào graph" if report.get("loaded") else "⚠️ Chưa nạp vào graph"]
    if report.get("metadata_incomplete"):
        flags.append("⚠️ Metadata chưa đầy đủ")
    st.caption(" · ".join(flags))


def render_ingest_page() -> None:
    st.title("📥 Nạp tài liệu vào Knowledge Graph")
    st.caption(f"Backend: `{_api_base()}` (đổi qua env `BACKEND_URL`)")
    st.markdown(
        "Tải lên một hoặc nhiều **văn bản pháp luật (PDF)**. Hệ thống sẽ phân tích "
        "cấu trúc và nạp (MERGE) vào Neo4j. Quá trình *idempotent* — nạp lại cùng "
        "một văn bản sẽ cập nhật trên đúng các node cũ."
    )

    uploaded = st.file_uploader(
        "Chọn file PDF",
        type=["pdf"],
        accept_multiple_files=True,
        key="ingest_uploader",
    )

    col_run, col_clear = st.columns([1, 1])
    run = col_run.button(
        "🚀 Ingest",
        type="primary",
        disabled=not uploaded,
        use_container_width=True,
    )
    if col_clear.button("🧹 Xoá kết quả", use_container_width=True):
        st.session_state.pop("ingest_result", None)
        st.rerun()

    if run and uploaded:
        files = [(f.name, f.getvalue()) for f in uploaded]
        try:
            with st.spinner(f"Đang ingest {len(files)} file..."):
                st.session_state.ingest_result = _call_ingest_documents(files)
        except requests.HTTPError as exc:
            resp = exc.response
            detail = ""
            if resp is not None:
                try:
                    detail = resp.json().get("detail", "")
                except Exception:
                    detail = resp.text
            st.error(f"Lỗi từ backend ({getattr(resp, 'status_code', '?')}): {detail}")
        except requests.RequestException as exc:
            st.error(f"Không gọi được backend: {exc}")

    result = st.session_state.get("ingest_result")
    if not result:
        return

    st.divider()
    s1, s2, s3 = st.columns(3)
    s1.metric("Tổng số file", result.get("total", 0))
    s2.metric("Thành công", result.get("succeeded", 0))
    s3.metric("Thất bại", result.get("failed", 0))

    for item in result.get("results", []):
        ok = item.get("success")
        icon = "✅" if ok else "❌"
        with st.expander(f"{icon} {item.get('filename', '?')}", expanded=not ok):
            if ok and item.get("report"):
                _render_ingest_report(item["report"])
            else:
                st.error(item.get("error") or "Ingest thất bại (không rõ lý do).")


# ============================================================================
# Router
# ============================================================================

PAGES = {
    "🕸️ Knowledge Graph": render_graph_page,
    "📥 Nạp tài liệu": render_ingest_page,
    "🔎 Audit tuân thủ": render_audit_page,
    "🤖 Hỏi đáp Graph": render_query_page,
}

page_key = st.sidebar.radio("📑 Trang", list(PAGES.keys()), index=0)
PAGES[page_key]()
