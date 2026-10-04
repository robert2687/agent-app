import type { ReactNode } from "react";
import { classNames } from "@/lib/format";

export function Card({
  children,
  className,
  title,
  subtitle,
  actions,
}: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className={classNames("nexus-panel p-5", className)}>
      {(title || actions) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && (
              <h2 className="text-sm font-semibold tracking-wide text-slate-200">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
