import type { ReactNode } from "react";
import { classNames } from "@/lib/format";

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={classNames(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-nexus-600/50 px-6 py-12 text-center",
        className,
      )}
    >
      <div className="mb-3 text-nexus-500">{icon}</div>
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
      {message}
    </p>
  );
}
