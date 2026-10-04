import { useState } from "react";
import { Github, Download } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/EmptyState";

/** GitHub ingestion form: URL + branch + depth-aware clone options. */
export function IngestionForm({ onQueued }: { onQueued: () => void }) {
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [depth, setDepth] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queued, setQueued] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    setQueued(null);
    try {
      const result = await api.ingestRepository({
        url: url.trim(),
        branch: branch.trim() || undefined,
        depth,
      });
      setQueued(result.message);
      setUrl("");
      setBranch("");
      onQueued();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingestion failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[2fr_1fr_120px]">
        <div>
          <label className="nexus-label" htmlFor="repo-url">
            Repository URL
          </label>
          <input
            id="repo-url"
            className="nexus-input font-mono text-xs"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://github.com/owner/repo"
          />
        </div>
        <div>
          <label className="nexus-label" htmlFor="repo-branch">
            Branch (optional)
          </label>
          <input
            id="repo-branch"
            className="nexus-input"
            value={branch}
            onChange={(event) => setBranch(event.target.value)}
            placeholder="default"
          />
        </div>
        <div>
          <label className="nexus-label" htmlFor="repo-depth">
            Depth
          </label>
          <select
            id="repo-depth"
            className="nexus-input"
            value={depth}
            onChange={(event) => setDepth(Number(event.target.value))}
          >
            {[1, 5, 10, 25, 50].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error && <ErrorNote message={error} />}
      {queued && (
        <p className="flex items-center gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-2 text-xs text-indigo-300">
          <Download className="h-3.5 w-3.5" /> {queued}
        </p>
      )}
      <Button
        onClick={() => void submit()}
        loading={busy}
        disabled={!/^https?:\/\/.+/.test(url.trim())}
      >
        <Github className="h-4 w-4" /> Clone & ingest
      </Button>
      <p className="text-[11px] leading-relaxed text-slate-500">
        Pipeline: depth-aware clone/pull → binary filtration → secret scanning →
        tree-sitter AST dependency graph → token-aware context windows. Watch live
        status in the list below.
      </p>
    </div>
  );
}
