// Client-side fetch helpers. Graph data comes from our own /api/graph/*
// route handlers (which talk to Neo4j server-side); backend-driven features
// go through the /api/backend/* proxy to FastAPI.

async function jsonOrThrow(res: Response) {
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail =
      (data && typeof data === "object" && (data.detail || data.error)) ||
      (typeof data === "string" ? data : "") ||
      `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

// ---- Graph (Neo4j via our route handlers) ----
export async function fetchGraphMeta() {
  return jsonOrThrow(await fetch("/api/graph/meta", { cache: "no-store" }));
}

export interface GraphDataParams {
  selectedDocId: string | null;
  includeStructure: boolean;
  onlyReal: boolean;
  maxDocs: number;
  auth: string[];
  loai: string[];
  year: number[];
}

export async function fetchGraphData(p: GraphDataParams) {
  return jsonOrThrow(
    await fetch("/api/graph/data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p),
      cache: "no-store",
    })
  );
}

export async function fetchSearch(q: string) {
  return jsonOrThrow(
    await fetch(`/api/graph/search?q=${encodeURIComponent(q)}`, { cache: "no-store" })
  );
}

export async function fetchDocuments(loai: string[], onlyReal: boolean) {
  const params = new URLSearchParams();
  if (loai.length) params.set("loai", loai.join(","));
  if (onlyReal) params.set("onlyReal", "1");
  return jsonOrThrow(
    await fetch(`/api/graph/documents?${params.toString()}`, { cache: "no-store" })
  );
}

export async function fetchDocDetails(id: string) {
  return jsonOrThrow(
    await fetch(`/api/graph/doc-details?id=${encodeURIComponent(id)}`, { cache: "no-store" })
  );
}

// ---- Backend proxy ----
function backendUrl(path: string) {
  return `/api/backend/${path.replace(/^\//, "")}`;
}

export async function backendPostForm(path: string, form: FormData) {
  return jsonOrThrow(await fetch(backendUrl(path), { method: "POST", body: form }));
}

export async function backendPostJson(path: string, body: unknown) {
  return jsonOrThrow(
    await fetch(backendUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}
