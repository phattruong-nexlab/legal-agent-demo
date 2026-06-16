import "server-only";

/** FastAPI base, mirrors _api_base() in the Streamlit app. */
export function apiBase(): string {
  const base = (process.env.BACKEND_URL || "http://localhost:8001").replace(/\/$/, "");
  return `${base}/api/v1`;
}
