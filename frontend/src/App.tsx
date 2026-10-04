import { useCallback, useEffect, useState } from "react";
import { api } from "@/api/client";
import { Sidebar, type ViewId } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { DashboardView } from "@/views/DashboardView";
import { RepositoriesView } from "@/views/RepositoriesView";
import { VaultView } from "@/views/VaultView";
import { ProvidersView } from "@/views/ProvidersView";
import { SwarmView } from "@/views/SwarmView";
import type { DashboardStats, SwarmJob, UsageSummary, VaultStatus } from "@/types";

const VIEW_META: Record<ViewId, { title: string; subtitle: string }> = {
  dashboard: {
    title: "Platform Dashboard",
    subtitle: "Fleet overview — ingestion, vault, swarms and spend",
  },
  repositories: {
    title: "GitHub Ingestion",
    subtitle: "Depth-aware clone/pull · secret scanning · AST dependency graphs",
  },
  vault: {
    title: "Key Vault & Credentials",
    subtitle: "AES-256-GCM at rest · PBKDF2/Argon2 key derivation",
  },
  swarm: {
    title: "Swarm Orchestrator",
    subtitle: "Planner · Architect · Coder · Reviewer · Patcher — with self-healing repair loop",
  },
  providers: {
    title: "AI Provider Router",
    subtitle: "NVIDIA Nemotron · Qwen · OpenAI · Anthropic · Gemini — adaptive failover",
  },
};

export default function App() {
  const [view, setView] = useState<ViewId>("dashboard");
  const [backendStatus, setBackendStatus] = useState<"checking" | "ok" | "down">(
    "checking",
  );
  const [vaultStatus, setVaultStatus] = useState<VaultStatus | null>(null);

  useEffect(() => {
    const check = async () => {
      try {
        await api.ready();
        setBackendStatus("ok");
        setVaultStatus(await api.vaultStatus());
      } catch {
        setBackendStatus("down");
      }
    };
    void check();
    const interval = setInterval(() => void check(), 15_000);
    return () => clearInterval(interval);
  }, []);

  const refreshVault = useCallback(async () => {
    try {
      setVaultStatus(await api.vaultStatus());
    } catch {
      /* keep last known state */
    }
  }, []);

  // Global (cross-view) data for the dashboard.
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [jobs, setJobs] = useState<SwarmJob[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  useEffect(() => {
    if (view !== "dashboard") return;
    void api.stats().then(setStats).catch(() => undefined);
    void api.listJobs().then(setJobs).catch(() => undefined);
    void api.usage().then(setUsage).catch(() => undefined);
  }, [view]);

  return (
    <div className="flex h-screen overflow-hidden bg-nexus-950">
      <Sidebar
        active={view}
        onSelect={(next) => {
          setView(next);
          void refreshVault();
        }}
        vaultUnlocked={
          vaultStatus === null ? null : vaultStatus.state === "unlocked"
        }
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          title={VIEW_META[view].title}
          subtitle={VIEW_META[view].subtitle}
          backendStatus={backendStatus}
        />
        <main className="flex-1 overflow-y-auto p-6">
          {view === "dashboard" && (
            <DashboardView stats={stats} jobs={jobs} usage={usage} />
          )}
          {view === "repositories" && <RepositoriesView />}
          {view === "vault" && <VaultView />}
          {view === "swarm" && <SwarmView />}
          {view === "providers" && <ProvidersView />}
        </main>
        <footer className="border-t border-nexus-700/60 bg-nexus-900/60 px-6 py-2">
          <p className="text-[10px] tracking-wide text-slate-600">
            NEXUS AI SWARM PLATFORM · FastAPI · Pydantic v2 · AES-256-GCM vault ·
            tree-sitter · SSE/WebSocket streaming · multi-agent self-healing pipeline
          </p>
        </footer>
      </div>
    </div>
  );
}
