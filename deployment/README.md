# CI/CD — GitHub Actions → Artifact Registry → Cloud Run

Workflow: [`.github/workflows/legal-agent-demo.yaml`](../.github/workflows/legal-agent-demo.yaml)

Triggers on push to **`develop`** (and manual `workflow_dispatch`). It builds two images,
pushes them to Google Artifact Registry, then deploys two Cloud Run services:

Both images live in a **single** Artifact Registry repo (`legal-agent-demo-ar-ase1`),
distinguished by image name (the Cloud Run service name).

| Service  | Dockerfile                       | Cloud Run service                    | Image (repo / name)                                   |
| -------- | -------------------------------- | ------------------------------------ | ----------------------------------------------------- |
| Backend  | `deployment/Dockerfile`          | `legal-agent-demo-cr-backend-ase1`   | `legal-agent-demo-ar-ase1/legal-agent-demo-cr-backend-ase1`  |
| Frontend | `deployment/Dockerfile.frontend` | `legal-agent-demo-cr-frontend-ase1`  | `legal-agent-demo-ar-ase1/legal-agent-demo-cr-frontend-ase1` |

The frontend is deployed **after** the backend and receives the backend's Cloud Run URL
via the `BACKEND_URL` env var automatically.

Region: `asia-southeast1`.

---

## 1. Required GitHub repository secrets

Settings → Secrets and variables → Actions → **New repository secret**:

| Secret                | Used for                                                        |
| --------------------- | --------------------------------------------------------------- |
| `GCP_PROJECT_ID`      | GCP project id                                                  |
| `GCP_PROJECT_NUMBER`  | GCP project number (for the Workload Identity provider path)    |
| `GEMINI_API_KEY`      | Gemini API key                                                  |
| `GEMINI_MODEL`        | Gemini model name → injected as `GEMINI_MODEL_NAME` in the app  |
| `LEGAL_BUCKET`        | GCS bucket for legal docs                                       |
| `NEO4J_URI`           | Neo4j / Aura connection URI                                     |
| `NEO4J_USERNAME`      | Neo4j username                                                  |
| `NEO4J_PASSWORD`      | Neo4j password                                                  |
| `NEO4J_DATABASE`      | Neo4j database name                                             |

> Note: the app reads `GEMINI_MODEL_NAME`, so the workflow maps the `GEMINI_MODEL`
> secret to the `GEMINI_MODEL_NAME` env var on the container.

---

## 2. One-time GCP setup

Run once (replace `PROJECT_ID` / `PROJECT_NUMBER`):

```bash
export PROJECT_ID=your-project-id
export REGION=asia-southeast1
export SA=sa-legal-agent-dev@${PROJECT_ID}.iam.gserviceaccount.com
export GITHUB_REPO=ORG/REPO   # e.g. nexlab/legal-agent-demo

# --- Enable APIs ---
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  iamcredentials.googleapis.com --project "$PROJECT_ID"

# --- Artifact Registry repo (single repo, shared by backend + frontend) ---
gcloud artifacts repositories create legal-agent-demo-ar-ase1 \
  --repository-format=docker --location=$REGION --project "$PROJECT_ID"

# --- Deployer service account + roles ---
gcloud iam service-accounts create sa-legal-agent-dev --project "$PROJECT_ID"
for ROLE in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA}" --role="$ROLE"
done

# --- Workload Identity Federation (keyless GitHub auth) ---
gcloud iam workload-identity-pools create legal-agent-dev-wip-github-glb \
  --location=global --project "$PROJECT_ID"

gcloud iam workload-identity-pools providers create-oidc legal-agent-dev-wipr-github-glb \
  --location=global --project "$PROJECT_ID" \
  --workload-identity-pool=legal-agent-dev-wip-github-glb \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'"

# --- Let the GitHub repo impersonate the SA ---
export POOL_ID=$(gcloud iam workload-identity-pools describe legal-agent-dev-wip-github-glb \
  --location=global --project "$PROJECT_ID" --format='value(name)')
gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT_ID" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
```

The app's own runtime service account (`$SA`) also needs the roles your app uses at
runtime — e.g. `roles/bigquery.user`, `roles/storage.objectViewer` /
`roles/storage.objectAdmin` on the bucket, and Vertex AI access if applicable.

---

## 3. Local development

```bash
# Backend + frontend, env baked from .env + gcp_credentials.json (backend)
docker compose -f deployment/docker-compose-local.yaml up --build

# Or the production-style images (env via .env at runtime)
docker compose -f deployment/docker-compose.yaml up --build
```

- Backend → http://localhost:8000  (health: `/api/v1/health`)
- Frontend → http://localhost:8501
