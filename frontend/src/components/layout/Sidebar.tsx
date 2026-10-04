import type { ReactNode } from "react";
import {
  Boxes,
  GitBranch,
  LayoutDashboard,
  KeyRound,
  Network,
  ShieldCheck,
} from "lucide-react";
import { classNames } from "@/lib/format";

export type ViewId = "dashboard" | "repositories" | "vault" | "swarm" | "providers";

const NAV: { id: ViewId; label: string; icon: ReactNode }[] = [
  { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
  { id: "repositories", label: "Repositories", icon: <GitBranch className="h-4 w-4" /> },
  { id: "vault", label: "Key Vault", icon: <KeyRound className="h-4 w-4" /> },
  { id: "swarm", label: "Swarm", icon: <Boxes className="h-4 w-4" /> },
  { id: "providers", label: "Providers", icon: <Network className="h-4 w-4" /> },
];

export function Sidebar({
  active,
  onSelect,
  vaultUnlocked,
}: {
  active: ViewId;
  onSelect: (view: ViewId) => void;
  vaultUnlocked: boolean | null;
}) {
  return (
    <nav
      className="flex h-full w-[220px] shrink-0 flex-col border-r border-nexus-700/60 bg-nexus-900/80"
      aria-label="Primary"
    >
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-900/40">
          <Network className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-bold leading-tight text-white">NEXUS</p>
          <p className="text-[10px] uppercase tracking-[0.2em] text-indigo-400">
            AI Swarm
          </p>
        </div>
      </div>

      <div className="flex-1 space-y-1 px-3">
        {NAV.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            aria-current={active === item.id ? "page" : undefined}
            className={classNames(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
              active === item.id
                ? "bg-indigo-500/15 text-indigo-200"
                : "text-slate-400 hover:bg-nexus-800 hover:text-slate-200",
            )}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </div>

      <div className="border-t border-nexus-700/60 p-4">
        <div className="flex items-center gap-2 rounded-lg bg-nexus-850 px-3 py-2">
          <ShieldCheck
            className={classNames(
              "h-4 w-4",
              vaultUnlocked === true
                ? "text-emerald-400"
                : vaultUnlocked === false
                  ? "text-amber-400"
                  : "text-slate-500",
            )}
          />
          <div className="text-[11px] leading-tight">
            <p className="font-medium text-slate-300">Key Vault</p>
            <p
              className={classNames(
                vaultUnlocked === true
                  ? "text-emerald-400"
                  : vaultUnlocked === false
                    ? "text-amber-400"
                    : "text-slate-500",
              )}
            >
              {vaultUnlocked === null
                ? "checking…"
                : vaultUnlocked
                  ? "unlocked · AES-256-GCM"
                  : "locked"}
            </p>
          </div>
        </div>
      </div>
    </nav>
  );
}
