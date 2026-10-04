/** Typed API client for the Nexus backend (all requests are relative). */

import type {
  DashboardStats,
  DiffSummary,
  ProviderCatalog,
  ProviderKey,
  RepositoryDetail,
  RepositorySummary,
  SwarmEvent,
  SwarmJob,
  SwarmJobDetail,
  UsageSummary,
  VaultStatus,
} from "@/types";

const BASE = import.meta.env.VITE_NEXUS_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    let code = "http_error";
    let message = response.statusText;
    let details: Record<string, unknown> | undefined;
    try {
      const body = (await response.json()) as {
        error?: string;
        message?: string;
        details?: Record<string, unknown>;
      };
      code = body.error ?? code;
      message = body.message ?? message;
      details = body.details;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, code, message, details);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  // ── Health ──────────────────────────────────────────────────────────────
  health: () => request<{ status: string; version: string }>("/health"),
  ready: () =>
    request<{
      status: string;
      database: string;
      providers_registered: number;
      vault: string;
      environment: string;
    }>("/ready"),

  // ── Repositories ────────────────────────────────────────────────────────
  listRepositories: () => request<RepositorySummary[]>("/repositories"),
  getRepository: (id: string) => request<RepositoryDetail>(`/repositories/${id}`),
  ingestRepository: (payload: { url: string; branch?: string; depth: number }) =>
    request<{ id: string; status: string; message: string }>("/repositories/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteRepository: (id: string) =>
    request<void>(`/repositories/${id}`, { method: "DELETE" }),

  // ── Vault ───────────────────────────────────────────────────────────────
  vaultStatus: () => request<VaultStatus>("/vault/status"),
  unlockVault: (passphrase: string) =>
    request<VaultStatus>("/vault/unlock", {
      method: "POST",
      body: JSON.stringify({ passphrase }),
    }),
  lockVault: () => request<VaultStatus>("/vault/lock", { method: "POST" }),
  listKeys: () => request<ProviderKey[]>("/vault/keys"),
  createKey: (payload: { provider_id: string; label: string; api_key: string }) =>
    request<ProviderKey>("/vault/keys", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  rotateKey: (id: string, api_key: string) =>
    request<ProviderKey>(`/vault/keys/${id}/rotate`, {
      method: "POST",
      body: JSON.stringify({ api_key }),
    }),
  deleteKey: (id: string) => request<void>(`/vault/keys/${id}`, { method: "DELETE" }),
  verifyKey: (id: string) =>
    request<{
      ok: boolean;
      provider_id: string;
      model: string;
      latency_ms: number;
      message: string;
    }>(`/vault/keys/${id}/verify`, { method: "POST" }),

  // ── Providers ───────────────────────────────────────────────────────────
  providerCatalog: () => request<ProviderCatalog>("/providers"),
  usage: () => request<UsageSummary>("/providers/usage"),
  routedChat: (payload: {
    messages: { role: string; content: string }[];
    model?: string | null;
    provider_id?: string | null;
    max_tokens?: number;
    temperature?: number;
  }) =>
    request<{
      provider_id: string;
      model: string;
      content: string;
      prompt_tokens: number;
      completion_tokens: number;
      latency_ms: number;
    }>("/providers/chat", { method: "POST", body: JSON.stringify(payload) }),

  // ── Swarm ───────────────────────────────────────────────────────────────
  listJobs: () => request<SwarmJob[]>("/swarm/jobs"),
  getJob: (id: string) => request<SwarmJobDetail>(`/swarm/jobs/${id}`),
  launchJob: (payload: {
    repository_id: string;
    task: string;
    preferred_model?: string | null;
    preferred_provider_id?: string | null;
    max_repair_iterations: number;
    validation_enabled: boolean;
  }) =>
    request<SwarmJob>("/swarm/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  cancelJob: (id: string) =>
    request<SwarmJob>(`/swarm/jobs/${id}/cancel`, { method: "POST" }),
  listJobEvents: (id: string, afterId = 0) =>
    request<SwarmEvent[]>(`/swarm/jobs/${id}/events?after_id=${afterId}`),
  jobDiff: (id: string, refresh = false) =>
    request<DiffSummary>(`/swarm/jobs/${id}/diff${refresh ? "?refresh=true" : ""}`),

  // ── Dashboard ───────────────────────────────────────────────────────────
  stats: () => request<DashboardStats>("/stats"),
};
