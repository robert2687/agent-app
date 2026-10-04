import { GitBranch } from "lucide-react";
import { api } from "@/api/client";
import { useApi } from "@/hooks/useApi";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IngestionForm } from "@/components/repositories/IngestionForm";
import { RepositoryCard } from "@/components/repositories/RepositoryCard";

export function RepositoriesView() {
  const { data, loading, error, refresh } = useApi(
    () => api.listRepositories(),
    [],
    { pollMs: 4000 },
  );

  return (
    <div className="space-y-6">
      <Card
        title="GitHub ingestion engine"
        subtitle="Depth-aware clone/pull with secret scanning and AST parsing"
      >
        <IngestionForm onQueued={refresh} />
      </Card>

      <Card
        title="Ingested repositories"
        subtitle={
          loading ? "loading…" : `${data?.length ?? 0} repository(ies)`
        }
      >
        {error && (
          <p className="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
            {error}
          </p>
        )}
        {!loading && (data?.length ?? 0) === 0 ? (
          <EmptyState
            icon={<GitBranch className="h-8 w-8" />}
            title="Nothing ingested yet"
            description="Paste a GitHub URL above — the engine clones it, filters binaries, scans for secrets and builds the dependency graph."
          />
        ) : (
          <ul className="space-y-3">
            {(data ?? []).map((repository) => (
              <RepositoryCard
                key={repository.id}
                repository={repository}
                onChanged={refresh}
              />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
