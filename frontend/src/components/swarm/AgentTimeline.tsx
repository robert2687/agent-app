import {
  Bot,
  CheckCircle2,
  Compass,
  DraftingCompass,
  FileCode2,
  GitPullRequestArrow,
  Loader2,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { classNames } from "@/lib/format";
import type { AgentSnapshot } from "@/hooks/useJobStream";

const AGENT_META: Record<
  string,
  { label: string; icon: React.ReactNode; blurb: string }
> = {
  planner: {
    label: "Planner",
    icon: <Compass className="h-4 w-4" />,
    blurb: "Decomposes the task",
  },
  architect: {
    label: "Architect",
    icon: <DraftingCompass className="h-4 w-4" />,
    blurb: "Designs modules & interfaces",
  },
  coder: {
    label: "Coder",
    icon: <FileCode2 className="h-4 w-4" />,
    blurb: "Writes complete file edits",
  },
  reviewer: {
    label: "Reviewer",
    icon: <GitPullRequestArrow className="h-4 w-4" />,
    blurb: "Static review of the diff",
  },
  patcher: {
    label: "Patcher",
    icon: <Wrench className="h-4 w-4" />,
    blurb: "Self-healing repairs",
  },
};

/** Horizontal pipeline of the five agent roles with live status. */
export function AgentTimeline({
  agents,
  activeAgent,
  repairIteration,
  maxRepairs,
}: {
  agents: Record<string, AgentSnapshot>;
  activeAgent: string | null;
  repairIteration: number;
  maxRepairs: number;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-stretch gap-3">
        {Object.entries(AGENT_META).map(([role, meta]) => {
          const snapshot = agents[role];
          const state = snapshot?.state ?? "pending";
          const isActive = activeAgent === role && state === "running";
          return (
            <div
              key={role}
              className={classNames(
                "flex min-w-[150px] flex-1 items-center gap-3 rounded-xl border p-3 transition",
                state === "done"
                  ? "border-emerald-500/30 bg-emerald-500/5"
                  : isActive
                    ? "border-indigo-500/50 bg-indigo-500/10 shadow-lg shadow-indigo-950/40"
                    : "border-nexus-700/60 bg-nexus-900/50",
              )}
            >
              <div
                className={classNames(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                  state === "done"
                    ? "bg-emerald-500/15 text-emerald-300"
                    : isActive
                      ? "bg-indigo-500/20 text-indigo-300"
                      : "bg-nexus-800 text-slate-500",
                )}
              >
                {state === "done" ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : isActive ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  meta.icon
                )}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-200">{meta.label}</p>
                <p className="truncate text-[10px] text-slate-500">{meta.blurb}</p>
                {isActive && snapshot?.startedAt && (
                  <Badge tone="indigo" className="mt-1">
                    <Bot className="h-3 w-3" /> streaming
                  </Badge>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {repairIteration > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          <Wrench className="h-3.5 w-3.5" />
          Self-healing loop: repair iteration {repairIteration} / {maxRepairs}
        </div>
      )}
    </div>
  );
}
