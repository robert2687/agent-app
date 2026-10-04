import { useState } from "react";
import { Boxes, Play, Square } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/EmptyState";
import type { ProviderRuntimeStatus, RepositorySummary, SwarmJob } from "@/types";

export function SwarmLauncher({
  repositories,
  providers,
  onLaunched,
  activeJob,
  onCancel,
  cancelling,
}: {
  repositories: RepositorySummary[];
  providers: ProviderRuntimeStatus[];
  onLaunched: (job: SwarmJob) => void;
  activeJob: SwarmJob | null;
  onCancel: () => void;
  cancelling: boolean;
}) {
  const readyRepos = repositories.filter((repo) => repo.status === "ready");
  const [repositoryId, setRepositoryId] = useState("");
  const [task, setTask] = useState("");
  const [model, setModel] = useState("");
  const [repairs, setRepairs] = useState(3);
  const [validation, setValidation] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const modelOptions = providers.flatMap((provider) =>
    provider.supported_models.map((m) => ({
      value: m,
      label: `${m} · ${provider.display_name}`,
      usable: provider.key_configured,
    })),
  );

  const launch = async () => {
    setBusy(true);
    setError(null);
    try {
      const job = await api.launchJob({
        repository_id: repositoryId,
        task,
        preferred_model: model || null,
        max_repair_iterations: repairs,
        validation_enabled: validation,
      });
      setTask("");
      onLaunched(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Launch failed");
    } finally {
      setBusy(false);
    }
  };

  const jobActive =
    activeJob !== null &&
    !["completed", "failed", "cancelled"].includes(activeJob.status);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className="nexus-label" htmlFor="swarm-repo">
            Target repository
          </label>
          <select
            id="swarm-repo"
            className="nexus-input"
            value={repositoryId}
            onChange={(event) => setRepositoryId(event.target.value)}
          >
            <option value="">
              {readyRepos.length === 0
                ? "No ready repositories — ingest one first"
                : "Select a repository…"}
            </option>
            {readyRepos.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="nexus-label" htmlFor="swarm-model">
            Model preference (routed with adaptive failover)
          </label>
          <select
            id="swarm-model"
            className="nexus-input"
            value={model}
            onChange={(event) => setModel(event.target.value)}
          >
            <option value="">Auto — best available provider</option>
            {modelOptions.map((option) => (
              <option
                key={option.value}
                value={option.value}
                disabled={!option.usable}
              >
                {option.usable ? "" : "🔒 "}
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="nexus-label" htmlFor="swarm-task">
          Task for the swarm
        </label>
        <textarea
          id="swarm-task"
          className="nexus-input min-h-[90px] resize-y"
          value={task}
          minLength={16}
          onChange={(event) => setTask(event.target.value)}
          placeholder="e.g. Add input validation to the API handlers and unit tests for each new branch."
        />
      </div>

      <div className="flex flex-wrap items-end gap-5">
        <div className="w-40">
          <label className="nexus-label" htmlFor="swarm-repairs">
            Max repair iterations
          </label>
          <select
            id="swarm-repairs"
            className="nexus-input"
            value={repairs}
            onChange={(event) => setRepairs(Number(event.target.value))}
          >
            {[0, 1, 2, 3, 5, 8].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <label className="flex cursor-pointer items-center gap-2 pb-2 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={validation}
            onChange={(event) => setValidation(event.target.checked)}
            className="h-4 w-4 rounded border-nexus-600 bg-nexus-900 accent-indigo-500"
          />
          Run lint + tests (enables self-healing loop)
        </label>
        <div className="ml-auto flex gap-2">
          {jobActive && (
            <Button variant="danger" size="sm" loading={cancelling} onClick={onCancel}>
              <Square className="h-3.5 w-3.5" /> Cancel job
            </Button>
          )}
          <Button
            onClick={() => void launch()}
            loading={busy}
            disabled={!repositoryId || task.trim().length < 16}
          >
            <Play className="h-4 w-4" /> Launch swarm
          </Button>
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {modelOptions.length > 0 &&
        modelOptions.every((option) => !option.usable) && (
          <p className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            <Boxes className="h-3.5 w-3.5" />
            No provider keys registered — add one in the Key Vault view before
            launching.
          </p>
        )}
    </div>
  );
}
