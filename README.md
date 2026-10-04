# NEXUS AI SWARM PLATFORM

Enterprise platform that **clones GitHub repositories, parses AST dependency
graphs, securely manages model API keys in an AES-256-GCM vault, and runs
self-healing multi-agent developer swarms** powered by NVIDIA Nemotron, the
Qwen family (DashScope / OpenRouter / vLLM), OpenAI, Anthropic and Google
Gemini — all through one OpenAI-compatible adaptive router.

| Layer | Technology |
| --- | --- |
| Backend | FastAPI · Pydantic v2 · SQLAlchemy 2.0 (async) · httpx |
| Async execution | asyncio task supervisor (single-process, in-memory event bus) |
| Security vault | `cryptography` AES-256-GCM · PBKDF2-HMAC-SHA256 / Argon2id KDF |
| Ingestion | GitPython (depth-aware clone/pull) · tree-sitter (+ regex fallback) |
| Frontend | React 18 · TypeScript (strict) · Tailwind CSS · Lucide icons |
| Realtime | Server-Sent Events (replay + live) · WebSocket mirror |
| Deployment | Docker multi-stage · non-root containers · docker-compose topology |

---

## 1 · Architecture Overview

```
┌─────────────────────────────── backend/app ───────────────────────────────┐
│                                                                           │
│  api/routes/            HTTP + SSE + WebSocket surface                    │
│      health · repositories · vault · providers · swarm                    │
│                                                                           │
│  services/                                                                │
│      git_ingestion   depth-aware clone/pull → binary filtration           │
│      secret_scanner  AWS/GitHub/NVAPI/private-key/… detection + redaction │
│      ast_parser      tree-sitter import graph (regex fallback per lang)   │
│      context_window  token-aware windowing, secret-bearing files blocked  │
│      kdf + vault     PBKDF2/Argon2 → AES-256-GCM seal/open                │
│      llm_client      OpenAI-compatible chat + streaming (httpx)           │
│      rate_limiter    sliding window + circuit breaker (closed/open/half)  │
│      provider_router adaptive failover · EWMA latency scoring · budgets   │
│      event_bus       bounded async pub/sub fan-out                        │
│                                                                           │
│  swarm/                                                                   │
│      agents/         PlannerAgent · ArchitectAgent · CoderAgent           │
│                      ReviewerAgent · PatcherAgent                         │
│      execution       sandboxed lint/test runner (timeout + scrubbed env)  │
│      diff_engine     unified git diff (incl. untracked files) + parser    │
│      orchestrator    pipeline supervisor + self-healing repair loop       │
│                                                                           │
│  db/                   SQLAlchemy models · DAO · async engine             │
└───────────────────────────────────────────────────────────────────────────┘
┌────────────────────────────── frontend/src ───────────────────────────────┐
│  views: Dashboard · Repositories · Vault · Swarm · Providers               │
│  swarm console: agent timeline · live token stream · event timeline       │
│                 · repair-loop panel · side-by-side diff viewer            │
└───────────────────────────────────────────────────────────────────────────┘
```

The full **end-to-end flow diagram** lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 2 · End-to-End Flow

`GitHub Ingestion → Key Vault & Provider Router → Swarm Orchestrator →
Self-Healing Loop → WebSocket / SSE / UI stream` — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#2-end-to-end-system-flow) for the
detailed ASCII diagram.

## 3 · Repository Layout

```
.
├── backend/                    FastAPI service (see backend/app/…)
│   ├── app/
│   │   ├── main.py             application factory + lifespan wiring
│   │   ├── core/               config · logging · error envelopes
│   │   ├── db/                 models · DAO · async session
│   │   ├── schemas/            Pydantic v2 API schemas
│   │   ├── api/                routes (health/repositories/vault/providers/swarm)
│   │   ├── services/           vault · router · ingestion · scanning · bus
│   │   ├── swarm/              orchestrator · agents · execution · diff
│   │   └── config/providers.json   provider catalog (reference schema)
│   ├── tests/                  87 tests incl. full self-healing E2E
│   ├── Dockerfile              multi-stage, non-root, healthcheck
│   └── requirements*.txt
├── frontend/                   React 18 + Tailwind + Lucide SPA
│   ├── src/…                   views · components · hooks · api client
│   ├── nginx.conf              SPA + /api + /ws reverse proxy
│   └── Dockerfile              node build → hardened nginx
├── docs/ARCHITECTURE.md        architecture + flow diagrams
├── docker-compose.yml          backend + frontend (+ postgres/redis profile)
├── .env.example                every configuration knob documented
└── Makefile                    install / dev / test / docker targets
```

## 4 · Codebase

Every file is complete, fully typed and syntax-verified:

- **Backend**: `mypy`-style annotations throughout, `ruff` clean, **87/87 tests
  passing** — including a full pipeline E2E (clone → agents → failing tests →
  PatcherAgent repair → green tests → diff) and a repair-budget-exhaustion E2E.
- **Frontend**: TypeScript `--strict` + `noUnusedLocals` clean, production
  Vite build passing.

## 5 · Deployment Assets

- `backend/Dockerfile` — multi-stage build, non-root `nexus` user, git + curl
  runtime, container healthcheck.
- `frontend/Dockerfile` — node build stage → nginx:alpine with SSE-aware
  (`proxy_buffering off`) reverse proxy and WebSocket upgrade.
- `docker-compose.yml` — hardened topology (`no-new-privileges`, healthcheck
  gating, named volumes) plus an `extended` profile with Postgres 16 + Redis 7.
- `.env.example` — every `NEXUS_*` setting with documentation.

## 6 · Setup & Operational Verification

### 6.1 Local development

```bash
# Backend (http://localhost:8000, docs at /api/docs)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp ../.env.example .env              # then set NEXUS_VAULT_MASTER_KEY
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (http://localhost:5173, proxies /api + /ws to :8000)
cd frontend
npm install
npm run dev
```

Or via make: `make install && make dev-backend` / `make dev-frontend`.

### 6.2 Verification commands

```bash
cd backend
.venv/bin/pytest -q          # 87 tests: crypto, scanner, parser, router, E2E swarm
.venv/bin/ruff check app tests
cd ../frontend
npm run build                # tsc --noEmit + vite build
```

### 6.3 Repository ingestion test

```bash
curl -X POST localhost:8000/api/repositories/ingest \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://github.com/octocat/Hello-World.git","depth":1}'
# → 202 {"id": "...", "status": "queued"}
curl localhost:8000/api/repositories/<id>          # status, languages, secrets, dep graph
curl -N localhost:8000/api/repositories/<id>/events   # live SSE ingestion progress
```

### 6.4 Dynamic provider key registration (Nemotron & Qwen)

```bash
# Unlock (or set NEXUS_VAULT_MASTER_KEY and it auto-unlocks at startup)
curl -X POST localhost:8000/api/vault/unlock \
  -H 'Content-Type: application/json' \
  -d '{"passphrase":"<master-passphrase>"}'

# Seal an NVIDIA Nemotron key (AES-256-GCM at rest)
curl -X POST localhost:8000/api/vault/keys \
  -H 'Content-Type: application/json' \
  -d '{"provider_id":"nvidia_nemotron","label":"NIM prod","api_key":"nvapi-…"}'

# Seal a Qwen DashScope key
curl -X POST localhost:8000/api/vault/keys \
  -H 'Content-Type: application/json' \
  -d '{"provider_id":"qwen_dashscope","label":"Qwen prod","api_key":"sk-…"}'

# Live credential verification (minimal routed completion)
curl -X POST localhost:8000/api/vault/keys/<key-id>/verify

# Router health: latency EWMA, circuits, rate-limit windows
curl localhost:8000/api/providers
```

### 6.5 Running a multi-agent job

```bash
curl -X POST localhost:8000/api/swarm/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "repository_id": "<repo-id>",
    "task": "Add a health check endpoint with unit tests",
    "preferred_model": "qwen-max",
    "max_repair_iterations": 3,
    "validation_enabled": true
  }'

curl -N localhost:8000/api/swarm/jobs/<job-id>/stream    # SSE: tokens, agents, repairs
curl localhost:8000/api/swarm/jobs/<job-id>/diff          # side-by-side diff payload
```

In the UI: **Repositories → ingest**, **Key Vault → register keys**,
**Swarm → launch**, then watch the agent timeline, live token stream,
repair-loop milestones and the final diff.

### 6.6 Docker Compose (production topology)

```bash
cp .env.example .env       # set NEXUS_VAULT_MASTER_KEY etc.
docker compose up -d --build
# UI      → http://localhost:3000
# API     → http://localhost:8000/api/docs
# Extended (Postgres + Redis): docker compose --profile extended up -d
```

### 6.7 Operational notes

- **Single worker**: the swarm supervisor and event bus are in-process by
  design — run `uvicorn --workers 1` (the default `Dockerfile` CMD) and scale
  horizontally with one swarm service per container.
- **Vault**: keys are sealed per record with a random salt + nonce and
  AAD-bound to the provider/record id. A lost passphrase makes sealed keys
  undecryptable (by design).
- **Validation sandbox**: lint/test commands run in the clone directory with a
  scrubbed environment and hard timeout (`NEXUS_EXECUTION_*` settings). Disable
  with `NEXUS_EXECUTION_ENABLED=false`.
- **Secrets in prompts**: files flagged by the secret scanner are excluded
  from every LLM context window.
