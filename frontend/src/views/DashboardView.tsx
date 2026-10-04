import { Boxes, CheckCircle2, Clock, GitBranch, Loader2, XCircle } from "lucide-react";
import { Badge, statusTone } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDateTime, formatDuration, formatNumber } from "@/lib/format";
import type { SwarmJob } from "@/types";

export function DashboardView({
  stats,
  jobs,
  usage,
}: {
  stats: { jobs: number; completed_jobs: number; active_jobs: number; repositories: number } | null;
  jobs: SwarmJob[];
  usage: { prompt_tokens: number; completion_tokens: number; total_requests: number; avg_latency_ms: number } | null;
}) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Repositories"
          value={stats?.repositories ?? "—"}
          hint="ingested via GitHub engine"
          icon={<GitBranch className="h-5 w-5" />}
        />
        <StatCard
          label="Swarm jobs"
          value={stats?.jobs ?? "—"}
          hint={`${stats?.active_jobs ?? 0} active`}
          icon={<Boxes className="h-5 w-5" />}
        />
        <StatCard
          label="Completed"
          value={stats?.completed_jobs ?? "—"}
          hint="with self-healing loop"
          icon={<CheckCircle2 className="h-5 w-5" />}
        />
        <StatCard
          label="Token spend"
          value={
            usage
              ? formatNumber(usage.prompt_tokens + usage.completion_tokens)
              : "—"
          }
          hint={
            usage
              ? `${formatNumber(usage.total_requests)} requests · ${Math.round(usage.avg_latency_ms)}ms avg`
              : undefined
          }
          icon={<Clock className="h-5 w-5" />}
        />
      </div>

      <Card title="Recent swarm jobs" subtitle="Newest first">
        {jobs.length === 0 ? (
          <EmptyState
            icon={<Boxes className="h-8 w-8" />}
            title="No swarm jobs yet"
            description="Ingest a repository, register a provider key, then launch your first multi-agent job from the Swarm view."
          />
        ) : (
          <ul className="space-y-2">
            {jobs.slice(0, 8).map((job) => (
              <li
                key={job.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-nexus-700/60 bg-nexus-900/60 px-3.5 py-2.5"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  {["queued"].includes(job.status) ? (
                    <Clock className="h-4 w-4 shrink-0 text-slate-500" />
                  ) : job.status === "completed" ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                  ) : job.status === "failed" ? (
                    <XCircle className="h-4 w-4 shrink-0 text-rose-400" />
                  ) : (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-indigo-400" />
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-xs text-slate-300">{job.task}</p>
                    <p className="text-[10px] text-slate-500">
                      {formatDateTime(job.created_at)} ·{" "}
                      {formatDuration(job.started_at, job.finished_at)} ·{" "}
                      {job.repair_iteration}/{job.max_repair_iterations} repairs
                    </p>
                  </div>
                </div>
                <Badge tone={statusTone(job.status)}>{job.status}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
