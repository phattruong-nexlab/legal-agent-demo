"use client";

import { useState } from "react";
import { backendPostForm } from "@/lib/client-api";
import { STATUS_META, normStatus } from "@/lib/constants";
import type {
  ExtractLegalBasisResponse,
  ExtractSegmentsResponse,
  AuditByGraphResponse,
  LegalBasisItem,
  DocumentSegment,
} from "@/lib/types";

export default function AuditPage() {
  const [file, setFile] = useState<File | null>(null);
  const [extracted, setExtracted] = useState<ExtractLegalBasisResponse | null>(null);
  const [segData, setSegData] = useState<ExtractSegmentsResponse | null>(null);
  const [results, setResults] = useState<AuditByGraphResponse | null>(null);

  const [busy, setBusy] = useState<string>("");
  const [error, setError] = useState("");
  const [elapsed, setElapsed] = useState<number | null>(null);

  const reset = () => {
    setFile(null);
    setExtracted(null);
    setSegData(null);
    setResults(null);
    setError("");
    setElapsed(null);
  };

  const onPick = (f: File | null) => {
    reset();
    setFile(f);
  };

  const doExtract = async () => {
    if (!file) return;
    setBusy("extract");
    setError("");
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      setExtracted(await backendPostForm("legal-analysis/extract-legal-basis", form));
    } catch (e: any) {
      setError(`Extract thất bại: ${e?.message || e}`);
    } finally {
      setBusy("");
    }
  };

  const doSegments = async () => {
    if (!file) return;
    setBusy("segments");
    setError("");
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      setSegData(await backendPostForm("legal-analysis/extract-segments", form));
    } catch (e: any) {
      setError(`Trích cấu trúc thất bại: ${e?.message || e}`);
    } finally {
      setBusy("");
    }
  };

  const doAudit = async () => {
    if (!extracted || !segData) return;
    setBusy("audit");
    setError("");
    const t0 = Date.now();
    try {
      const form = new FormData();
      form.append("audited_document", JSON.stringify(extracted.document));
      form.append("legal_bases", JSON.stringify(extracted.legal_bases));
      form.append("segments", JSON.stringify(segData.segments));
      const data = await backendPostForm("legal-analysis/audit-by-graph", form);
      setResults(data);
      setElapsed((Date.now() - t0) / 1000);
    } catch (e: any) {
      setError(`Audit thất bại: ${e?.message || e}`);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">🔎 Audit tuân thủ văn bản</h1>
          <p className="mt-1 text-sm text-slate-500">Backend qua proxy: /api/backend/legal-analysis</p>
        </div>
        <button className="btn" onClick={reset}>
          🔄 Reset
        </button>
      </div>

      <div className="card mt-5">
        <label className="mb-1 block text-sm font-medium">Tải lên văn bản PDF cần audit</label>
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => onPick(e.target.files?.[0] || null)}
          className="block w-full text-sm"
        />
        {file && (
          <p className="mt-2 text-sm text-green-700">
            📄 <b>{file.name}</b> ({(file.size / 1024).toFixed(1)} KB)
          </p>
        )}
      </div>

      {error && <div className="card mt-4 border-red-200 bg-red-50 text-red-700">❌ {error}</div>}

      {!file ? (
        <p className="mt-4 text-sm text-slate-500">⬆️ Tải file PDF để bắt đầu.</p>
      ) : (
        <>
          {/* Step 1 */}
          <Step title="Bước 1 — Trích xuất căn cứ pháp lý">
            {!extracted ? (
              <button className="btn btn-primary" disabled={busy === "extract"} onClick={doExtract}>
                {busy === "extract" ? "Đang trích…" : "🔍 Trích xuất từ trang đầu"}
              </button>
            ) : (
              <ExtractedSection data={extracted} />
            )}
          </Step>

          {/* Step 2 */}
          {extracted && extracted.legal_bases.length > 0 && (
            <Step title="Bước 2 — Trích cấu trúc văn bản đầu vào">
              {!segData ? (
                <>
                  <p className="mb-2 text-xs text-slate-500">
                    Hệ thống lấy đơn vị cấu trúc lớn nhất (Chương → nếu không có thì Điều).
                  </p>
                  <button
                    className="btn btn-primary"
                    disabled={busy === "segments"}
                    onClick={doSegments}
                  >
                    {busy === "segments" ? "Đang trích…" : "🧩 Trích cấu trúc"}
                  </button>
                </>
              ) : (
                <SegmentsSection unitType={segData.unit_type} segments={segData.segments} />
              )}
            </Step>
          )}

          {/* Step 3 */}
          {segData && segData.segments.length > 0 && (
            <Step title="Bước 3 — Đối chiếu với Knowledge Graph">
              {!results ? (
                <>
                  <p className="mb-2 text-xs text-slate-500">
                    Mỗi {segData.unit_type} được đối chiếu với từng căn cứ (chạy song song).
                  </p>
                  <button className="btn btn-primary" disabled={busy === "audit"} onClick={doAudit}>
                    {busy === "audit" ? "Đang đối chiếu…" : "⚖️ Bắt đầu audit"}
                  </button>
                </>
              ) : (
                <>
                  {elapsed !== null && (
                    <p className="mb-2 text-sm text-green-700">Hoàn tất sau {elapsed.toFixed(1)}s.</p>
                  )}
                  <ResultsSection response={results} />
                </>
              )}
            </Step>
          )}
        </>
      )}
    </div>
  );
}

function Step({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <h2 className="mb-3 border-t border-slate-200 pt-4 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function ExtractedSection({ data }: { data: ExtractLegalBasisResponse }) {
  const doc = data.document;
  const bases = data.legal_bases;
  return (
    <div>
      <div className="card">
        <p className="font-medium">📄 Văn bản được audit:</p>
        <ul className="mt-1 text-sm">
          <li>
            <b>Số hiệu:</b> <code>{doc.law_number || "—"}</code>
          </li>
          <li>
            <b>Tên:</b> {doc.law_name || "—"}
          </li>
          <li>
            <b>Ngày BH:</b> {doc.date || "—"}
          </li>
        </ul>
      </div>
      {bases.length === 0 ? (
        <div className="card mt-3 border-amber-200 bg-amber-50 text-amber-700">
          ⚠️ Không trích được căn cứ pháp lý nào từ trang đầu.
        </div>
      ) : (
        <>
          <p className="mt-3 font-medium">🔗 {bases.length} căn cứ pháp lý trích được:</p>
          <table className="data mt-1">
            <thead>
              <tr>
                <th>#</th>
                <th>Số hiệu</th>
                <th>Tên</th>
                <th>Ngày</th>
              </tr>
            </thead>
            <tbody>
              {bases.map((b: LegalBasisItem, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>{b.law_number}</td>
                  <td>{b.law_name}</td>
                  <td>{b.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function SegmentsSection({ unitType, segments }: { unitType: string; segments: DocumentSegment[] }) {
  return (
    <div>
      <p className="font-medium">
        🧩 Đơn vị cấu trúc lớn nhất: <code>{unitType}</code> — {segments.length} phần
      </p>
      <table className="data mt-1">
        <thead>
          <tr>
            <th>#</th>
            <th>Phần</th>
            <th>Độ dài (ký tự)</th>
          </tr>
        </thead>
        <tbody>
          {segments.map((s) => (
            <tr key={s.index}>
              <td>{s.index}</td>
              <td>{s.label}</td>
              <td>{(s.content || "").length}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <details className="mt-2">
        <summary className="cursor-pointer text-sm text-slate-600">Xem nội dung từng phần</summary>
        <div className="mt-2 space-y-3">
          {segments.map((s) => (
            <div key={s.index}>
              <p className="font-medium">{s.label}</p>
              <pre className="whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">
                {(s.content || "").slice(0, 2000)}
              </pre>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

function ResultsSection({ response }: { response: AuditByGraphResponse }) {
  const unitType = response.unit_type || "phần";
  const results = response.results || [];

  const counts: Record<string, number> = {};
  for (const k of Object.keys(STATUS_META)) counts[k] = 0;
  for (const r of results) {
    const st = normStatus(r.overall_status);
    counts[st] = (counts[st] || 0) + 1;
  }

  return (
    <div>
      <div className="grid grid-cols-4 gap-3">
        <Metric label="✅ Tuân thủ" value={counts["Tuân thủ"] || 0} />
        <Metric label="❌ Không tuân thủ" value={counts["Không tuân thủ"] || 0} />
        <Metric label="⚠️ Cần kiểm tra" value={counts["Cần kiểm tra"] || 0} />
        <Metric label="❓ Không tìm thấy" value={counts["Không tìm thấy trong hệ thống"] || 0} />
      </div>

      <h3 className="mt-5 text-base font-semibold">📋 Kết quả tổng hợp</h3>
      <table className="data mt-1">
        <thead>
          <tr>
            <th>#</th>
            <th>Căn cứ pháp lý</th>
            <th>Ngày</th>
            <th>Trạng thái</th>
            <th>Khớp KG</th>
            <th>{unitType} liên quan</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => {
            const status = normStatus(r.overall_status);
            const icon = STATUS_META[status]?.icon || "•";
            const segs = r.segments || [];
            const nRel = segs.filter((s) => s.applicable).length;
            return (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>{r.audited_law || ""}</td>
                <td>{r.date || ""}</td>
                <td>
                  {icon} {status}
                </td>
                <td>{r.matched_doc_id ? "✓" : "—"}</td>
                <td>{segs.length ? nRel : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <h3 className="mt-5 text-base font-semibold">🔍 Chi tiết — chỉ các {unitType} liên quan</h3>
      <p className="text-xs text-slate-500">
        Các {unitType} không thuộc phạm vi điều chỉnh đã được lọc bỏ. Cột &quot;Lý do&quot; giải thích kết
        luận (kể cả khi tuân thủ).
      </p>
      <div className="mt-2 space-y-2">
        {results.map((r, i) => {
          const status = normStatus(r.overall_status);
          const icon = STATUS_META[status]?.icon || "•";
          const segs = r.segments || [];
          const related = segs.filter((s) => s.applicable);
          return (
            <details key={i} className="card">
              <summary className="cursor-pointer font-medium">
                {icon} {i + 1}. {r.audited_law || "?"} — {status} ({related.length}/{segs.length}{" "}
                {unitType} liên quan)
              </summary>
              {r.explanation && (
                <div className="mt-2 rounded bg-blue-50 p-2 text-sm">{r.explanation}</div>
              )}
              {related.length === 0 ? (
                <p className="mt-2 text-xs text-slate-500">
                  Không có {unitType} nào liên quan đến căn cứ này.
                </p>
              ) : (
                <table className="data mt-2">
                  <thead>
                    <tr>
                      <th>Phần</th>
                      <th>Trạng thái</th>
                      <th>Lý do</th>
                    </tr>
                  </thead>
                  <tbody>
                    {related.map((s, j) => {
                      const sStatus = normStatus(s.status);
                      const sIcon = STATUS_META[sStatus]?.icon || "•";
                      return (
                        <tr key={j}>
                          <td>{s.segment_label || ""}</td>
                          <td>
                            {sIcon} {sStatus}
                          </td>
                          <td>{s.reason || ""}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </details>
          );
        })}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}
