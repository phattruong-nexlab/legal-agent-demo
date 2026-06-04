// LEGAL_KG_PIPELINE.md section 7.3.
//
// With the merge-on-số_hiệu strategy in load_document.cypher, ingesting a real
// document automatically upgrades any PLACEHOLDER that shares its số hiệu (the
// node identity is preserved, so inbound AMENDS/REFERENCES stay attached).
// This query therefore just reports the placeholders still awaiting ingestion
// so an operator knows which source documents to feed next.

// @unresolved
MATCH (ph:Document {trạng_thái: "PLACEHOLDER"})
OPTIONAL MATCH ()-[r]->(ph)
RETURN ph.số_hiệu AS số_hiệu, ph.id AS id, count(r) AS referenced_by
ORDER BY referenced_by DESC;
