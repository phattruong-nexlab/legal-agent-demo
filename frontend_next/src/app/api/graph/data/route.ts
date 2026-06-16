import { NextRequest, NextResponse } from "next/server";
import { overviewGraph, docSubgraph, computeMatchedDocs } from "@/lib/graph-queries";
import { applyFilterDim } from "@/lib/graph-transform";

export const dynamic = "force-dynamic";

interface Body {
  selectedDocId: string | null;
  includeStructure: boolean;
  onlyReal: boolean;
  maxDocs: number;
  auth: string[];
  loai: string[];
  year: number[];
}

export async function POST(req: NextRequest) {
  const b = (await req.json()) as Body;
  const hasFilter = Boolean(b.auth?.length || b.loai?.length || b.year?.length);
  const matched = hasFilter
    ? await computeMatchedDocs(b.auth || [], b.loai || [], b.year || [])
    : null;

  const { nodes, edges } = b.selectedDocId
    ? await docSubgraph(b.selectedDocId, !!b.includeStructure)
    : await overviewGraph([], !!b.onlyReal, b.maxDocs || 60);

  const { nMatched, nTotal } = applyFilterDim(nodes, edges, matched);

  return NextResponse.json({ nodes, edges, nMatched, nTotal, hasFilter });
}
