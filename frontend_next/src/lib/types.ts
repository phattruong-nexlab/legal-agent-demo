// Shared TypeScript types for the frontend.

// vis-network compatible shapes (we feed these straight into the network).
export interface GraphNode {
  id: string;
  label: string;
  size: number;
  color: string;
  title: string; // HTML tooltip
}

export interface GraphEdge {
  // vis-network uses `from`/`to`; we keep `id`-free and let vis assign.
  from: string;
  to: string;
  label: string;
  title: string;
  color: string;
  width: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  nMatched: number;
  nTotal: number;
  hasFilter: boolean;
}

export interface DocRow {
  id: string;
  so_hieu: string | null;
  display: string;
  loai_code: string | null;
  ngay_bh: unknown;
  trang_thai: string | null;
  co_quan: string | null;
}

export interface SearchHit {
  kind: string;
  id: string;
  so: number | null;
  tieu_de: string | null;
  preview: string;
  doc_id: string;
  doc_display: string | null;
  doc_so_hieu: string | null;
  score: number;
}

export interface DocDetails {
  doc: Record<string, any>;
  arts: { số: number | null; tiêu_đề: string | null }[];
}

export interface GraphStats {
  documents: number;
  placeholders: number;
  articles: number;
  clauses: number;
  points: number;
  amends: number;
  repeals: number;
  replaces: number;
  based_on: number;
  refs: number;
}

// ---- Backend API response types (mirror pydantic schemas) ----
export interface LegalBasisItem {
  law_number: string;
  law_name: string;
  date: string;
}

export interface ExtractLegalBasisResponse {
  document: LegalBasisItem;
  legal_bases: LegalBasisItem[];
}

export interface DocumentSegment {
  unit_type: string;
  index: number;
  label: string;
  content: string;
}

export interface ExtractSegmentsResponse {
  unit_type: string;
  segments: DocumentSegment[];
}

export interface SegmentComplianceResult {
  segment_index: number | null;
  segment_label: string;
  applicable: boolean;
  status: string;
  reason: string;
}

export interface AuditByGraphResult {
  audited_law: string;
  date: string;
  matched_doc_id: string | null;
  overall_status: string;
  explanation: string;
  segments: SegmentComplianceResult[];
}

export interface AuditByGraphResponse {
  unit_type: string;
  results: AuditByGraphResult[];
}

export interface IngestReport {
  so_hieu?: string | null;
  doc_class?: string | null;
  doc_id?: string | null;
  n_articles?: number;
  n_clauses?: number;
  n_points?: number;
  n_amendments?: number;
  n_citations?: number;
  loaded?: boolean;
  metadata_incomplete?: boolean;
}

export interface FileIngestResult {
  filename: string;
  success: boolean;
  report: IngestReport | null;
  error: string | null;
}

export interface BatchIngestReport {
  total: number;
  succeeded: number;
  failed: number;
  results: FileIngestResult[];
}

export interface QueryArticleStatusResponse {
  question: string;
  parsed: {
    law_number: string;
    law_name: string;
    article_so: number | null;
    clause_so: number | null;
    point_kyhieu: string;
    intent: string;
  };
  document: {
    doc_id: string;
    so_hieu: string;
    ten: string;
    loai: string;
    ngay_ban_hanh: string;
    ngay_hieu_luc: string;
    ngay_het_hieu_luc: string;
    trang_thai: string;
  } | null;
  article: {
    id: string;
    so: number;
    tieu_de: string;
    noi_dung: string;
    clauses: {
      so: number | null;
      noi_dung: string;
      thu_tu: number | null;
      points: { ky_hieu: string; noi_dung: string; thu_tu: number | null }[];
    }[];
  } | null;
  amendments: {
    rel_type: string;
    src_doc_id: string;
    src_so_hieu: string;
    src_ten: string;
    src_ngay_ban_hanh: string;
    src_trang_thai: string;
    scope: string;
    scope_type: string;
    target_article: number | null;
    target_clause: number | null;
    target_point: string | null;
    effective_from: string;
  }[];
  answer: string;
}
