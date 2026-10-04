import { CheckCircle2, ListChecks, XCircle } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import type { SwarmEvent } from "@/types";

/** Persisted milestone timeline: validations, repairs, edits, verdicts. */
export function EventTimeline({ events }: { events: SwarmEvent[] }) {
  const milestones = events.filter(
    (event) =>
      event.type === "validation.result" ||
      event.type === "repair.loop" ||
      event.type === "edits.applied" ||
      event.type === "agent.complete" ||
      event.type === "context.built" ||
      event.type === "job.diff" ||
      event.type === "job.completed" ||
      event.type === "job.failed",
  );

  if (milestones.length === 0) {
    return (
      <EmptyState
        icon={<ListChecks className="h-7 w-7" />}
        title="No milestones yet"
        description="Validation results, repair iterations and agent completions will appear here."
      />
    );
  }

  return (
    <ol className="relative space-y-3 border-l border-nexus-700/70 pl-4">
      {milestones.map((event, index) => (
        <li key={`${event.id ?? index}-${event.type}`} className="relative">
          <span className="absolute -left-[21px] top-1 flex h-3 w-3 items-center justify-center">
            {event.type === "validation.result" ? (
              event.data.passed ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              ) : (
                <XCircle className="h-3.5 w-3.5 text-rose-400" />
              )
            ) : (
              <span
                className={
                  event.type === "job.failed"
                    ? "h-2 w-2 rounded-full bg-rose-400"
                    : event.type === "job.completed"
                      ? "h-2 w-2 rounded-full bg-emerald-400"
                      : "h-2 w-2 rounded-full bg-indigo-400"
                }
              />
            )}
          </span>
          <Milestone event={event} />
        </li>
      ))}
    </ol>
  );
}

function Milestone({ event }: { event: SwarmEvent }) {
  switch (event.type) {
    case "validation.result":
      return (
        <div>
          <p className="text-xs font-medium text-slate-300">
            Validation {event.data.passed ? "passed" : "failed"} · lint{" "}
            {event.data.lint_ok ? "✓" : "✗"} · tests {event.data.tests_ok ? "✓" : "✗"}
          </p>
          {!event.data.passed && (
            <pre className="mt-1 max-h-32 overflow-y-auto rounded-lg bg-nexus-950/80 p-2 font-mono text-[10px] text-slate-400">
              {String(event.data.tests_excerpt ?? event.data.lint_excerpt ?? "")}
            </pre>
          )}
        </div>
      );
    case "repair.loop":
      return (
        <p className="text-xs font-medium text-amber-300">
          Self-healing: repair iteration {String(event.data.iteration)} triggered by{" "}
          {String(event.data.trigger)}
          {Array.isArray(event.data.failing_files) &&
            (event.data.failing_files as string[]).length > 0 &&
            ` · failing: ${(event.data.failing_files as string[]).slice(0, 3).join(", ")}`}
        </p>
      );
    case "edits.applied":
      return (
        <p className="text-xs text-slate-400">
          {String(event.agent ?? "agent")} applied {String(event.data.count)} edit(s)
          {typeof event.data.summary === "string" && event.data.summary
            ? ` — ${event.data.summary.slice(0, 140)}`
            : ""}
        </p>
      );
    case "agent.complete":
      return (
        <p className="text-xs text-slate-400">
          {String(event.agent)} finished
          {event.data.artifact
            ? ` — ${JSON.stringify(event.data.artifact).slice(0, 140)}`
            : ""}
        </p>
      );
    case "context.built":
      return (
        <p className="text-xs text-slate-400">
          Context built: {String(event.data.windows)} window(s) ·{" "}
          {String(event.data.files)} files · ~
          {String(event.data.estimated_tokens)} tokens ·{" "}
          {String(event.data.secret_blocked_files)} secret-bearing file(s) excluded
        </p>
      );
    case "job.diff":
      return (
        <p className="text-xs text-slate-300">
          Diff ready: {String(event.data.files)} file(s), +
          {String(event.data.additions)} / −{String(event.data.deletions)}
        </p>
      );
    case "job.completed":
      return (
        <p className="text-xs font-semibold text-emerald-300">
          Job completed — {String(event.data.repairs ?? 0)} repair iteration(s)
        </p>
      );
    case "job.failed":
      return (
        <p className="text-xs font-semibold text-rose-300">
          Job failed — {String(event.data.error ?? "unknown error")}
        </p>
      );
    default:
      return null;
  }
}
