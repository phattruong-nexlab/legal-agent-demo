import { NextRequest, NextResponse } from "next/server";
import { apiBase } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const maxDuration = 600; // long-running audit/ingest calls

function targetUrl(req: NextRequest, path: string[]): string {
  const qs = req.nextUrl.search || "";
  return `${apiBase()}/${path.join("/")}${qs}`;
}

async function forward(req: NextRequest, path: string[]): Promise<NextResponse> {
  const url = targetUrl(req, path);
  const method = req.method;

  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  const accept = req.headers.get("accept");
  if (accept) headers["accept"] = accept;

  const init: RequestInit = { method, headers };
  if (method !== "GET" && method !== "HEAD") {
    // Preserve raw body (multipart boundaries, JSON) exactly.
    init.body = Buffer.from(await req.arrayBuffer());
  }

  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e: any) {
    return NextResponse.json(
      { detail: `Không gọi được backend: ${e?.message || e}` },
      { status: 502 }
    );
  }

  const body = await res.arrayBuffer();
  const respHeaders = new Headers();
  const respCt = res.headers.get("content-type");
  if (respCt) respHeaders.set("content-type", respCt);
  return new NextResponse(body, { status: res.status, headers: respHeaders });
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  return forward(req, ctx.params.path);
}

export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  return forward(req, ctx.params.path);
}
