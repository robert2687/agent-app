import { useEffect, useState } from "react";
import {
  Boxes,
  FileDiff,
  ListChecks,
  RadioTower,
  ScrollText,
} from "lucide-react";
import { api } from "@/api/client";
import { useApi } from "@/hooks/useApi";
import { useJobStream } from "@/hooks/useJobStream";
import { Badge, statusTone } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { AgentTimeline } from "@/components/swarm/AgentTimeline";
import { TokenStream } from "@/components/swarm/TokenStream";
import { EventTimeline } from "@/components/swarm/RepairLoopPanel";
import { DiffViewer } from "@/components/swarm/DiffViewer";
import { SwarmLauncher } from "@/components/swarm/SwarmLauncher";
import { classNames, formatDuration, formatNumber } from "@/lib/format";
import type { DiffSummary, SwarmJob } from "@/types";

type ConsoleTab = "stream" | "timeline" | "diff";

export function SwarmView() {
  const jobsQuery = useApi(() => api.listJobs(), [], { pollMs: 4000 });
  const reposQuery = useApi(() => api.listRepositories(), []);
  const providersQuery = useApi(() => api.providerCatalog(), []);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [tab, setTab] = useState<ConsoleTab>("stream");
  const [cancelling, setCancelling] = useState(false);
  const [diff, setDiff] = useState<DiffSummary | null>(null);

  const activeJob: SwarmJob | null =
    jobsQuery.data?.find((job) => job.id === activeJobId) ?? null;
  const stream = useJobStream(activeJobId);

  // Refresh the job list quickly while a job is running.
  useEffect(() => {
    if (activeJob && !["completed", "failed", "cancelled"].includes(activeJob.status)) {
      const timer = setInterval(() => jobsQuery.refresh(), 1500);
      return () => clearInterval(timer);
    }
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJob?.status, activeJobId]);

  // Load the diff when the job completes.
  useEffect(() => {
    if (!activeJobId || activeJob?.status !== "completed") return;
    let cancelled = false;
    api
      .jobDiff(activeJobId)
      .then((result) => {
        if (!cancelled) setDiff(result);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [activeJobId, activeJob?.status]);

  const cancel = async () => {
    if (!activeJobId) return;
    setCancelling(true);
    await api.cancelJob(activeJobId).catch(() => undefined);
    setCancelling(false);
    jobsQuery.refresh();
  };

  return (
    <div className="space-y-6">
      <Card
        title="Launch a multi-agent swarm"
        subtitle="Planner → Architect → Coder → Reviewer → Validator → Patcher (self-healing)"
      >
        <SwarmLauncher
          repositories={reposQuery.data ?? []}
          providers={providersQuery.data?.providers ?? []}
          activeJob={activeJob}
          onCancel={() => void cancel()}
          cancelling={cancelling}
          onLaunched={(job) => {
            setActiveJobId(job.id);
            setTab("stream");
            setDiff(null);
            jobsQuery.refresh();
          }}
        />
      </Card>

      {jobsQuery.data && jobsQuery.data.length > 0 && (
        <Card title="Jobs" subtitle="Select a job to inspect its live console">
          <ul className="flex flex-wrap gap-2">
            {jobsQuery.data.map((job) => (
              <li key={job.id}>
                <button
                  onClick={() => {
                    setActiveJobId(job.id);
                    setDiff(null);
                  }}
                  className={classNames(
                    "flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs transition",
                    activeJobId === job.id
                      ? "border-indigo-500/50 bg-indigo-500/15 text-indigo-200"
                      : "border-nexus-700/60 bg-nexus-900/60 text-slate-400 hover:text-slate-200",
                  )}
                >
                  <span className="max-w-[220px] truncate">{job.task}</span>
                  <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {activeJobId === null ? (
        <EmptyState
          icon={<Boxes className="h-8 w-8" />}
          title="No job selected"
          description="Launch a swarm above, or pick one of your previous jobs to replay its console and diff."
        />
      ) : (
        <Card
          title={
            <span className="flex items-center gap-2">
              <RadioTower className="h-4 w-4 text-indigo-400" />
              Swarm console
              {activeJob && <Badge tone={statusTone(activeJob.status)}>{activeJob.status}</Badge>}
              {stream.connected && <Badge tone="emerald">SSE live</Badge>}
            </span>
          }
          subtitle={
            activeJob
              ? `${formatDuration(activeJob.started_at, activeJob.finished_at)} · ${formatNumber(
                  activeJob.token_usage.prompt_tokens + activeJob.token_usage.completion_tokens,
                )} tokens · ${activeJob.token_usage.requests} LLM calls`
              : "loading job…"
          }
          actions={
            <div className="flex rounded-lg border border-nexus-700/60 p-0.5 text-xs">
              {(
                [
                  ["stream", "Token stream", <ScrollText key="i" className="h-3.5 w-3.5" />],
                  ["timeline", "Timeline", <ListChecks key="i" className="h-3.5 w-3.5" />],
                  ["diff", "Diff", <FileDiff key="i" className="h-3.5 w-3.5" />],
                ] as [ConsoleTab, string, React.ReactNode][]
              ).map(([id, label, icon]) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={classNames(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 transition",
                    tab === id
                      ? "bg-indigo-500/20 text-indigo-200"
                      : "text-slate-500 hover:text-slate-300",
                  )}
                >
                  {icon}
                  {label}
                </button>
              ))}
            </div>
          }
        >
          <div className="space-y-4">
            <AgentTimeline
              agents={stream.agents}
              activeAgent={stream.currentAgent}
              repairIteration={
                activeJob?.repair_iteration ?? stream.repairs
              }
              maxRepairs={activeJob?.max_repair_iterations ?? 3}
            />

            {stream.error && (
              <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                {stream.error}
              </p>
            )}

            {tab === "stream" && (
              <TokenStream
                tokenText={stream.tokenText}
                activeAgent={stream.currentAgent}
              />
            )}
            {tab === "timeline" && <EventTimeline events={stream.timeline} />}
            {tab === "diff" && <DiffViewer diff={diff} />}
          </div>
        </Card>
      )}
    </div>
  );
}
