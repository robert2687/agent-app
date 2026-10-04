import { Activity } from "lucide-react";
import { Badge, statusTone } from "@/components/ui/Badge";

export function Header({
  title,
  subtitle,
  backendStatus,
}: {
  title: string;
  subtitle: string;
  backendStatus: "checking" | "ok" | "down";
}) {
  return (
    <header className="flex items-center justify-between border-b border-nexus-700/60 bg-nexus-900/60 px-6 py-4">
      <div>
        <h1 className="text-lg font-semibold text-white">{title}</h1>
        <p className="text-xs text-slate-500">{subtitle}</p>
      </div>
      <div className="flex items-center gap-2">
        <Badge tone={statusTone(backendStatus)}>
          <Activity className="h-3 w-3" />
          {backendStatus === "checking"
            ? "connecting"
            : backendStatus === "ok"
              ? "backend online"
              : "backend offline"}
        </Badge>
      </div>
    </header>
  );
}
