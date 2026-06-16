import "server-only";
import neo4j from "neo4j-driver";
import { runRecords, runDicts } from "./neo4j.server";
import { collect } from "./graph-transform";
import { REL_COLOR } from "./constants";
import type { GraphNode, GraphEdge, GraphStats } from "./types";

export const STATS_Q = `
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
`;

export async function getStats(): Promise<GraphStats> {
  const rows = await runDicts(STATS_Q);
  return (rows[0] as GraphStats) || ({} as GraphStats);
}

export async function listAuthorities(): Promise<string[]> {
  const rows = await runDicts(`
    MATCH (d:Document)
    WHERE d.cơ_quan_ban_hành IS NOT NULL AND d.cơ_quan_ban_hành <> ''
    RETURN DISTINCT d.cơ_quan_ban_hành AS val ORDER BY val
  `);
  return rows.map((r) => r.val);
}

export async function listYears(): Promise<number[]> {
  const rows = await runDicts(`
    MATCH (d:Document)
    WHERE d.ngày_ban_hành IS NOT NULL
    RETURN DISTINCT d.ngày_ban_hành.year AS val ORDER BY val DESC
  `);
  return rows.map((r) => Number(r.val)).filter((v) => !Number.isNaN(v));
}

export async function computeMatchedDocs(
  auth: string[],
  loai: string[],
  year: number[]
): Promise<Set<string>> {
  const conds: string[] = [];
  const params: Record<string, unknown> = {};
  if (auth.length) {
    conds.push("d.cơ_quan_ban_hành IN $auth");
    params.auth = auth;
  }
  if (loai.length) {
    conds.push("d.loại_code IN $loai");
    params.loai = loai;
  }
  if (year.length) {
    conds.push("d.ngày_ban_hành.year IN $year");
    params.year = year.map((y) => neo4j.int(Math.trunc(y)));
  }
  if (!conds.length) return new Set();
  const q = `MATCH (d:Document) WHERE ${conds.join(" AND ")} RETURN d.id AS id`;
  const rows = await runDicts(q, params);
  return new Set(rows.map((r) => r.id).filter(Boolean));
}

export async function listDocuments(
  loai: string[],
  onlyReal: boolean,
  limit = 200
): Promise<Record<string, any>[]> {
  const conds: string[] = [];
  const params: Record<string, unknown> = { limit: Math.trunc(limit) };
  if (loai.length) {
    conds.push("d.loại_code IN $loai");
    params.loai = loai;
  }
  if (onlyReal) {
    conds.push("(d.trạng_thái IS NULL OR d.trạng_thái <> 'PLACEHOLDER')");
  }
  const where = conds.length ? "WHERE " + conds.join(" AND ") : "";
  const q = `
    MATCH (d:Document)
    ${where}
    RETURN d.id AS id,
           d.số_hiệu AS so_hieu,
           coalesce(d.tên_ngắn, d.tên, d.số_hiệu, d.id) AS display,
           d.loại_code AS loai_code,
           d.ngày_ban_hành AS ngay_bh,
           d.trạng_thái AS trang_thai,
           d.cơ_quan_ban_hành AS co_quan
    ORDER BY (d.ngày_ban_hành IS NULL), d.ngày_ban_hành DESC, d.số_hiệu
    LIMIT toInteger($limit)
  `;
  return runDicts(q, params);
}

export async function searchFulltext(text: string, limit = 30): Promise<Record<string, any>[]> {
  if (!text || !text.trim()) return [];
  const q = `
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
    LIMIT toInteger($limit)
  `;
  try {
    return await runDicts(q, { q: text, limit: Math.trunc(limit) });
  } catch {
    return runDicts(
      `
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
      LIMIT toInteger($limit)
      `,
      { q: text, limit: Math.trunc(limit) }
    );
  }
}

export async function overviewGraph(
  loai: string[],
  onlyReal: boolean,
  maxDocs = 60
): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  const docs = await listDocuments(loai, onlyReal, maxDocs);
  const ids = docs.map((d) => d.id).filter(Boolean);
  if (!ids.length) return { nodes: [], edges: [] };

  const qDirect = `
    MATCH (d:Document) WHERE d.id IN $ids
    OPTIONAL MATCH (d)-[r:AMENDS|REPEALS|REPLACES|BASED_ON|REFERENCES]->(o:Document)
    WHERE o.id IN $ids
    RETURN d, r, o
  `;
  const { nodes, edges } = collect(await runRecords(qDirect, { ids }));

  const qViaArticle = `
    MATCH (d:Document) WHERE d.id IN $ids
    MATCH (d)-[:HAS_ARTICLE]->(a:Article)
    OPTIONAL MATCH (a)-[:REFERENCES]->(o1:Document) WHERE o1.id IN $ids
    OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(c:Clause)-[:REFERENCES]->(o2:Document)
                   WHERE o2.id IN $ids
    WITH d.id AS src, collect(DISTINCT o1.id) + collect(DISTINCT o2.id) AS targets
    UNWIND targets AS dst
    WITH src, dst WHERE dst IS NOT NULL AND dst <> src
    RETURN src, dst, count(*) AS via_count
  `;
  const seen = new Set(edges.map((e) => `${e.from}|${e.to}|${e.label}`));
  for (const row of await runDicts(qViaArticle, { ids })) {
    const sId = `Document::${row.src}`;
    const eId = `Document::${row.dst}`;
    const key = `${sId}|${eId}|REFERENCES`;
    if (seen.has(key)) continue;
    seen.add(key);
    const nVia = row.via_count ?? 1;
    edges.push({
      from: sId,
      to: eId,
      label: "",
      title: nVia > 1 ? `REFERENCES (×${nVia} citations)` : "REFERENCES",
      color: REL_COLOR.REFERENCES,
      width: 2.5,
    });
  }
  return { nodes, edges };
}

export async function docSubgraph(
  docId: string,
  includeStructure: boolean
): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  const queries: [string, Record<string, unknown>][] = [
    [
      `MATCH (d:Document {id: $id})
       OPTIONAL MATCH (d)-[r1:AMENDS|REPEALS|REPLACES|BASED_ON|REFERENCES]->(o:Document)
       RETURN d, r1, o`,
      { id: docId },
    ],
    [
      `MATCH (d:Document {id: $id})
       OPTIONAL MATCH (s:Document)-[r2:AMENDS|REPEALS|REPLACES|BASED_ON|REFERENCES]->(d)
       RETURN d, r2, s`,
      { id: docId },
    ],
    [
      `MATCH (d:Document {id: $id})
       OPTIONAL MATCH (d)-[r3:ISSUED_BY]->(a:Authority)
       OPTIONAL MATCH (d)-[r4:OF_TYPE]->(t:DocumentType)
       RETURN d, r3, a, r4, t`,
      { id: docId },
    ],
  ];
  if (includeStructure) {
    queries.push([
      `MATCH (d:Document {id: $id})-[r:HAS_ARTICLE]->(a:Article)
       OPTIONAL MATCH (a)-[r2:HAS_CLAUSE]->(c:Clause)
       RETURN d, r, a, r2, c`,
      { id: docId },
    ]);
  }
  const all = [];
  for (const [q, p] of queries) {
    all.push(...(await runRecords(q, p)));
  }
  return collect(all);
}

export async function fetchDocDetails(docId: string): Promise<{ doc: Record<string, any>; arts: any[] } | null> {
  const rows = await runDicts(
    `MATCH (d:Document {id: $id})
     OPTIONAL MATCH (d)-[:HAS_ARTICLE]->(a:Article)
     RETURN d{.*} AS doc, collect({số: a.số, tiêu_đề: a.tiêu_đề}) AS arts`,
    { id: docId }
  );
  if (!rows.length) return null;
  const out = rows[0];
  out.arts = (out.arts || []).filter((a: any) => a["số"] !== null && a["số"] !== undefined);
  return out as { doc: Record<string, any>; arts: any[] };
}
