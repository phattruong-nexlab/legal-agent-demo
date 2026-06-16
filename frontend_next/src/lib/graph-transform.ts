import "server-only";
import neo4j, { Record as Neo4jRecord } from "neo4j-driver";
import { LABEL_COLOR, REL_COLOR } from "./constants";
import type { GraphNode, GraphEdge } from "./types";
import { toPlain } from "./neo4j.server";

const KIND_ORDER = [
  "Document",
  "Chapter",
  "Article",
  "Clause",
  "Point",
  "Authority",
  "DocumentType",
] as const;

function kindOf(labels: string[]): string {
  for (const k of KIND_ORDER) if (labels.includes(k)) return k;
  return "Unknown";
}

function nodeLabel(labels: string[], props: Record<string, any>): string {
  const kind = kindOf(labels);
  switch (kind) {
    case "Document":
      return props["tên_ngắn"] || props["số_hiệu"] || props["id"] || "?";
    case "Article":
      return `Điều ${props["số"] ?? "?"}`;
    case "Clause":
      return `Khoản ${props["số"] ?? "?"}`;
    case "Point":
      return `Điểm ${props["ký_hiệu"] ?? "?"}`;
    case "Chapter":
      return `Chương ${props["số"] ?? "?"}`;
    case "Authority":
      return props["tên"] || "?";
    case "DocumentType":
      return props["tên"] || props["code"] || "?";
    default:
      return "?";
  }
}

function nodeColor(labels: string[], props: Record<string, any>): string {
  const kind = kindOf(labels);
  if (kind === "Document" && props["trạng_thái"] === "PLACEHOLDER") {
    return LABEL_COLOR._Placeholder;
  }
  return LABEL_COLOR[kind] || "#7F8C8D";
}

function nodeSize(labels: string[]): number {
  const kind = kindOf(labels);
  const sizes: Record<string, number> = {
    Document: 28,
    Chapter: 22,
    Article: 16,
    Clause: 12,
    Point: 8,
    Authority: 24,
    DocumentType: 20,
  };
  return sizes[kind] ?? 10;
}

function agId(labels: string[], props: Record<string, any>): string {
  const kind = kindOf(labels);
  if (["Document", "Chapter", "Article", "Clause", "Point"].includes(kind)) {
    return `${kind}::${props["id"] ?? ""}`;
  }
  if (kind === "Authority") return `Authority::${props["tên"] ?? ""}`;
  if (kind === "DocumentType") return `DocumentType::${props["code"] ?? ""}`;
  return `Unknown::${props["id"] ?? Math.random()}`;
}

function tooltip(labels: string[], props: Record<string, any>): string {
  const lines = [`<b>:${labels.join(" :")}</b>`];
  for (const [k, v] of Object.entries(props)) {
    if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) {
      continue;
    }
    let s = String(v);
    if (s.length > 250) s = s.slice(0, 250) + "…";
    lines.push(`<i>${k}</i>: ${s}`);
  }
  return lines.join("<br>");
}

/**
 * Collect GraphNode/GraphEdge from raw neo4j records.
 * Two passes: nodes first (the JS driver's relationships don't carry node
 * objects, so we map element ids -> agraph ids), then relationships.
 */
export function collect(records: Neo4jRecord[]): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes = new Map<string, GraphNode>();
  const elementToAg = new Map<string, string>();
  const edgesSeen = new Set<string>();
  const edges: GraphEdge[] = [];

  const addNode = (val: any) => {
    if (!val || !neo4j.isNode(val)) return;
    const labels = val.labels as string[];
    const props = toPlain(val);
    const nid = agId(labels, props);
    elementToAg.set(val.elementId, nid);
    if (!nodes.has(nid)) {
      nodes.set(nid, {
        id: nid,
        label: nodeLabel(labels, props),
        size: nodeSize(labels),
        color: nodeColor(labels, props),
        title: tooltip(labels, props),
      });
    }
  };

  const addRel = (val: any) => {
    if (!val || !neo4j.isRelationship(val)) return;
    const sId = elementToAg.get(val.startNodeElementId);
    const eId = elementToAg.get(val.endNodeElementId);
    if (!sId || !eId) return;
    const key = `${sId}|${eId}|${val.type}`;
    if (edgesSeen.has(key)) return;
    edgesSeen.add(key);
    edges.push({
      from: sId,
      to: eId,
      label: "",
      title: val.type,
      color: REL_COLOR[val.type] || "#999",
      width: 2.5,
    });
  };

  const eachValue = (rec: Neo4jRecord, fn: (v: any) => void) => {
    for (const key of rec.keys) {
      const val = rec.get(key as string);
      if (Array.isArray(val)) val.forEach(fn);
      else fn(val);
    }
  };

  for (const rec of records) eachValue(rec, addNode);
  for (const rec of records) eachValue(rec, addRel);

  return { nodes: Array.from(nodes.values()), edges };
}

// ---------------------------------------------------------------------------
// Filter dimming — "focus + context" visualization
// ---------------------------------------------------------------------------

function dim(hex: string, factor = 0.22): string {
  const h = (hex || "").replace(/^#/, "");
  if (h.length !== 6) return "#E0E4E8";
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  if ([r, g, b].some(Number.isNaN)) return "#E0E4E8";
  const blend = (c: number) => Math.round(c * factor + 255 * (1 - factor));
  const hx = (c: number) => blend(c).toString(16).padStart(2, "0").toUpperCase();
  return `#${hx(r)}${hx(g)}${hx(b)}`;
}

function docIdOfAgNode(agNodeId: string): string | null {
  if (agNodeId.startsWith("Document::")) {
    return agNodeId.split("::", 2)[1] || null;
  }
  for (const prefix of ["Article::", "Clause::", "Point::", "Chapter::"]) {
    if (agNodeId.startsWith(prefix)) {
      const path = agNodeId.slice(prefix.length);
      return path.includes("#") ? path.split("#")[0] : null;
    }
  }
  return null;
}

export function applyFilterDim(
  nodes: GraphNode[],
  edges: GraphEdge[],
  matchedDocIds: Set<string> | null
): { nMatched: number; nTotal: number } {
  const docCount = nodes.filter((n) => n.id.startsWith("Document::")).length;
  if (matchedDocIds === null) return { nMatched: docCount, nTotal: docCount };

  const dimmed = new Set<string>();
  let matched = 0;
  for (const n of nodes) {
    const docId = docIdOfAgNode(n.id);
    if (docId === null) continue; // Authority / DocumentType — always bright
    if (matchedDocIds.has(docId)) {
      if (n.id.startsWith("Document::")) matched++;
      continue;
    }
    n.color = dim(n.color);
    dimmed.add(n.id);
  }
  for (const e of edges) {
    if (dimmed.has(e.from) || dimmed.has(e.to)) {
      e.color = dim(e.color, 0.18);
    }
  }
  return { nMatched: matched, nTotal: docCount };
}

export { REL_COLOR };
