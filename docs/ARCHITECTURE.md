# NEXUS AI SWARM PLATFORM — System Architecture

## 1 · Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PRESENTATION — React 18 + Tailwind CSS + Lucide (frontend/src)              │
│   Dashboard │ Repositories │ Key Vault │ Swarm Console │ Providers          │
│   Agent timeline · live token stream (SSE) · repair-loop panel              │
│   Side-by-side diff viewer · provider health table                          │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │ REST (/api) + SSE (/stream) + WebSocket (/ws)
┌───────────────▼─────────────────────────────────────────────────────────────┐
│ API SURFACE — FastAPI + Pydantic v2 (backend/app/api)                       │
│   /api/health /ready /stats      liveness · readiness · dashboard counters  │
│   /api/repositories…             ingest (202 async) · list · detail · SSE   │
│   /api/vault…                    unlock/lock · key CRUD · rotate · verify   │
│   /api/providers…                catalog+health · usage · routed chat       │
│   /api/swarm…                    launch · inspect · cancel · SSE · WS · diff│
└───────────────┬─────────────────────────────────────────────────────────────┘
                │ Container (app.state.container)
┌───────────────▼─────────────────────────────────────────────────────────────┐
│ DOMAIN SERVICES (backend/app/services)                                      │
│  GitIngestionService   depth-aware clone/pull (threadpool) · size limits    │
│  SecretScanner         11 rule families, redacted previews only             │
│  AstParser             tree-sitter import graphs · regex fallback/lang      │
│  ContextWindowBuilder  ~4 chars/token packing · BFS over dep graph          │
│  KeyVault + KDF        PBKDF2-HMAC-SHA256 (100k iters) / Argon2id           │
│                        → AES-256-GCM seal/open (per-record salt+nonce+AAD)  │
│  ProviderRouter        candidate selection → failover chain → budgets       │
│  SlidingWindow + CircuitBreaker   rate limiting · failure isolation         │
│  OpenAICompatibleClient  chat + SSE streaming for every endpoint            │
│  EventBus              bounded drop-oldest pub/sub (SSE/WS fan-out)         │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────────────────┐
│ SWARM ORCHESTRATION (backend/app/swarm)                                     │
│  SwarmOrchestrator   supervised asyncio pipeline per job                    │
│  Agents: Planner → Architect → Coder → Reviewer → (Validator → Patcher)ⁿ    │
│  CommandRunner       scrubbed-env, timeout-capped lint/test execution       │
│  DiffEngine          git diff HEAD (intent-to-add for new files) + parser   │
└───────────────┬─────────────────────────────────────────────────────────────┘
                │ SQLAlchemy 2.0 async (SQLite default · Postgres ready)
┌───────────────▼─────────────────────────────────────────────────────────────┐
│ PERSISTENCE — repositories · provider_keys · swarm_jobs · swarm_events      │
│               usage_records (per-request latency/token telemetry)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2 · End-to-End System Flow

```
                 ┌──────────────────────────┐
   GitHub URL    │   GITHUB INGESTION       │  GitPython clone --depth=N
 ──────────────►│   ENGINE (async,thread)  │  or fetch+reset (pull)
                 └───────────┬──────────────┘  binary & vendored filtration
                             │
              ┌──────────────┼───────────────────┬─────────────────────┐
              ▼              ▼                   ▼                     │
     ┌────────────────┐ ┌──────────────┐ ┌───────────────────┐         │
     │ SECRET SCANNER │ │ AST PARSER   │ │ LANGUAGE/LOC CENSUS│        │
     │ 11 rule families│ │ tree-sitter │ │ py/ts/go/rs/rb/java│        │
     │ redacted only  │ │ import graph│ └───────────────────┘         │
     └───────┬────────┘ └──────┬───────┘                               │
             │                 │                                       │
             │  blocked files  ▼                                       │
             │        ┌──────────────────────┐                         │
             └───────►│ TOKEN-AWARE CONTEXT  │  entry points → plan    │
                      │ WINDOWING           │  refs → 1-hop BFS        │
                      │ (≤24k tok/window)   │  ~4 chars/token          │
                      └──────────┬───────────┘                         │
                                 │                                     │
   ┌─────────────────────────────▼─────────────────────────────────────▼───┐
   │                     SWARM ORCHESTRATOR (per job)                       │
   │                                                                        │
   │  ┌──────────┐   ┌────────────┐   ┌──────────┐   ┌───────────┐         │
   │  │ PLANNER  │──►│ ARCHITECT  │──►│  CODER   │──►│ REVIEWER  │         │
   │  │ steps+   │   │ modules+   │   │ complete │   │ verdict + │         │
   │  │ files    │   │ interfaces │   │ file     │   │ findings  │         │
   │  └──────────┘   └────────────┘   │ edits    │   └─────┬─────┘         │
   │                                  └────┬─────┘         │               │
   │                                       ▼               ▼               │
   │                              [safe path-traversal-   blocking findings │
   │                               checked write to        route to loop    │
   │                               repo worktree]              │           │
   │                                       │                   │           │
   │                                       ▼                   ▼           │
   │                              ┌────────────────────────────────┐       │
   │        │                      │  VALIDATOR (sandboxed)        │       │
   │        │                      │  lint (ruff) + tests (pytest) │       │
   │        │                      │  timeout · scrubbed env       │       │
   │        │                      └───────────┬───────────────────┘       │
   │        │                                  │ pass?                     │
   │        │                       no ◄───────┴────────► yes ─────────┐   │
   │        ▼                                            │              │   │
   │  ┌─────────────┐   failure context (stderr excerpts, │              │   │
   │  │  PATCHER    │◄── failing files, current code)     │              │   │
   │  │ AGENT       │    ── up to N repair iterations ────┼──► diff     │   │
   │  └──────┬──────┘                                    │              │   │
   │         │ apply fixes → re-validate (loop)           ▼              │   │
   │         └────────────────────────────►  [budget exhausted → FAILED]│   │
   │                                                                       │   │
   │   Every stage ──► EventBus ──► SSE / WebSocket ──► UI                │   │
   └───────────────────────────────────────────────────────────────────────┘   │
                                                                                │
   ┌───────────────────────────────────────────────────────────────────────┐   │
   │              KEY VAULT & AI MODEL PROVIDER ROUTER                     │◄──┘
   │                                                                       │
   │   master passphrase ─► KDF (PBKDF2 100k / Argon2id) ─► AES-256-GCM   │
   │   per key record: random salt + nonce + AAD(provider:record)         │
   │                                                                       │
   │   chat/stream request ─► candidate selection:                        │
   │     1. model support? 2. key active? 3. circuit closed?              │
   │     4. order: preference → priority → score(EWMA latency × pressure) │
   │   attempt chain with adaptive failover:                              │
   │     429 → rate-limit cooldown · 401/403 → key invalid · 5xx → next   │
   │   per-job token budget enforced before every call                    │
   │                                                                       │
   │   ┌───────────────┐ ┌───────────────┐ ┌───────────────┐               │
   │   │ NVIDIA NIM    │ │ DashScope     │ │ OpenRouter    │               │
   │   │ nemotron-4-   │ │ qwen-max ·    │ │ qwen-2.5-     │               │
   │   │ 340b-instruct │ │ qwen2.5-coder │ │ coder-32b     │               │
   │   └───────────────┘ └───────────────┘ └───────────────┘               │
   │   (+ OpenAI · Anthropic · Gemini OpenAI-compatible endpoints)         │
   └───────────────────────────────────────────────────────────────────────┘
```

## 3 · Self-Healing Loop Detail

```
                    ┌─────────────────────────────────────────┐
                    │              CODER EDITS                │
                    └───────────────────┬─────────────────────┘
                                        ▼
                              ┌───────────────────┐
                              │  lint (ruff)      │
                              │  tests (pytest)   │
                              └─────────┬─────────┘
                          pass           │           fail
                    ┌────────────────────┴─────────────────────┐
                    ▼                                          ▼
              ┌──────────┐        repair_iteration < N?   ┌─────────┐
              │ DONE     │                │ yes            │ PATCHER │
              │ (green)  │                ▼                │  AGENT  │
              └──────────┘        ┌──────────────┐         └────┬────┘
                                  │  increment   │              │
                                  │  iteration   │◄─────────────┘
                                  └──────┬───────┘  corrective edits
                                         │          (full-file contents)
                                         ▼
                                   re-validate ──► loop (max N)
                                          │
                                    N exhausted
                                          ▼
                                   ┌────────────┐
                                   │ JOB FAILED │  (validation artifact kept)
                                   └────────────┘
```

## 4 · Realtime Streaming Contract

| Event | Topic | Persisted | Payload highlights |
| --- | --- | --- | --- |
| `repo.update` / `repo.completed` / `repo.failed` | `repo:{id}` | bus only | status, counts |
| `job.update` | `job:{id}` | ✔ | status, current_agent |
| `context.built` | `job:{id}` | ✔ | windows, files, estimated tokens, blocked files |
| `agent.start` | `job:{id}` | ✔ | agent, description |
| `agent.token` | `job:{id}` | bus only (hot path) | agent, delta |
| `agent.complete` | `job:{id}` | ✔ | artifact digest |
| `edits.applied` | `job:{id}` | ✔ | files, count, summary |
| `validation.result` | `job:{id}` | ✔ | passed, lint/tests ok, excerpts |
| `repair.loop` | `job:{id}` | ✔ | trigger, iteration, failing files |
| `job.diff` | `job:{id}` | ✔ | files, additions, deletions |
| `job.completed` / `job.failed` / `job.cancelled` | `job:{id}` | ✔ | terminal state |

SSE streams replay the persisted backlog first (honouring `Last-Event-ID`
semantics via the `id:` field), then follow the live bus; terminal frames close
the stream. A WebSocket mirror is available at
`/api/swarm/jobs/{id}/ws` for bidirectional clients.

## 5 · Security Model

1. **At rest**: provider keys sealed with AES-256-GCM under a key derived from
   the master passphrase (PBKDF2-HMAC-SHA256 ≥100k iterations, or Argon2id).
   Each record carries a unique salt + nonce and AAD binding
   (`provider_id:record_id`) — ciphertexts cannot be transplanted.
2. **In memory**: the derived key lives only while the vault is unlocked;
   `lock()` zeroizes it. Verification of a re-unlock uses a sealed constant.
3. **In transit**: TLS terminates at your ingress; the router sends Bearer (or
   `x-api-key` + `anthropic-version` for Anthropic) credentials only to the
   configured provider base URLs.
4. **To models**: secret-scanner-flagged files are excluded from every context
   window; the validator subprocess runs with a scrubbed environment and
   hard timeout; file edits are path-traversal checked (`resolve()` +
   `is_relative_to`).
5. **Containers**: multi-stage builds, non-root users, `no-new-privileges`,
   healthchecks, and no secrets baked into images.
