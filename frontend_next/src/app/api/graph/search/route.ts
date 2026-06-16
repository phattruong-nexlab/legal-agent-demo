import { NextRequest, NextResponse } from "next/server";
import { searchFulltext } from "@/lib/graph-queries";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") || "";
  const hits = await searchFulltext(q, 25);
  return NextResponse.json({ hits });
}
