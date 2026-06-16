"use client";

import { useEffect, useRef } from "react";
import type { GraphNode, GraphEdge } from "@/lib/types";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  height?: number;
  onSelectDocument?: (docId: string) => void;
}

function htmlTitle(html: string): HTMLElement {
  const el = document.createElement("div");
  el.style.maxWidth = "320px";
  el.style.fontSize = "12px";
  el.style.whiteSpace = "normal";
  el.innerHTML = html;
  return el;
}

export default function GraphCanvas({ nodes, edges, height = 720, onSelectDocument }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<any>(null);
  const onSelectRef = useRef(onSelectDocument);
  onSelectRef.current = onSelectDocument;

  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};

    (async () => {
      const vis = await import("vis-network/standalone");
      if (disposed || !containerRef.current) return;

      const visNodes = nodes.map((n) => ({
        id: n.id,
        label: n.label,
        size: n.size,
        color: { background: n.color, border: n.color, highlight: { background: "#F7DC6F", border: "#E1B12C" } },
        title: htmlTitle(n.title),
        shape: "dot",
      }));
      const visEdges = edges.map((e, i) => ({
        id: `e${i}`,
        from: e.from,
        to: e.to,
        color: { color: e.color, highlight: "#F7DC6F" },
        width: e.width,
        title: e.title ? htmlTitle(e.title) : undefined,
      }));

      const data = {
        nodes: new vis.DataSet(visNodes),
        edges: new vis.DataSet(visEdges),
      };
      const options = {
        autoResize: true,
        height: "100%",
        width: "100%",
        physics: {
          enabled: true,
          stabilization: { iterations: 180 },
          barnesHut: { gravitationalConstant: -8000, springLength: 120 },
        },
        interaction: { hover: true, tooltipDelay: 120, navigationButtons: false },
        nodes: { font: { size: 14, face: "Inter, system-ui, sans-serif" }, borderWidth: 1 },
        edges: {
          arrows: { to: { enabled: true, scaleFactor: 0.6 } },
          smooth: { enabled: true, type: "dynamic", roundness: 0.5 },
          font: { size: 0 },
        },
      };

      const network = new vis.Network(containerRef.current, data, options as any);
      networkRef.current = network;

      network.on("click", (params: any) => {
        const id = params?.nodes?.[0];
        if (typeof id === "string" && id.startsWith("Document::")) {
          const docId = id.slice("Document::".length);
          if (docId) onSelectRef.current?.(docId);
        }
      });

      cleanup = () => network.destroy();
    })();

    return () => {
      disposed = true;
      cleanup();
      networkRef.current = null;
    };
    // Re-create network whenever the data identity changes.
  }, [nodes, edges]);

  return (
    <div
      ref={containerRef}
      style={{ height, width: "100%" }}
      className="rounded-lg border border-slate-200 bg-white"
    />
  );
}
