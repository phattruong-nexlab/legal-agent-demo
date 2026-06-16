// Visual styling + domain vocab ported from frontend/main.py (Streamlit).
// Shared between server (graph transforms) and client (legends, badges).

export const LABEL_COLOR: Record<string, string> = {
  Document: "#4F8EF7",
  _Placeholder: "#B0BEC5",
  Chapter: "#16A085",
  Article: "#27AE60",
  Clause: "#7DCEA0",
  Point: "#A9DFBF",
  Authority: "#E67E22",
  DocumentType: "#9B59B6",
};

export const REL_COLOR: Record<string, string> = {
  // Lifecycle — warm, high-contrast palette
  AMENDS: "#F77F00",
  REPEALS: "#D62828",
  REPLACES: "#FF006E",
  // Provenance & citation — cool palette
  BASED_ON: "#0077B6",
  REFERENCES: "#2A9D8F",
  // Metadata — purple family
  ISSUED_BY: "#6A4C93",
  OF_TYPE: "#8338EC",
  // Structural — muted gray
  HAS_CHAPTER: "#B0BEC5",
  HAS_ARTICLE: "#B0BEC5",
  HAS_CLAUSE: "#CFD8DC",
  HAS_POINT: "#ECEFF1",
};

export interface RelInfo {
  code: string;
  vn: string;
  desc: string;
}

export const REL_INFO: RelInfo[] = [
  { code: "AMENDS", vn: "Sửa đổi", desc: "VB hiện tại sửa đổi / bổ sung điều khoản của VB kia." },
  { code: "REPEALS", vn: "Bãi bỏ", desc: "VB hiện tại bãi bỏ Điều/Khoản hoặc cụm từ trong VB kia." },
  { code: "REPLACES", vn: "Thay thế", desc: "Thay thế phụ lục hoặc cụm từ bên trong VB kia." },
  { code: "BASED_ON", vn: "Căn cứ pháp lý", desc: "VB hiện tại được ban hành căn cứ vào VB kia (phần 'Căn cứ...')." },
  { code: "REFERENCES", vn: "Dẫn chiếu", desc: "Điều / Khoản của VB hiện tại dẫn chiếu nội dung trong VB kia." },
  { code: "ISSUED_BY", vn: "Ban hành bởi", desc: "Cơ quan ban hành văn bản (Bộ, Chính phủ, Quốc hội...)." },
  { code: "OF_TYPE", vn: "Loại văn bản", desc: "Phân loại văn bản (Luật / Nghị định / Thông tư...)." },
];

export const DOC_TYPE_LABEL: Record<string, string> = {
  LUAT: "Luật",
  NQ: "Nghị quyết",
  ND: "Nghị định",
  TT: "Thông tư",
  QD: "Quyết định",
  CT: "Chỉ thị",
  PL: "Pháp lệnh",
  UNKNOWN: "Khác",
};

// Node legend (order matters for display).
export const NODE_LEGEND: { name: string; color: string }[] = [
  { name: "Document", color: LABEL_COLOR.Document },
  { name: "Placeholder", color: LABEL_COLOR._Placeholder },
  { name: "Article", color: LABEL_COLOR.Article },
  { name: "Clause", color: LABEL_COLOR.Clause },
  { name: "Authority", color: LABEL_COLOR.Authority },
  { name: "DocumentType", color: LABEL_COLOR.DocumentType },
];

// ---- Audit page ----
export const STATUS_META: Record<string, { icon: string; color: string }> = {
  "Tuân thủ": { icon: "✅", color: "#16A34A" },
  "Không tuân thủ": { icon: "❌", color: "#DC2626" },
  "Cần kiểm tra": { icon: "⚠️", color: "#F59E0B" },
  "Không tìm thấy trong hệ thống": { icon: "❓", color: "#6B7280" },
};

export function normStatus(s: string | null | undefined): string {
  const v = (s || "").trim() || "Cần kiểm tra";
  return v === "Không liên quan" ? "Cần kiểm tra" : v;
}

// ---- Query page ----
export const DOC_STATUS_BADGE: Record<string, { label: string; color: string }> = {
  HIEU_LUC: { label: "🟢 Còn hiệu lực", color: "#16A34A" },
  HET_HIEU_LUC: { label: "🔴 Hết hiệu lực", color: "#DC2626" },
  SUA_DOI: { label: "🟠 Đã được sửa đổi", color: "#F77F00" },
  CHUA_HIEU_LUC: { label: "🟡 Chưa có hiệu lực", color: "#F59E0B" },
  PLACEHOLDER: { label: "⚪ Chưa nạp đầy đủ", color: "#9CA3AF" },
};

export const REL_VN_LABEL: Record<string, string> = {
  AMENDS: "Sửa đổi/bổ sung",
  REPEALS: "Bãi bỏ",
  REPLACES: "Thay thế",
};

export const SAMPLE_QUESTIONS = [
  "Điều 18 Thông tư 08/2022 còn hiệu lực không?",
  "Nội dung Điều 5 Nghị định 58/2023 là gì?",
  "Khoản 2 Điều 10 Luật Giáo dục 2019 đã bị sửa đổi chưa?",
];
