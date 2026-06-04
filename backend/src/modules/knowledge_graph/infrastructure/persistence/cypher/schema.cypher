// Constraints & indexes — LEGAL_KG_PIPELINE.md section 3.5. Run once on init.
// Statements are separated by semicolons and executed individually (idempotent).

CREATE CONSTRAINT doc_id_unique IF NOT EXISTS
  FOR (d:Document) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT doc_so_hieu_unique IF NOT EXISTS
  FOR (d:Document) REQUIRE d.số_hiệu IS UNIQUE;

CREATE CONSTRAINT article_id_unique IF NOT EXISTS
  FOR (a:Article) REQUIRE a.id IS UNIQUE;

CREATE CONSTRAINT clause_id_unique IF NOT EXISTS
  FOR (c:Clause) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT point_id_unique IF NOT EXISTS
  FOR (p:Point) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT chapter_id_unique IF NOT EXISTS
  FOR (ch:Chapter) REQUIRE ch.id IS UNIQUE;

CREATE CONSTRAINT authority_name_unique IF NOT EXISTS
  FOR (a:Authority) REQUIRE a.tên IS UNIQUE;

CREATE CONSTRAINT doctype_code_unique IF NOT EXISTS
  FOR (t:DocumentType) REQUIRE t.code IS UNIQUE;

CREATE INDEX doc_loai IF NOT EXISTS FOR (d:Document) ON (d.loại_code);

CREATE INDEX doc_trang_thai IF NOT EXISTS FOR (d:Document) ON (d.trạng_thái);

CREATE INDEX doc_hieu_luc IF NOT EXISTS FOR (d:Document) ON (d.ngày_hiệu_lực);

CREATE INDEX doc_ban_hanh IF NOT EXISTS FOR (d:Document) ON (d.ngày_ban_hành);

CREATE INDEX doc_loai_hieu_luc IF NOT EXISTS
  FOR (d:Document) ON (d.loại_code, d.ngày_hiệu_lực);

CREATE FULLTEXT INDEX article_fulltext IF NOT EXISTS
  FOR (a:Article) ON EACH [a.tiêu_đề, a.nội_dung];

CREATE FULLTEXT INDEX clause_fulltext IF NOT EXISTS
  FOR (c:Clause) ON EACH [c.nội_dung];
