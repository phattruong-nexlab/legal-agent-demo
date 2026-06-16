"use client";

import { useEffect, useRef, useState } from "react";

export interface Option {
  value: string;
  label: string;
}

interface Props {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}

export default function MultiSelect({
  label,
  options,
  selected,
  onChange,
  placeholder = "Tất cả",
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const toggle = (v: string) => {
    onChange(selected.includes(v) ? selected.filter((s) => s !== v) : [...selected, v]);
  };

  const summary =
    selected.length === 0
      ? placeholder
      : selected.length <= 2
      ? options
          .filter((o) => selected.includes(o.value))
          .map((o) => o.label)
          .join(", ")
      : `${selected.length} đã chọn`;

  return (
    <div className="relative" ref={ref}>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-md border border-slate-300 bg-white px-3 py-1.5 text-left text-sm hover:border-brand"
      >
        <span className={selected.length ? "text-slate-800" : "text-slate-400"}>{summary}</span>
        <span className="text-slate-400">▾</span>
      </button>
      {open && (
        <div className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-md border border-slate-200 bg-white p-1 shadow-lg">
          {options.length === 0 && (
            <p className="px-2 py-1 text-xs text-slate-400">Không có lựa chọn</p>
          )}
          {options.map((o) => (
            <label
              key={o.value}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-slate-50"
            >
              <input
                type="checkbox"
                checked={selected.includes(o.value)}
                onChange={() => toggle(o.value)}
              />
              <span>{o.label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
