// Idempotent load templates — LEGAL_KG_PIPELINE.md section 8.
// Each "// @name" block is one statement run (in order) inside ONE transaction.
// Vietnamese property names come from $props built in the repository layer.

// @document
// MERGE on số hiệu so a previously-minted PLACEHOLDER is upgraded in place
// (keeps its inbound relationships) instead of clashing with the unique
// số_hiệu constraint.
MERGE (d:Document {số_hiệu: $so_hieu})
ON CREATE SET d.id = $id
SET d += $props,
    d.id = $id,
    d.ingested_at = datetime(),
    d.version = coalesce(d.version, 0) + 1
WITH d
MERGE (auth:Authority {tên: $authority_name})
MERGE (d)-[:ISSUED_BY]->(auth)
WITH d
MERGE (t:DocumentType {code: $doc_type_code})
  ON CREATE SET t.tên = $doc_type_label
MERGE (d)-[:OF_TYPE]->(t);

// @chapters
UNWIND $chapters AS ch
MATCH (d:Document {id: $doc_id})
MERGE (c:Chapter {id: ch.id})
SET c.số = ch.số, c.tiêu_đề = ch.tiêu_đề
MERGE (d)-[:HAS_CHAPTER]->(c);

// @articles
UNWIND $articles AS art
MATCH (d:Document {id: $doc_id})
MERGE (a:Article {id: art.id})
SET a += art.props
MERGE (d)-[:HAS_ARTICLE]->(a);

// @clauses
UNWIND $clauses AS cl
MATCH (a:Article {id: cl.article_id})
MERGE (c:Clause {id: cl.id})
SET c += cl.props
MERGE (a)-[:HAS_CLAUSE]->(c);

// @points
UNWIND $points AS pt
MATCH (c:Clause {id: pt.clause_id})
MERGE (p:Point {id: pt.id})
SET p += pt.props
MERGE (c)-[:HAS_POINT]->(p);

// @based_on
UNWIND $based_on AS bo
MATCH (d:Document {id: $doc_id})
MERGE (target:Document {số_hiệu: bo.số_hiệu})
  ON CREATE SET target.id = bo.doc_id,
                target.trạng_thái = "PLACEHOLDER",
                target.ingested_at = datetime()
MERGE (d)-[:BASED_ON]->(target);

// @amends
UNWIND $amends AS am
MATCH (src:Document {id: $doc_id})
MERGE (target:Document {số_hiệu: am.target_so_hieu})
  ON CREATE SET target.id = am.target_doc_id,
                target.trạng_thái = "PLACEHOLDER",
                target.ingested_at = datetime()
MERGE (src)-[r:AMENDS {source_clause_id: am.source_clause_id, scope: am.scope}]->(target)
SET r += am.props;

// @repeals
UNWIND $repeals AS am
MATCH (src:Document {id: $doc_id})
MERGE (target:Document {số_hiệu: am.target_so_hieu})
  ON CREATE SET target.id = am.target_doc_id,
                target.trạng_thái = "PLACEHOLDER",
                target.ingested_at = datetime()
MERGE (src)-[r:REPEALS {source_clause_id: am.source_clause_id, scope: am.scope}]->(target)
SET r += am.props;

// @replaces
UNWIND $replaces AS am
MATCH (src:Document {id: $doc_id})
MERGE (target:Document {số_hiệu: am.target_so_hieu})
  ON CREATE SET target.id = am.target_doc_id,
                target.trạng_thái = "PLACEHOLDER",
                target.ingested_at = datetime()
MERGE (src)-[r:REPLACES {source_clause_id: am.source_clause_id, scope: am.scope}]->(target)
SET r += am.props;

// @citations_external
UNWIND $citations_external AS ct
MATCH (src {id: ct.source_id})
MERGE (target:Document {số_hiệu: ct.target_so_hieu})
  ON CREATE SET target.id = ct.target_doc_id,
                target.trạng_thái = "PLACEHOLDER",
                target.ingested_at = datetime()
MERGE (src)-[:REFERENCES]->(target);

// @citations_internal
UNWIND $citations_internal AS ct
MATCH (src {id: ct.source_id})
MATCH (a:Article {id: ct.target_article_id})
MERGE (src)-[:REFERENCES]->(a);
