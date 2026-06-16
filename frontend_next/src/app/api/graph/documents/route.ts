import { NextRequest, NextResponse } from "next/server";
import { listDocuments } from "@/lib/graph-queries";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const loai = (sp.get("loai") || "").split(",").filter(Boolean);
  const onlyReal = sp.get("onlyReal") === "1";
  const docs = await listDocuments(loai, onlyReal, 300);
  return NextResponse.json({ docs });
}
