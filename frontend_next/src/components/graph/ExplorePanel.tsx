"use client";

import { useEffect, useState } from "react";
import { fetchSearch, fetchDocuments, fetchDocDetails } from "@/lib/client-api";
import { DOC_TYPE_LABEL } from "@/lib/constants";
import type { SearchHit, DocRow, DocDetails } from "@/lib/types";

type Tab = "search" | "browse" | "detail";

interface Props {
  onlyReal: boolean;
  selectedDocId: string | null;
  onSelectDoc: (id: string) => void;
}

export default function ExplorePanel({ onlyReal, selectedDocId, onSelectDoc }: Props) {
  const [tab, setTab] = useState<Tab>("search");

  return (
    <div style={{ minWidth: 360 }}>
      <div className="mb-3 flex gap-1 border-b border-slate-200">
        <TabBtn active={tab === "search"} onClick={() => setTab("search")}>
          🔍 Tìm trong nội dung
        </TabBtn>
        <TabBtn active={tab === "browse"} onClick={() => setTab("browse")}>
          📋 Duyệt văn bản
        </TabBtn>
        <TabBtn active={tab === "detail"} onClick={() => setTab("detail")}>
          📄 Chi tiết
        </TabBtn>
      </div>
      {tab === "search" && <SearchTab onSelectDoc={onSelectDoc} />}
      {tab === "browse" && <BrowseTab onlyReal={onlyReal} onSelectDoc={onSelectDoc} />}
      {tab === "detail" && <DetailTab selectedDocId={selectedDocId} />}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`-mb-px border-b-2 px-2 py-1.5 text-xs font-medium ${
        active ? "border-brand text-brand" : "border-transparent text-slate-500 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

function SearchTab({ onSelectDoc }: { onSelectDoc: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (!q.trim()) {
      setHits([]);
      setTouched(false);
      return;
    }
    setLoading(true);
    setTouched(true);
    const t = setTimeout(async () => {
      try {
        const { hits } = await fetchSearch(q.trim());
        setHits(hits);
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div>
      <input
        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
        placeholder='vd: "tuyển sinh", "mã trường"'
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {loading && <p className="mt-2 text-xs text-slate-400">Đang tìm...</p>}
      {touched && !loading && <p className="mt-2 text-xs text-slate-400">{hits.length} kết quả</p>}
      <div className="mt-2 space-y-2">
        {hits.map((h) => (
          <div key={h.id} className="card p-3">
            <p className="text-sm font-semibold">
              {h.doc_display} <code className="text-xs text-slate-500">{h.doc_so_hieu || ""}</code>
            </p>
            <p className="text-sm">
              Điều {h.so ?? "?"} — <em>{h.tieu_de || ""}</em>
            </p>
            <p className="mt-1 text-xs text-slate-500">{h.preview}</p>
            <button className="btn mt-2 w-full" onClick={() => onSelectDoc(h.doc_id)}>
              Xem trong graph →
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function BrowseTab({
  onlyReal,
  onSelectDoc,
}: {
  onlyReal: boolean;
  onSelectDoc: (id: string) => void;
}) {
  const [docs, setDocs] = useState<DocRow[]>([]);

  useEffect(() => {
    fetchDocuments([], onlyReal).then((d) => setDocs(d.docs));
  }, [onlyReal]);

  return (
    <div>
      <p className="mb-2 text-xs text-slate-400">{docs.length} văn bản</p>
      <div className="space-y-1">
        {docs.map((d) => (
          <button
            key={d.id}
            onClick={() => onSelectDoc(d.id)}
            className="flex w-full items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5 text-left text-sm hover:border-brand hover:bg-slate-50"
          >
            <span>{(d.trang_thai || "") !== "PLACEHOLDER" ? "🟦" : "⬜"}</span>
            <span className="flex-1 truncate">{d.display}</span>
            <code className="text-xs text-slate-400">{d.so_hieu || ""}</code>
          </button>
        ))}
      </div>
    </div>
  );
}

function DetailTab({ selectedDocId }: { selectedDocId: string | null }) {
  const [det, setDet] = useState<DocDetails | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedDocId) {
      setDet(null);
      return;
    }
    setLoading(true);
    fetchDocDetails(selectedDocId)
      .then((d) => setDet(d.details))
      .finally(() => setLoading(false));
  }, [selectedDocId]);

  if (!selectedDocId) return <p className="text-sm text-slate-500">Chọn 1 văn bản để xem chi tiết.</p>;
  if (loading) return <p className="text-sm text-slate-400">Đang tải...</p>;
  if (!det) return <p className="text-sm text-amber-600">Không tìm thấy.</p>;

  const doc = det.doc;
  return (
    <div className="space-y-2 text-sm">
      <h3 className="text-base font-bold">{doc["tên_ngắn"] || doc["tên"] || doc["id"]}</h3>
      <pre className="rounded bg-slate-100 px-2 py-1 text-xs">{doc["số_hiệu"] || ""}</pre>
      <div className="grid grid-cols-2 gap-1">
        <div>
          <b>Loại:</b> {DOC_TYPE_LABEL[doc["loại_code"]] || doc["loại_code"] || ""}
        </div>
        <div>
          <b>Trạng thái:</b> {doc["trạng_thái"] || "—"}
        </div>
        <div>
          <b>Ngày BH:</b> {doc["ngày_ban_hành"] || "—"}
        </div>
        <div>
          <b>Hiệu lực:</b> {doc["ngày_hiệu_lực"] || "—"}
        </div>
      </div>
      {doc["cơ_quan_ban_hành"] && (
        <div>
          <b>Cơ quan:</b> {doc["cơ_quan_ban_hành"]}
        </div>
      )}
      {doc["người_ký"] && (
        <div>
          <b>Người ký:</b> {doc["người_ký"]} ({doc["chức_vụ_người_ký"] || ""})
        </div>
      )}
      {det.arts.length > 0 && (
        <div>
          <b>Mục lục Điều:</b>
          <ul className="mt-1 list-disc pl-5">
            {[...det.arts]
              .sort((a, b) => (a["số"] || 0) - (b["số"] || 0))
              .map((a, i) => (
                <li key={i}>
                  Điều {a["số"]} — {a["tiêu_đề"] || ""}
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
