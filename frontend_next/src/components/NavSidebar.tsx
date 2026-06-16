"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Mirrors the PAGES dict in frontend/main.py. "Hỏi đáp Graph" is hidden there
// (commented out), so it's omitted from the nav but the page still exists.
const PAGES = [
  { href: "/graph", label: "Knowledge Graph", icon: "🕸️" },
  { href: "/ingest", label: "Nạp tài liệu", icon: "📥" },
  { href: "/audit", label: "Audit tuân thủ", icon: "🔎" },
];

export default function NavSidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-slate-200 bg-white">
      <div className="px-4 py-5">
        <div className="flex items-center gap-2 text-lg font-bold text-slate-800">
          <span>⚖️</span>
          <span>Legal KG</span>
        </div>
        <p className="mt-1 text-xs text-slate-400">Knowledge Graph Explorer</p>
      </div>
      <nav className="px-2">
        <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          📑 Trang
        </p>
        {PAGES.map((p) => {
          const active = pathname === p.href || pathname.startsWith(p.href + "/");
          return (
            <Link
              key={p.href}
              href={p.href}
              className={`mb-1 flex items-center gap-2 rounded-md px-3 py-2 text-sm transition ${
                active
                  ? "bg-blue-50 font-semibold text-brand"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <span>{p.icon}</span>
              <span>{p.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
