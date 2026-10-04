import { useMemo, useState } from "react";
import { FileDiff, FilePlus2, FileMinus2, FileCode2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { classNames } from "@/lib/format";
import type { DiffSummary } from "@/types";

/**
 * Side-by-side unified diff viewer.
 * Left pane: removed/context lines (old). Right pane: added/context lines (new).
 */
export function DiffViewer({ diff }: { diff: DiffSummary | null }) {
  const [selected, setSelected] = useState<string | null>(null);

  const files = diff?.files ?? [];
  const activeFile = useMemo(
    () => files.find((file) => file.path === selected) ?? files[0] ?? null,
    [files, selected],
  );

  if (!diff || files.length === 0) {
    return (
      <EmptyState
        icon={<FileDiff className="h-8 w-8" />}
        title="No diff yet"
        description="Once the swarm finishes, the unified git diff (including new files) appears here for side-by-side review."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
      <aside className="max-h-[560px] space-y-1 overflow-y-auto rounded-xl border border-nexus-700/60 bg-nexus-900/60 p-2">
        {files.map((file) => (
          <button
            key={file.path}
            onClick={() => setSelected(file.path)}
            className={classNames(
              "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition",
              activeFile?.path === file.path
                ? "bg-indigo-500/15 text-indigo-200"
                : "text-slate-400 hover:bg-nexus-800",
            )}
          >
            {file.is_new ? (
              <FilePlus2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
            ) : file.is_deleted ? (
              <FileMinus2 className="h-3.5 w-3.5 shrink-0 text-rose-400" />
            ) : (
              <FileCode2 className="h-3.5 w-3.5 shrink-0 text-slate-500" />
            )}
            <span className="truncate font-mono">{file.path}</span>
            <span className="ml-auto shrink-0 font-mono text-[10px]">
              <span className="text-emerald-400">+{file.additions}</span>{" "}
              <span className="text-rose-400">−{file.deletions}</span>
            </span>
          </button>
        ))}
      </aside>

      <div className="min-w-0">
        {activeFile ? (
          <div className="overflow-hidden rounded-xl border border-nexus-700/60">
            <header className="flex items-center justify-between gap-2 border-b border-nexus-700/60 bg-nexus-900/80 px-4 py-2.5">
              <p className="truncate font-mono text-xs text-slate-300">
                {activeFile.path}
              </p>
              <div className="flex shrink-0 gap-1.5">
                {activeFile.is_new && <Badge tone="emerald">new file</Badge>}
                {activeFile.is_deleted && <Badge tone="rose">deleted</Badge>}
                {activeFile.is_binary && <Badge tone="amber">binary</Badge>}
              </div>
            </header>
            {activeFile.is_binary ? (
              <p className="p-6 text-center text-xs text-slate-500">
                Binary file — diff suppressed.
              </p>
            ) : (
              <div className="max-h-[520px] overflow-auto">
                <table className="w-full border-collapse font-mono text-[11px] leading-[1.55]">
                  <tbody>
                    {activeFile.hunks.map((hunk, hunkIndex) => {
                      const rows: {
                        left: [number, string] | null;
                        right: [number, string] | null;
                      }[] = [];
                      let leftIndex = 0;
                      let rightIndex = 0;
                      while (
                        leftIndex < hunk.old_lines.length ||
                        rightIndex < hunk.new_lines.length
                      ) {
                        const oldLine = hunk.old_lines[leftIndex];
                        const newLine = hunk.new_lines[rightIndex];
                        if (oldLine && newLine && oldLine[1] === newLine[1]) {
                          rows.push({ left: oldLine, right: newLine });
                          leftIndex += 1;
                          rightIndex += 1;
                        } else if (
                          newLine &&
                          (!oldLine ||
                            rightIndex < hunk.new_lines.length) &&
                          (!oldLine || oldLine[1] !== newLine[1]) &&
                          (leftIndex >= hunk.old_lines.length ||
                            !(
                              hunk.old_lines[leftIndex] &&
                              hunk.new_lines[rightIndex + 1] &&
                              hunk.old_lines[leftIndex][1] ===
                                hunk.new_lines[rightIndex + 1][1]
                            ))
                        ) {
                          rows.push({ left: null, right: newLine });
                          rightIndex += 1;
                        } else if (oldLine) {
                          rows.push({ left: oldLine, right: null });
                          leftIndex += 1;
                        } else {
                          rows.push({ left: null, right: newLine });
                          rightIndex += 1;
                        }
                      }
                      return (
                        <HunkTable
                          key={hunkIndex}
                          hunkIndex={hunkIndex}
                          hunkHeader={`@@ -${hunk.old_start} +${hunk.new_start} @@`}
                          rows={rows}
                        />
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function HunkTable({
  hunkHeader,
  rows,
  hunkIndex,
}: {
  hunkHeader: string;
  rows: { left: [number, string] | null; right: [number, string] | null }[];
  hunkIndex: number;
}) {
  return (
    <>
      <tr key={`h-${hunkIndex}`}>
        <td
          colSpan={4}
          className="border-y border-nexus-700/50 bg-nexus-800/60 px-3 py-1 font-mono text-[10px] text-indigo-300"
        >
          {hunkHeader}
        </td>
      </tr>
      {rows.map((row, index) => {
        const removed = row.left !== null && row.right === null;
        const added = row.right !== null && row.left === null;
        return (
          <tr key={`${hunkIndex}-${index}`} className="align-top">
            <td
              className={classNames(
                "w-10 select-none border-r border-nexus-800 px-2 text-right text-slate-600",
                removed && "bg-rose-500/5",
                added && "bg-nexus-900/40",
              )}
            >
              {row.left ? row.left[0] : ""}
            </td>
            <td
              className={classNames(
                "w-1/2 whitespace-pre-wrap px-2",
                removed
                  ? "bg-rose-500/10 text-rose-300"
                  : "text-slate-300",
              )}
            >
              {row.left ? row.left[1] : ""}
            </td>
            <td
              className={classNames(
                "w-10 select-none border-l border-r border-nexus-800 px-2 text-right text-slate-600",
                added && "bg-emerald-500/5",
                removed && "bg-nexus-900/40",
              )}
            >
              {row.right ? row.right[0] : ""}
            </td>
            <td
              className={classNames(
                "w-1/2 whitespace-pre-wrap px-2",
                added
                  ? "bg-emerald-500/10 text-emerald-300"
                  : "text-slate-300",
              )}
            >
              {row.right ? row.right[1] : ""}
            </td>
          </tr>
        );
      })}
    </>
  );
}
