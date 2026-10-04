# ═══════════════════════════════════════════════════════════════════════════
# NEXUS AI SWARM PLATFORM — Frontend image (multi-stage: build → nginx)
# ═══════════════════════════════════════════════════════════════════════════

# ── Stage 1: TypeScript check + production bundle ──────────────────────────
FROM node:22-alpine AS build

WORKDIR /build

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY tsconfig.json vite.config.ts tailwind.config.js postcss.config.js index.html ./
COPY src ./src

RUN npm run build

# ── Stage 2: hardened nginx runtime ────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/nexus.conf
COPY --from=build /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
    CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
