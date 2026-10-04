import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  GitBranch,
  Loader2,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { api } from "@/api/client";
import { Badge, statusTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { RepositorySummary } from "@/types";

export function RepositoryCard({
  repository,
  onChanged,
}: {
  repository: RepositorySummary;
  onChanged: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const remove = async () => {
    await api.deleteRepository(repository.id).catch(() => undefined);
    onChanged();
  };

  const busy = ["queued", "cloning", "scanning", "parsing"].includes(repository.status);
  const languages = Object.entries(repository.languages ?? {}).slice(0, 6);
  const criticalFindings = (repository.secret_findings ?? []).filter(
    (finding) => finding.severity === "critical" || finding.severity === "high",
  ).length;

  return (
    <li className="rounded-xl border border-nexus-700/60 bg-nexus-900/60">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <button
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-slate-500" />
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate font-mono text-sm text-slate-200">
                {repository.name}
              </p>
              <Badge tone={statusTone(repository.status)}>
                {busy && <Loader2 className="h-3 w-3 animate-spin" />}
                {repository.status}
              </Badge>
            </div>
            <p className="truncate text-[11px] text-slate-500">
              {repository.default_branch ?? "—"} @{" "}
              {(repository.head_commit ?? "").slice(0, 8) || "—"} ·{" "}
              {formatNumber(repository.file_count)} files ·{" "}
              {formatNumber(repository.total_loc)} LOC · updated{" "}
              {formatDateTime(repository.updated_at)}
            </p>
          </div>
        </button>
        <div className="flex items-center gap-2">
          {criticalFindings > 0 && (
            <Badge tone="rose">
              <ShieldAlert className="h-3 w-3" />
              {criticalFindings} secret{criticalFindings > 1 ? "s" : ""}
            </Badge>
          )}
          <Button variant="ghost" size="sm" onClick={() => void remove()} aria-label="Delete repository">
            <Trash2 className="h-3.5 w-3.5 text-slate-500" />
          </Button>
        </div>
      </div>

      {expanded && (
        <div className="space-y-4 border-t border-nexus-700/60 p-4 text-xs">
          {repository.error && (
            <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-rose-300">
              {repository.error}
            </p>
          )}
          <div>
            <p className="nexus-label">Languages</p>
            <div className="flex flex-wrap gap-1.5">
              {languages.length > 0 ? (
                languages.map(([language, count]) => (
                  <Badge key={language} tone="sky">
                    <FileCode2 className="h-3 w-3" />
                    {language} · {count}
                  </Badge>
                ))
              ) : (
                <span className="text-slate-500">—</span>
              )}
            </div>
          </div>
          <div>
            <p className="nexus-label">
              Secret scan ({(repository.secret_findings ?? []).length} findings,
              redacted)
            </p>
            {repository.secret_findings?.length ? (
              <ul className="max-h-40 space-y-1 overflow-y-auto rounded-lg bg-nexus-950/70 p-2 font-mono text-[11px]">
                {repository.secret_findings.map((finding, index) => (
                  <li key={index} className="flex items-center gap-2">
                    <Badge tone={statusTone(finding.severity)}>{finding.severity}</Badge>
                    <span className="text-slate-300">{finding.file}:{finding.line}</span>
                    <span className="truncate text-slate-500">{finding.preview}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500">clean — no secrets detected</p>
            )}
          </div>
          <div className="flex items-center gap-2 text-slate-500">
            <GitBranch className="h-3.5 w-3.5" />
            <span className="font-mono">{repository.url}</span>
          </div>
        </div>
      )}
    </li>
  );
}
