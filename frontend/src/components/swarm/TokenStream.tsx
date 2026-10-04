import { useEffect, useRef } from "react";
import { Terminal } from "lucide-react";
import { classNames } from "@/lib/format";

/** Live token-by-token output panel, one section per agent. */
export function TokenStream({
  tokenText,
  activeAgent,
}: {
  tokenText: Record<string, string>;
  activeAgent: string | null;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const entries = Object.entries(tokenText);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [tokenText]);

  if (entries.length === 0) {
    return (
      <div className="flex h-full min-h-[280px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-nexus-600/50 text-slate-600">
        <Terminal className="h-6 w-6" />
        <p className="text-xs">
          Agent token output will stream here (SSE) once the swarm starts.
        </p>
      </div>
    );
  }

  return (
    <div className="max-h-[520px] space-y-3 overflow-y-auto rounded-xl border border-nexus-700/60 bg-nexus-950/80 p-3">
      {entries.map(([agent, text]) => {
        const isActive = agent === activeAgent;
        const display = text.length > 8000 ? `${text.slice(0, 8000)}\n… (stream truncated for display)` : text;
        return (
          <div key={agent}>
            <div className="mb-1 flex items-center gap-2">
              <span
                className={classNames(
                  "rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider",
                  isActive
                    ? "bg-indigo-500/20 text-indigo-300"
                    : "bg-nexus-800 text-slate-400",
                )}
              >
                {agent}
              </span>
              {isActive && (
                <span className="text-[10px] text-indigo-400">streaming…</span>
              )}
            </div>
            <pre
              className={classNames(
                "token-stream whitespace-pre-wrap rounded-lg bg-nexus-900/70 p-3 font-mono text-[11px] leading-relaxed text-slate-300",
                isActive && "live-cursor",
              )}
            >
              {display}
            </pre>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
