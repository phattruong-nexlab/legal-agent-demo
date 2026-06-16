# Legal Knowledge Graph — Next.js frontend

A Next.js (App Router + TypeScript + Tailwind) port of the Streamlit UI in
`../frontend/main.py`. Feature parity:

| Page | Route | Source (Streamlit) |
| --- | --- | --- |
| Knowledge Graph Explorer | `/graph` | `render_graph_page` |
| Nạp tài liệu (Ingest) | `/ingest` | `render_ingest_page` |
| Audit tuân thủ | `/audit` | `render_audit_page` |
| Hỏi đáp Graph (hidden in nav) | `/query` | `render_query_page` |

## Architecture

- **Graph pages** talk to **Neo4j Aura directly from the server** via
  `neo4j-driver`, inside Next.js route handlers under `src/app/api/graph/*`.
  The Cypher, node/edge colouring and the "focus + context" filter-dimming were
  ported 1:1 from the Streamlit app (`src/lib/graph-*.ts`). Credentials never
  reach the browser.
- **Ingest / Audit / Query** post to the FastAPI backend through a thin proxy at
  `src/app/api/backend/[...path]/route.ts`, so the browser only ever calls the
  Next server (no CORS, no exposed backend URL).
- Graph visualization uses **vis-network** (same engine as `streamlit-agraph`).

## Setup

```bash
cd frontend_next
cp .env.local.example .env.local   # fill in Neo4j + BACKEND_URL
npm install
npm run dev                        # http://localhost:3000
```

### Environment (`.env.local`)

| Var | Purpose |
| --- | --- |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | Neo4j Aura, server-side only |
| `BACKEND_URL` | FastAPI base (default `http://localhost:8001`) |

These mirror the variables the Streamlit app reads from the repo-root `.env`.

## Build

```bash
npm run build
npm start
```
