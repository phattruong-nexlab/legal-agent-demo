import { NextResponse } from "next/server";
import { pingNeo4j } from "@/lib/neo4j.server";
import { getStats, listAuthorities, listYears } from "@/lib/graph-queries";

export const dynamic = "force-dynamic";

// Sidebar bootstrap data: connection status + filter options + stats.
export async function GET() {
  const conn = await pingNeo4j();
  if (!conn.ok) {
    return NextResponse.json(
      { connected: false, error: conn.error, authorities: [], years: [], stats: {} },
      { status: 200 }
    );
  }
  const [authorities, years, stats] = await Promise.all([
    listAuthorities(),
    listYears(),
    getStats(),
  ]);
  return NextResponse.json({ connected: true, authorities, years, stats });
}
