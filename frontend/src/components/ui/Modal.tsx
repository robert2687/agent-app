import type { ReactNode } from "react";
import { X } from "lucide-react";
import { classNames } from "@/lib/format";

export function Modal({
  open,
  onClose,
  title,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={classNames(
          "max-h-[85vh] w-full overflow-y-auto rounded-xl border border-nexus-600/60 bg-nexus-850 shadow-2xl",
          wide ? "max-w-2xl" : "max-w-md",
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-nexus-700/60 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-500 transition hover:bg-nexus-700 hover:text-slate-300"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
