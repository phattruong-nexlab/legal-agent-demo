"use client";

import { useState } from "react";
import { backendPostJson } from "@/lib/client-api";
import { DOC_STATUS_BADGE, REL_VN_LABEL, SAMPLE_QUESTIONS } from "@/lib/constants";
import type { QueryArticleStatusResponse } from "@/lib/types";

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QueryArticleStatusResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const run = async (qOverride?: string) => {
    const q = (qOverride ?? question).trim();
    if (!q) return;
    setQuestion(q);
    setResult(null);
    setError("");
    setLoading(true);
    try {
      setResult(await backendPostJson("legal-analysis/query-article-status", { question: q }));
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setQuestion("");
    setResult(null);
    setError("");
  };

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">🤖 Hỏi đáp Knowledge Graph</h1>
          <p className="mt-1 text-sm text-slate-500">
            Đặt câu hỏi tự nhiên về một Điều/Khoản — hệ thống dùng LLM để hiểu câu hỏi, truy vấn ngược
            graph, rồi sinh câu trả lời.
          </p>
        </div>
        <button className="btn" onClick={reset}>
          🔄 Xóa
        </button>
      </div>

      <p className="mt-4 text-sm font-medium">Câu hỏi mẫu:</p>
      <div className="mt-1 grid gap-2 sm:grid-cols-3">
        {SAMPLE_QUESTIONS.map((q, i) => (
          <button key={i} className="btn text-left text-xs" onClick={() => run(q)}>
            {q}
          </button>
        ))}
      </div>

      <textarea
        className="mt-4 w-full rounded-md border border-slate-300 p-3 text-sm"
        rows={3}
        placeholder='vd: "Điều 18 Thông tư 08/2022 còn hiệu lực không?"'
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <button
        className="btn btn-primary mt-2"
        disabled={!question.trim() || loading}
        onClick={() => run()}
      >
        {loading ? "Đang tra cứu…" : "🔍 Tra cứu"}
      </button>

      {error && <div className="card mt-4 border-red-200 bg-red-50 text-red-700">❌ {error}</div>}

      {!result && !error && (
        <p className="mt-4 text-sm text-slate-500">⬆️ Nhập câu hỏi rồi nhấn Tra cứu.</p>
      )}

      {result && (
        <div className="mt-6 space-y-5">
          {result.answer?.trim() && (
            <div>
              <h3 className="text-base font-semibold">💬 Trả lời</h3>
              <div className="mt-1 rounded-md border-l-4 border-brand bg-blue-50 p-4 text-[15px] leading-relaxed">
                {result.answer}
              </div>
            </div>
          )}

          <details className="card">
            <summary className="cursor-pointer text-sm font-medium">
              🧠 LLM đã hiểu câu hỏi như thế nào
            </summary>
            <table className="data mt-2">
              <tbody>
                {[
                  ["Số hiệu", result.parsed.law_number || "—"],
                  ["Tên VB", result.parsed.law_name || "—"],
                  ["Điều", result.parsed.article_so ?? "—"],
                  ["Khoản", result.parsed.clause_so ?? "—"],
                  ["Điểm", result.parsed.point_kyhieu || "—"],
                  ["Ý định", result.parsed.intent || "—"],
                ].map(([k, v]) => (
                  <tr key={String(k)}>
                    <td className="font-medium">{k}</td>
                    <td>{String(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          <div>
            <h3 className="text-base font-semibold">📚 Dữ liệu graph</h3>
            <DocCard doc={result.document} />
            <ArticleCard article={result.article} />
            <Amendments amendments={result.amendments || []} />
          </div>
        </div>
      )}
    </div>
  );
}

function DocCard({ doc }: { doc: QueryArticleStatusResponse["document"] }) {
  if (!doc) {
    return (
      <div className="card mt-2 border-amber-200 bg-amber-50 text-amber-700">
        Không tìm thấy văn bản tương ứng trong Knowledge Graph.
      </div>
    );
  }
  const badge = DOC_STATUS_BADGE[doc.trang_thai] || { label: doc.trang_thai || "—", color: "#6B7280" };
  return (
    <div className="card mt-2">
      <p className="font-medium">📄 {doc.ten || doc.so_hieu || doc.doc_id}</p>
      <span
        className="chip mt-1"
        style={{ background: `${badge.color}1A`, color: badge.color }}
      >
        {badge.label}
      </span>
      <div className="mt-2 grid grid-cols-2 gap-1 text-sm">
        <div>
          <b>Số hiệu:</b> <code>{doc.so_hieu || "—"}</code>
        </div>
        <div>
          <b>Loại:</b> {doc.loai || "—"}
        </div>
        <div>
          <b>Ngày BH:</b> {doc.ngay_ban_hanh || "—"}
        </div>
        <div>
          <b>Hiệu lực:</b> {doc.ngay_hieu_luc || "—"}
        </div>
      </div>
      {doc.ngay_het_hieu_luc && (
        <div className="mt-1 text-sm">
          <b>Ngày hết hiệu lực:</b> {doc.ngay_het_hieu_luc}
        </div>
      )}
    </div>
  );
}

function ArticleCard({ article }: { article: QueryArticleStatusResponse["article"] }) {
  if (!article) {
    return (
      <div className="card mt-2 text-sm text-slate-500">
        Câu hỏi không nhắc đến Điều cụ thể, hoặc Điều không tồn tại trong văn bản.
      </div>
    );
  }
  return (
    <div className="card mt-2">
      <p className="font-medium">
        Điều {article.so}
        {article.tieu_de ? ` — ` : ""}
        <em>{article.tieu_de}</em>
      </p>
      {article.noi_dung && <p className="mt-1 text-sm">{article.noi_dung}</p>}
      {article.clauses?.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm text-slate-600">
            📋 {article.clauses.length} khoản
          </summary>
          <div className="mt-1 space-y-1 text-sm">
            {article.clauses.map((cl, i) => (
              <div key={i}>
                <b>Khoản {cl.so}.</b> {cl.noi_dung || ""}
                {(cl.points || []).map((pt, j) => (
                  <div key={j} className="pl-6">
                    <b>{pt.ky_hieu})</b> {pt.noi_dung || ""}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function Amendments({ amendments }: { amendments: QueryArticleStatusResponse["amendments"] }) {
  if (!amendments.length) {
    return (
      <div className="card mt-2 border-green-200 bg-green-50 text-green-700">
        ✅ Không có văn bản nào sửa đổi / bãi bỏ / thay thế ở phạm vi này.
      </div>
    );
  }
  return (
    <div className="mt-2">
      <p className="font-medium">⚠️ {amendments.length} văn bản tác động đến phạm vi đang hỏi:</p>
      <table className="data mt-1">
        <thead>
          <tr>
            <th>Quan hệ</th>
            <th>Văn bản nguồn</th>
            <th>Ngày BH</th>
            <th>Phạm vi</th>
            <th>Mô tả gốc</th>
          </tr>
        </thead>
        <tbody>
          {amendments.map((a, i) => {
            const scopeBits: string[] = [];
            if (a.target_article != null) scopeBits.push(`Điều ${a.target_article}`);
            if (a.target_clause != null) scopeBits.push(`Khoản ${a.target_clause}`);
            if (a.target_point) scopeBits.push(`Điểm ${a.target_point}`);
            const scope = scopeBits.join(" · ") || a.scope_type || "—";
            return (
              <tr key={i}>
                <td>{REL_VN_LABEL[a.rel_type] || a.rel_type}</td>
                <td>{a.src_so_hieu || a.src_doc_id || "—"}</td>
                <td>{a.src_ngay_ban_hanh || "—"}</td>
                <td>{scope}</td>
                <td>{(a.scope || "").slice(0, 120)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
