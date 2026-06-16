"use client";

import { REL_INFO, REL_COLOR, NODE_LEGEND } from "@/lib/constants";

export function NodeLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {NODE_LEGEND.map((n) => (
        <span key={n.name} className="flex items-center gap-1 text-[13px]">
          <span
            className="inline-block h-3 w-3 rounded-full"
            style={{ background: n.color }}
          />
          {n.name}
        </span>
      ))}
    </div>
  );
}

export function RelLegend() {
  return (
    <div>
      <table className="data">
        <thead>
          <tr>
            <th>Quan hệ</th>
            <th>VN</th>
            <th>Mô tả</th>
          </tr>
        </thead>
        <tbody>
          {REL_INFO.map((r) => (
            <tr key={r.code}>
              <td className="whitespace-nowrap">
                <span
                  className="mr-2 inline-block h-[5px] w-7 rounded align-middle"
                  style={{ background: REL_COLOR[r.code] || "#999" }}
                />
                <span
                  className="font-mono text-xs font-semibold"
                  style={{ color: REL_COLOR[r.code] || "#999" }}
                >
                  {r.code}
                </span>
              </td>
              <td className="whitespace-nowrap text-[13px] font-semibold">{r.vn}</td>
              <td className="text-xs text-slate-600">{r.desc}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-400">
        💡 Di chuột lên mũi tên trong graph để xem loại quan hệ.
      </p>
    </div>
  );
}
