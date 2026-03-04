# AutoHaus CIL — Phase 4 Cloud Run Deployment Spec

**Status:** PENDING AUTHORIZATION  
**Author:** Antigravity Agent  
**Date:** 2026-03-04  
**Authorized by:** Moaz Sial (required before any step below is executed)

---

## Architecture Decision

Replit is **UI-only**. The FastAPI CIL backend must run on a persistent, scalable, authenticated compute layer.  
**Chosen target:** Google Cloud Run (serverless containers, scales-to-zero, native GCP IAM).

---

## Prerequisites (one-time setup, already available)

| Item | Status |
|---|---|
| GCP Project | `autohaus-infrastructure` ✅ |
| BigQuery dataset | `autohaus_cil` ✅ |
| Gemini API key | `GEMINI_API_KEY` env var ✅ |
| Service Account | To be created (see Step 2) |
| Docker image | To be built (see Step 3) |
| Cloud Run service | To be deployed (see Step 5) |

---

## Step 1 — Enable Required GCP APIs

```bash
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project autohaus-infrastructure
```

---

## Step 2 — Create Dedicated Service Account

```bash
# Create the service account
gcloud iam service-accounts create autohaus-cil-backend \
  --display-name="AutoHaus CIL Backend" \
  --project autohaus-infrastructure

# Grant BigQuery access
gcloud projects add-iam-policy-binding autohaus-infrastructure \
  --member="serviceAccount:autohaus-cil-backend@autohaus-infrastructure.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding autohaus-infrastructure \
  --member="serviceAccount:autohaus-cil-backend@autohaus-infrastructure.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# Grant Secret Manager access (for future secrets rotation)
gcloud projects add-iam-policy-binding autohaus-infrastructure \
  --member="serviceAccount:autohaus-cil-backend@autohaus-infrastructure.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Step 3 — Create Artifact Registry Repository

```bash
gcloud artifacts repositories create autohaus-cil \
  --repository-format=docker \
  --location=us-central1 \
  --description="AutoHaus CIL Backend Images" \
  --project autohaus-infrastructure
```

---

## Step 4 — Build & Push Docker Image

The existing `Dockerfile` in `10_IT_AI_Core_Layer/backend/` is the build context.

```bash
cd 10_IT_AI_Core_Layer/backend

# Configure Docker auth for Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push
gcloud builds submit . \
  --tag us-central1-docker.pkg.dev/autohaus-infrastructure/autohaus-cil/backend:latest \
  --project autohaus-infrastructure
```

> **Note:** Verify the Dockerfile's CMD is `uvicorn main:app --host 0.0.0.0 --port 8080`.  
> Cloud Run always expects port **8080**. Currently `main.py` defaults to 8000 — update before build:

```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## Step 5 — Deploy to Cloud Run

```bash
gcloud run deploy autohaus-cil-backend \
  --image us-central1-docker.pkg.dev/autohaus-infrastructure/autohaus-cil/backend:latest \
  --platform managed \
  --region us-central1 \
  --service-account autohaus-cil-backend@autohaus-infrastructure.iam.gserviceaccount.com \
  --set-env-vars "GEMINI_API_KEY=<value>,PUBLIC_URL=<cloud-run-url>" \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 20 \
  --min-instances 0 \
  --max-instances 5 \
  --no-allow-unauthenticated \
  --project autohaus-infrastructure
```

> **Security Note:** `--no-allow-unauthenticated` means only callers with `roles/run.invoker` can call the backend.  
> `batch_ingest.py` will need an `Authorization: Bearer $(gcloud auth print-identity-token)` header, or a service-account token.

---

## Step 6 — Point batch_ingest.py at Cloud Run

Once deployed, Cloud Run will provide a URL like:  
`https://autohaus-cil-backend-<hash>-uc.a.run.app`

Update `batch_ingest.py` by setting the `CIL_BASE_URL` env var before running:

```bash
export CIL_BASE_URL="https://autohaus-cil-backend-<hash>-uc.a.run.app"
python3 10_IT_AI_Core_Layer/backend/scripts/batch_ingest.py
```

Or permanently in `.env`:
```
CIL_BASE_URL=https://autohaus-cil-backend-<hash>-uc.a.run.app
```

---

## Step 7 — (Optional) Custom Domain

```bash
gcloud run domain-mappings create \
  --service autohaus-cil-backend \
  --domain api.autohausia.com \
  --region us-central1 \
  --project autohaus-infrastructure
```

---

## Current State (Local Dev)

| Item | Value |
|---|---|
| Local server | `http://127.0.0.1:8001` (running) |
| Process | PID tracked in background |
| Start command | `cd 10_IT_AI_Core_Layer/backend && python3 -m uvicorn main:app --host 127.0.0.1 --port 8001` |
| `batch_ingest.py` default | `http://localhost:8001` |
| Port 5000 | ❌ Blocked by macOS AirPlay/Control Center |
| BigQuery | ⚠️ Needs `gcloud auth application-default login` re-auth |

---

## ⚠️ Deployment Authorization Required

**Do not execute Step 4 or Step 5 until Moaz gives explicit authorization.**  
When ready, confirm with: *"Authorize Phase 4 Cloud Run deployment."*
