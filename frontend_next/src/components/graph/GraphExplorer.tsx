"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import Popover from "@/components/ui/Popover";
import MultiSelect from "@/components/ui/MultiSelect";
import { NodeLegend, RelLegend } from "./Legend";
import ExplorePanel from "./ExplorePanel";
import { DOC_TYPE_LABEL } from "@/lib/constants";
import { fetchGraphMeta, fetchGraphData, fetchDocDetails } from "@/lib/client-api";
import type { GraphData, GraphStats } from "@/lib/types";

const GraphCanvas = dynamic(() => import("./GraphCanvas"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[720px] items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-400">
      Đang tải graph…
    </div>
  ),
});

interface Meta {
  connected: boolean;
  error?: string;
  authorities: string[];
  years: number[];
  stats: Partial<GraphStats>;
}

export default function GraphExplorer() {
  const [meta, setMeta] = useState<Meta | null>(null);

  const [filterAuth, setFilterAuth] = useState<string[]>([]);
  const [filterLoai, setFilterLoai] = useState<string[]>([]);
  const [filterYear, setFilterYear] = useState<string[]>([]);

  const [onlyReal, setOnlyReal] = useState(false);
  const [includeStructure, setIncludeStructure] = useState(false);
  const [maxDocs, setMaxDocs] = useState(60);

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedTitle, setSelectedTitle] = useState<string>("");

  const [graph, setGraph] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchGraphMeta().then(setMeta).catch((e) => setMeta({ connected: false, error: String(e), authorities: [], years: [], stats: {} }));
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchGraphData({
        selectedDocId,
        includeStructure,
        onlyReal,
        maxDocs,
        auth: filterAuth,
        loai: filterLoai,
        year: filterYear.map(Number),
      });
      setGraph(data);
    } finally {
      setLoading(false);
    }
  }, [selectedDocId, includeStructure, onlyReal, maxDocs, filterAuth, filterLoai, filterYear]);

  useEffect(() => {
    if (meta?.connected) reload();
  }, [meta?.connected, reload]);

  // Resolve a friendly title when a document is selected.
  useEffect(() => {
    if (!selectedDocId) {
      setSelectedTitle("");
      return;
    }
    fetchDocDetails(selectedDocId).then((d) => {
      const doc = d.details?.doc;
      setSelectedTitle(
        doc?.["tên_ngắn"] || doc?.["tên"] || doc?.["số_hiệu"] || selectedDocId
      );
    });
  }, [selectedDocId]);

  if (!meta) {
    return <p className="p-8 text-slate-400">Đang kết nối Neo4j Aura…</p>;
  }
  if (!meta.connected) {
    return (
      <div className="p-8">
        <div className="card border-red-200 bg-red-50 text-red-700">
          ❌ Không kết nối được Neo4j: {meta.error || "Kiểm tra .env.local"}
        </div>
      </div>
    );
  }

  const s = meta.stats;
  const yearOptions = meta.years.map((y) => ({ value: String(y), label: String(y) }));
  const authOptions = meta.authorities.map((a) => ({ value: a, label: a }));
  const loaiOptions = Object.keys(DOC_TYPE_LABEL).map((c) => ({
    value: c,
    label: `${c} — ${DOC_TYPE_LABEL[c]}`,
  }));

  return (
    <div className="flex">
      {/* Sidebar: filters + display + stats */}
      <div className="w-72 shrink-0 border-r border-slate-200 bg-white p-4">
        <h2 className="text-base font-bold">🎯 Lọc & Highlight</h2>
        <p className="mb-3 text-xs text-slate-400">
          Document khớp sẽ <b>sáng</b>, không khớp <b>mờ đi</b> — không xóa khỏi graph.
        </p>
        <div className="space-y-3">
          <MultiSelect
            label="Cơ quan ban hành"
            options={authOptions}
            selected={filterAuth}
            onChange={setFilterAuth}
            placeholder="Tất cả cơ quan"
          />
          <MultiSelect
            label="Loại văn bản"
            options={loaiOptions}
            selected={filterLoai}
            onChange={setFilterLoai}
            placeholder="Tất cả loại"
          />
          <MultiSelect
            label="Năm ban hành"
            options={yearOptions}
            selected={filterYear}
            onChange={setFilterYear}
            placeholder="Tất cả năm"
          />
        </div>

        <hr className="my-4 border-slate-200" />
        <h3 className="mb-2 text-sm font-semibold">⚙️ Hiển thị</h3>
        <label className="mb-2 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyReal} onChange={(e) => setOnlyReal(e.target.checked)} />
          Ẩn placeholder
        </label>
        <label className="mb-2 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeStructure}
            onChange={(e) => setIncludeStructure(e.target.checked)}
          />
          Hiện Điều/Khoản
        </label>
        <label className="block text-sm">
          <span className="text-slate-600">Tối đa Document (overview): {maxDocs}</span>
          <input
            type="range"
            min={10}
            max={200}
            step={10}
            value={maxDocs}
            onChange={(e) => setMaxDocs(Number(e.target.value))}
            className="mt-1 w-full"
          />
        </label>

        <hr className="my-4 border-slate-200" />
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold">📊 Thống kê graph</summary>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Metric label="Documents" value={s.documents ?? 0} />
            <Metric label="Placeholders" value={s.placeholders ?? 0} />
            <Metric label="Articles" value={s.articles ?? 0} />
            <Metric label="Clauses" value={s.clauses ?? 0} />
          </div>
          <div className="mt-2 text-xs text-slate-600">
            <b>Quan hệ:</b>
            <ul className="list-disc pl-5">
              <li>AMENDS: {s.amends ?? 0}</li>
              <li>REPEALS: {s.repeals ?? 0}</li>
              <li>REPLACES: {s.replaces ?? 0}</li>
              <li>BASED_ON: {s.based_on ?? 0}</li>
              <li>REFERENCES: {s.refs ?? 0}</li>
            </ul>
          </div>
        </details>
      </div>

      {/* Main content */}
      <div className="flex-1 p-6">
        <h1 className="text-2xl font-bold">⚖️ Legal Knowledge Graph Explorer</h1>
        <p className="mb-4 text-sm text-slate-500">
          Khám phá đồ thị văn bản pháp luật trên Neo4j Aura — click vào node Document để mở rộng.
        </p>

        {/* Action bar */}
        <div className="mb-3 flex items-center gap-2">
          <Popover trigger="📖 Chú thích" width={520}>
            <RelLegend />
          </Popover>
          <Popover trigger="🔍 Khám phá" width={460}>
            <ExplorePanel
              onlyReal={onlyReal}
              selectedDocId={selectedDocId}
              onSelectDoc={(id) => setSelectedDocId(id)}
            />
          </Popover>
          <div className="ml-auto">
            <NodeLegend />
          </div>
        </div>

        <hr className="mb-3 border-slate-200" />

        {/* Title row */}
        {selectedDocId ? (
          <div className="mb-3 flex items-center gap-3">
            <button className="btn" onClick={() => setSelectedDocId(null)}>
              ← Overview
            </button>
            <h2 className="text-lg font-semibold">🎯 {selectedTitle || selectedDocId}</h2>
          </div>
        ) : (
          <h2 className="mb-3 text-lg font-semibold">🗺️ Overview — toàn bộ graph</h2>
        )}

        {/* Filter banner */}
        {graph?.hasFilter && (
          <div className="mb-2 rounded border-l-4 border-orange-500 bg-amber-50 px-3 py-1.5 text-[13px]">
            🎯 <b>Bộ lọc đang bật</b> — khớp {graph.nMatched}/{graph.nTotal} Document. Các Document khác
            mờ đi để giữ ngữ cảnh.
          </div>
        )}

        {/* Graph */}
        {loading && !graph ? (
          <div className="flex h-[720px] items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-400">
            Đang tải graph…
          </div>
        ) : !graph || graph.nodes.length === 0 ? (
          <div className="card text-slate-500">Không có node nào để hiển thị.</div>
        ) : (
          <>
            <GraphCanvas
              nodes={graph.nodes}
              edges={graph.edges}
              height={720}
              onSelectDocument={(id) => setSelectedDocId(id)}
            />
            <p className="mt-2 text-xs text-slate-400">
              📦 {graph.nodes.length} node · 🔗 {graph.edges.length} edge · Click vào Document để zoom
              vào subgraph của nó.
            </p>
          </>
        )}
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
