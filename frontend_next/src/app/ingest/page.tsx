"use client";

import { useState } from "react";
import { backendPostForm } from "@/lib/client-api";
import type { BatchIngestReport, IngestReport } from "@/lib/types";

export default function IngestPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<BatchIngestReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    if (!files.length) return;
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      for (const f of files) form.append("files", f, f.name);
      const data = await backendPostForm("knowledge-graph/ingest", form);
      setResult(data);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-bold">📥 Nạp tài liệu vào Knowledge Graph</h1>
      <p className="mt-1 text-sm text-slate-500">
        Tải lên một hoặc nhiều <b>văn bản pháp luật (PDF)</b>. Hệ thống phân tích cấu trúc và nạp
        (MERGE) vào Neo4j. Quá trình <em>idempotent</em> — nạp lại cùng văn bản sẽ cập nhật node cũ.
      </p>

      <div className="card mt-5">
        <input
          type="file"
          accept="application/pdf"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files || []))}
          className="block w-full text-sm"
        />
        {files.length > 0 && (
          <p className="mt-2 text-xs text-slate-500">{files.length} file đã chọn</p>
        )}
        <div className="mt-3 flex gap-2">
          <button className="btn btn-primary" disabled={!files.length || loading} onClick={run}>
            {loading ? "Đang ingest…" : "🚀 Ingest"}
          </button>
          <button
            className="btn"
            onClick={() => {
              setResult(null);
              setError("");
            }}
          >
            🧹 Xoá kết quả
          </button>
        </div>
      </div>

      {error && (
        <div className="card mt-4 border-red-200 bg-red-50 text-red-700">Lỗi: {error}</div>
      )}

      {result && (
        <div className="mt-6">
          <div className="grid grid-cols-3 gap-3">
            <Metric label="Tổng số file" value={result.total} />
            <Metric label="Thành công" value={result.succeeded} />
            <Metric label="Thất bại" value={result.failed} />
          </div>
          <div className="mt-4 space-y-2">
            {result.results.map((item, i) => (
              <details key={i} className="card" open={!item.success}>
                <summary className="cursor-pointer font-medium">
                  {item.success ? "✅" : "❌"} {item.filename}
                </summary>
                {item.success && item.report ? (
                  <ReportView report={item.report} />
                ) : (
                  <p className="mt-2 text-sm text-red-600">
                    {item.error || "Ingest thất bại (không rõ lý do)."}
                  </p>
                )}
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ReportView({ report }: { report: IngestReport }) {
  const flags: string[] = [report.loaded ? "✅ Đã nạp vào graph" : "⚠️ Chưa nạp vào graph"];
  if (report.metadata_incomplete) flags.push("⚠️ Metadata chưa đầy đủ");
  return (
    <div className="mt-3">
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <b>Số hiệu:</b> {report.so_hieu || "—"}
        </div>
        <div>
          <b>Loại:</b> {report.doc_class || "—"}
        </div>
        <div>
          <b>Doc ID:</b> <code className="text-xs">{report.doc_id || "—"}</code>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-5 gap-2">
        <Metric label="Điều" value={report.n_articles ?? 0} />
        <Metric label="Khoản" value={report.n_clauses ?? 0} />
        <Metric label="Điểm" value={report.n_points ?? 0} />
        <Metric label="Sửa đổi" value={report.n_amendments ?? 0} />
        <Metric label="Trích dẫn" value={report.n_citations ?? 0} />
      </div>
      <p className="mt-2 text-xs text-slate-500">{flags.join(" · ")}</p>
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
