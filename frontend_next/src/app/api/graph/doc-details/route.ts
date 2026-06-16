import { NextRequest, NextResponse } from "next/server";
import { fetchDocDetails } from "@/lib/graph-queries";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  if (!id) return NextResponse.json({ details: null });
  const details = await fetchDocDetails(id);
  return NextResponse.json({ details });
}
