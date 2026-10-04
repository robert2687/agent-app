import type { ButtonHTMLAttributes, ReactNode } from "react";
import { classNames } from "@/lib/format";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-indigo-600/40 border-transparent",
  secondary:
    "bg-nexus-800 text-slate-200 hover:bg-nexus-700 border-nexus-600/70 disabled:opacity-50",
  danger:
    "bg-rose-600/90 text-white hover:bg-rose-500 border-transparent disabled:opacity-50",
  ghost:
    "bg-transparent text-slate-300 hover:bg-nexus-800 border-transparent disabled:opacity-40",
};

const SIZES: Record<Size, string> = {
  sm: "px-2.5 py-1 text-xs",
  md: "px-4 py-2 text-sm",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children: ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  children,
  className,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={classNames(
        "inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition",
        "focus:outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:cursor-not-allowed",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
    >
      {loading && (
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/40 border-t-white" />
      )}
      {children}
    </button>
  );
}
