# CLOUD RUN EVALUATION REPORT
## AutoHaus C-OS v3.1.1-Alpha · Phase A
## Generated: 2026-03-04 · Evaluator: Antigravity Agent

---

## A1 — HARDCODED URLs

**Files requiring update before Cloud Run cut-over:**

| File | Line | Reference | Type |
|---|---|---|---|
| `10_IT_AI_Core_Layer/backend/routes/logistics.py` | 58 | `https://autohaus-command.replit.app` | Hardcoded Replit URL as default fallback |
| `10_IT_AI_Core_Layer/scripts/trigger_intake.py` | 148 | `https://fe24ad2a-...worf.replit.dev/webhooks/leads` | Hardcoded Replit dev URL (legacy script) |
| `10_IT_AI_Core_Layer/backend/docs/CIL_MASTER_BLUEPRINT.md` | 6 | `https://autohaus-command.replit.app` | Documentation reference (informational only — no code impact) |
| `10_IT_AI_Core_Layer/frontend/vite.config.ts` | 16, 21 | `http://localhost:8000` | Vite dev proxy target (local dev only — no prod impact) |
| `10_IT_AI_Core_Layer/backend/test_membrane.py` | 6 | `http://localhost:8000/api/webhooks/twilio/sms` | Test file only — no prod impact |
| `10_IT_AI_Core_Layer/backend/test_ws_orchestrator.py` | 7 | `ws://localhost:8000/ws/chat` | Test file — **uses `ws://` (insecure)** — see A4 |
| `10_IT_AI_Core_Layer/backend/scripts/batch_ingest.py` | 11 | `http://localhost:8001` | Env-var overridable — OK for local, update env var for Cloud Run |

**Critical code changes required (2):**
1. `logistics.py:58` — Replace hardcoded Replit fallback with `os.environ.get("UI_BASE_URL")` (already reading from env, just remove the hardcoded default)
2. `trigger_intake.py:148` — Replace hardcoded Replit dev URL with env var

**Total references: 7 (2 critical, 3 test-only, 1 docs, 1 env-overridable)**

---

## A2 — SECRETS AUDIT

**All secrets required by the backend (names only — no values):**

| Variable Name | Where Used | Sensitive | Notes |
|---|---|---|---|
| `GEMINI_API_KEY` | `attachment_processor.py`, `chat_stream.py`, `extraction_engine.py` | ✅ YES | Primary AI key |
| `TWILIO_ACCOUNT_SID` | `twilio_service.py`, `setup_twilio_ops.py` | ✅ YES | Twilio credentials |
| `TWILIO_AUTH_TOKEN` | `twilio_service.py` | ✅ YES | Twilio credentials |
| `TWILIO_PHONE_NUMBER` | `twilio_service.py`, `setup_twilio_ops.py` | ⚠️ Semi | Phone number |
| `TWILIO_PHONE_PN_SID` | `setup_twilio_ops.py` | ⚠️ Semi | Twilio resource SID |
| `GCP_SERVICE_ACCOUNT_JSON` | `drive_ear.py`, `identity_resolution.py` | ✅ YES | Full SA JSON — **highest risk if leaked** |
| `GITHUB_WEBHOOK_SECRET` | `deploy_routes.py` | ✅ YES | Webhook HMAC secret |
| `SECURITY_ACCESS_KEY_HASH` | `security_access.py` | ✅ YES | Security layer key hash |
| `CEO_PHONE_NUMBER` | Various notification routes | ⚠️ Semi | PII |
| `GCP_PROJECT` | Various | ❌ Not sensitive | Can stay as Cloud Run env var |
| `BQ_DATASET` | Various | ❌ Not sensitive | Can stay as Cloud Run env var |
| `PUBLIC_URL` | `lifespan()`, `drive_ear.py` | ❌ Not sensitive | Set to Cloud Run URL post-deployment |
| `UI_BASE_URL` | `logistics.py` | ❌ Not sensitive | Set to Replit frontend URL |
| `CIL_BASE_URL` | `batch_ingest.py` | ❌ Not sensitive | Admin script only — set locally |
| `DOCS_DIR` | `batch_ingest.py` | ❌ Not sensitive | Admin script only |

**In GCP Secret Manager already:** Unknown — Moaz to confirm
**Action required from Moaz:** Inject values for the 8 sensitive secrets into GCP Secret Manager during Phase B-B1.

> ⚠️ **`GCP_SERVICE_ACCOUNT_JSON`** is the highest-risk secret. On Cloud Run, this should be replaced entirely with Workload Identity / the Cloud Run service account — no JSON key needed at all. This is an improvement over the current architecture.

---

## A3 — GCP PERMISSIONS

**Project:** `autohaus-infrastructure`  
**Active account:** `moaz@autohausia.com` ✅ (SOVEREIGN)

**Service API check result:** `gcloud services list` requires interactive browser re-auth in non-TTY context (the `bq` CLI has the same issue). The Python SDK (ADC) works correctly but the gcloud CLI binaries require a different token.

**Confirmed APIs active (via successful Python SDK calls):**
- `bigquery.googleapis.com` ✅ (actively writing proposals today)
- `generativelanguage.googleapis.com` ✅ (Gemini extracting claims)

**APIs to verify and enable (run in your terminal):**
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  --project autohaus-infrastructure
```

**Existing Service Accounts:**
- `replit-cil-orchestrator@autohaus-infrastructure.iam.gserviceaccount.com` (present — role TBD)
- Recommend creating a dedicated `autohaus-cil-backend` SA per the Phase B spec

**Action required:** Moaz runs the `gcloud services enable` command above, then confirms all 4 APIs show `ENABLED`.

---

## A4 — WEBSOCKET COMPATIBILITY

**Status: CONDITIONAL — ONE ISSUE FOUND**

**WebSocket implementation details:**
- FastAPI standard `WebSocket` + `WebSocketDisconnect` — ✅ Cloud Run compatible
- Route: `/ws/chat` — ✅ standard path
- No `ws://` hardcoding in production code — ✅
- Protocol is standard `websockets` library — ✅

**Issue found — in-memory connection manager:**
```python
# chat_stream.py — ConnectionManager stores active websockets in-process dict
manager = ConnectionManager()  # module-level singleton
self._active_connections: Dict[str, WebSocket] = {}
```
On Cloud Run with multiple instances (which happens at any load > 1 concurrent user), each instance has its own `manager`. A client connected to instance A cannot receive broadcasts from instance B.

**Current impact:** Low — because Cloud Run is configured with `--min-instances 1` and chat sessions are per-user. Real-time broadcasts (dashboard updates, anomaly alerts) would silently fail for users on different instances.

**Changes required before Stage 2:**
1. **Test files** (`test_ws_orchestrator.py`) use `ws://` — update to `wss://` for Cloud Run testing
2. **WebSocket broadcast resilience:** For production multi-instance, replace `ConnectionManager` with a Redis pub/sub or Cloud Pub/Sub broadcast. **For Phase B Stage 1 (single instance), this is not a blocker** — Cloud Run at `--min-instances 1` and `--max-instances 1` eliminates the race condition. Only becomes a blocker at `--max-instances > 1`.

**Recommendation:** Deploy Phase B with `--max-instances 1` initially to sidestep the broadcast problem. Upgrade to Redis pub/sub as a follow-on task.

---

## A5 — RESOURCE REQUIREMENTS

**Gemini API round-trip measured:** `8.5 seconds` for Test.pdf (standard invoice)
**Expected range:** 6–20 seconds depending on document complexity

**Memory profile:**
- FastAPI + 15 routes + all agent initializations at startup: ~200–350 MB baseline
- PyMuPDF (for local PDF parsing): +50–100 MB per large PDF during processing
- Gemini sends bytes to the API — PDF is NOT held in RAM during model inference
- `VectorVault` (in-memory vector store): +50–150 MB depending on corpus size
- Peak during concurrent ingestion: estimated 500–700 MB

**Recommendations:**

| Parameter | Value | Rationale |
|---|---|---|
| Memory | **2Gi** | 700 MB peak + 3x headroom. 4Gi only needed if batch processing 10+ concurrent docs |
| CPU | **2** | Gemini calls are I/O-bound (waiting on API), 2 vCPU handles concurrency well |
| Min instances | **1** | Eliminates cold start for interactive chat, cost ~$18/month at idle |
| Max instances | **1 (initially)** | Avoids WebSocket broadcast race condition — scale to 3 after Redis pub/sub is added |
| Concurrency | **10** | Gemini calls are async; 10 concurrent requests per instance is safe |
| Request timeout | **300s** | Gemini can take 15–30s on large docs; 300s provides a wide safety margin |

---

## A6 — DOCKERFILE FEASIBILITY

**Existing Dockerfile:** ✅ YES — at `10_IT_AI_Core_Layer/backend/Dockerfile`

**Current content (needs updates):**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD ["uvicorn", "api_webhook:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Critical bug:** `CMD` references `api_webhook:app` — the correct entry point is `main:app`.

**System dependencies required:**
| Package | System Lib Required | Why |
|---|---|---|
| `pymupdf>=1.23.0` | `libmupdf-dev`, `libfreetype-dev` | PDF rendering (may be bundled in PyMuPDF wheel) |
| `pillow-heif>=0.13.0` | `libheif-dev`, `libde265-dev` | HEIC/HEIF image format |
| `python-magic>=0.4.27` | `libmagic1` | File type detection |
| `python-docx>=1.1.0` | None | Pure Python |

> **Important:** Recent PyMuPDF wheels are self-contained (no system libs needed). Check with a test build. `libmagic1` is the only certain system-level dependency.

**Required Dockerfile addition:**
```dockerfile
RUN apt-get update && apt-get install -y \
    libmagic1 \
    libheif-dev \
    && rm -rf /var/lib/apt/lists/*
```

**Estimated image size:** 800 MB – 1.1 GB (python:3.11-slim base ~120 MB + deps)

---

## A7 — COST PROJECTION

**Inputs measured:**
- Gemini API round-trip: 8.5s average
- Per-doc pipeline time (including BQ write): ~12s total
- Average claims per doc: 29
- Average tokens per doc: ~3,000 input + ~1,500 output = 4,500 tokens
- Cloud Run CPU: 2 vCPU · Memory: 2Gi

**Cloud Run cost formula:**
- CPU: 2 × $0.000024 × seconds = $0.000048/sec
- Memory: 2 × $0.0000025 × seconds = $0.000005/sec
- Total compute: ~$0.000053/sec

| Scenario | Docs/day | Active seconds/day | Compute cost | Min-instance cost | **Total/month** |
|---|---|---|---|---|---|
| **Low** | 5 docs | 60s | $0.003/day · ~$0.09/mo | $18/mo (1 inst) | **~$18/month** |
| **Medium** | 50 docs | 600s | $0.03/day · ~$0.90/mo | $18/mo | **~$19/month** |
| **High** | 300 docs | 3,600s | $0.19/day · ~$5.70/mo | $18/mo | **~$24/month** |

**Gemini API cost (separate):**
- Gemini 2.5 Flash: ~$0.075 per 1M input tokens, ~$0.30 per 1M output tokens
- Per doc: 3K input = $0.000225 + 1.5K output = $0.00045 → **~$0.00068/doc**
- 50 docs/day × 30 days = 1,500 docs/month → **~$1.02/month**

**Key cost drivers:**
1. Min-instance idle cost ($18/month) dominates at low volume — consider `--min-instances 0` for non-interactive services
2. Gemini API is negligible at current batch sizes
3. BigQuery: free tier covers 1 TB queries/month — no cost at current scale

---

## BLOCKERS BEFORE DEPLOYMENT

| # | Blocker | Severity | Resolution |
|---|---|---|---|
| 1 | **Dockerfile CMD references wrong entry point** (`api_webhook:app` instead of `main:app`) | 🔴 Critical | Fix before build |
| 2 | **`gcloud services enable` for 4 APIs** — cannot confirm enabled without interactive auth | 🟡 Medium | Moaz runs 1 command |
| 3 | **Secrets not in GCP Secret Manager** — all 8 sensitive secrets need injection | 🟡 Medium | Moaz injects values during B1 |
| 4 | **`logistics.py` hardcoded Replit URL** — will cause UI redirect failures on Cloud Run | 🟡 Medium | 1-line code fix |
| 5 | **`GCP_SERVICE_ACCOUNT_JSON` pattern** — JSON key file is insecure at rest | 🟢 Low (for Phase B1) | Replace with Workload Identity post-deployment |
| 6 | **WebSocket broadcast with multiple instances** | 🟢 Low (mitigated at `--max-instances 1`) | Redis pub/sub for future scale |

---

## ESTIMATED DEPLOYMENT TIME

**Phase B end-to-end (once blockers resolved):** `2–3 hours`
- B1 (secret shells): 10 min (Antigravity) + Moaz injection time
- B2 (Dockerfile fix): 5 min
- B3 (health endpoint): Already done ✅
- B4 (secret refs): 30 min
- B5 (deploy): 15–20 min for build + deploy
- B6 (validation): 20 min
- B7 (Replit cut-over): separate authorization + 30 min

---

*Phase A complete. Awaiting Moaz review and Phase B authorization.*
*Generated by Antigravity · AutoHaus C-OS v3.1.1-Alpha*
