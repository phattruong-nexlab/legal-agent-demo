// Graph statistics — LEGAL_KG_PIPELINE.md section 5 `stats`.
// COUNT {} subqueries (Neo4j 5.x+) so exactly one row is always returned,
// even on an empty graph.

// @counts
RETURN
  count { MATCH (d:Document) WHERE d.trạng_thái <> "PLACEHOLDER" } AS documents,
  count { MATCH (d:Document {trạng_thái: "PLACEHOLDER"}) } AS placeholders,
  count { MATCH (:Article) } AS articles,
  count { MATCH (:Clause) } AS clauses,
  count { MATCH (:Point) } AS points,
  count { MATCH ()-[:AMENDS]->() } AS amends,
  count { MATCH ()-[:REPEALS]->() } AS repeals,
  count { MATCH ()-[:REPLACES]->() } AS replaces,
  count { MATCH ()-[:REFERENCES]->() } AS references_;
