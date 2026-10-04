import type { ReactNode } from "react";
import { classNames } from "@/lib/format";

type Tone = "neutral" | "indigo" | "emerald" | "amber" | "rose" | "sky";

const TONES: Record<Tone, string> = {
  neutral: "bg-nexus-700/60 text-slate-300 border-nexus-600/60",
  indigo: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  emerald: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  rose: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  sky: "bg-sky-500/15 text-sky-300 border-sky-500/30",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={classNames(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-4",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function statusTone(status: string): Tone {
  switch (status) {
    case "ready":
    case "completed":
    case "active":
    case "closed":
    case "unlocked":
    case "ok":
      return "emerald";
    case "failed":
    case "open":
    case "invalid":
    case "revoked":
      return "rose";
    case "queued":
    case "locked":
      return "neutral";
    case "cancelled":
    case "half_open":
      return "amber";
    default:
      return "indigo";
  }
}
