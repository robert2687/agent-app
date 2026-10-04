# ═══════════════════════════════════════════════════════════════════════════
# NEXUS AI SWARM PLATFORM — Backend image (multi-stage, non-root, hardened)
# ═══════════════════════════════════════════════════════════════════════════

# ── Stage 1: dependency builder ────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN python -m pip install --prefix=/install --no-compile -r requirements.txt

# ── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# git        → GitPython clone/pull/diff engine
# curl       → container healthchecks
# libffi/gcc-runtime pieces are pulled in by cryptography wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user
RUN groupadd --system --gid 1001 nexus \
    && useradd --system --uid 1001 --gid nexus --create-home --shell /usr/sbin/nologin nexus

COPY --from=builder /install /usr/local
WORKDIR /opt/nexus
COPY --chown=nexus:nexus app ./app

RUN mkdir -p /data/workspace/repos \
    && chown -R nexus:nexus /data /opt/nexus
USER nexus

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
