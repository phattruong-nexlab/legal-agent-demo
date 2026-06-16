"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: "left" | "right";
  width?: number;
}

export default function Popover({ trigger, children, align = "left", width = 460 }: Props) {
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

  return (
    <div className="relative inline-block" ref={ref}>
      <button className="btn btn-pill" onClick={() => setOpen((v) => !v)}>
        {trigger}
      </button>
      {open && (
        <div
          className="absolute z-30 mt-2 max-h-[70vh] overflow-auto rounded-lg border border-slate-200 bg-white p-4 shadow-xl"
          style={{ width, [align]: 0 } as React.CSSProperties}
        >
          {children}
        </div>
      )}
    </div>
  );
}
