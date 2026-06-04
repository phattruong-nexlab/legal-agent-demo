// Post-load validation checks — LEGAL_KG_PIPELINE.md section 9.
// Each "// @name" block returns rows; the repository aggregates them into a
// JSON report (non-empty result ⇒ warning/error for that check).

// @missing_ngay_ban_hanh
MATCH (d:Document)
WHERE d.ngày_ban_hành IS NULL AND d.trạng_thái <> "PLACEHOLDER"
RETURN d.id AS id, d.số_hiệu AS số_hiệu;

// @orphan_article
MATCH (a:Article)
WHERE NOT (a)<-[:HAS_ARTICLE]-(:Document)
RETURN a.id AS id;

// @non_continuous_dieu
MATCH (d:Document)-[:HAS_ARTICLE]->(a:Article)
WITH d, collect(a.số) AS so_dieu, max(a.số) AS max_so
WHERE size(so_dieu) <> max_so
RETURN d.id AS id, so_dieu;

// @self_amend
MATCH (d:Document)-[r:AMENDS|REPEALS|REPLACES]->(d)
RETURN d.id AS id, type(r) AS rel;

// @placeholder_count
MATCH (d:Document {trạng_thái: "PLACEHOLDER"})
RETURN count(d) AS placeholder_count;
