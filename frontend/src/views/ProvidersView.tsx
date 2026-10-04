import { Activity, Gauge, ShieldCheck, Zap } from "lucide-react";
import { api } from "@/api/client";
import { useApi } from "@/hooks/useApi";
import { Badge, statusTone } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { formatNumber } from "@/lib/format";

export function ProvidersView() {
  const catalog = useApi(() => api.providerCatalog(), [], { pollMs: 5000 });
  const usage = useApi(() => api.usage(), [], { pollMs: 5000 });

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Requests routed"
          value={formatNumber(usage.data?.total_requests ?? 0)}
          hint={`${usage.data?.ok_requests ?? 0} ok · ${usage.data?.failed_requests ?? 0} failed`}
          icon={<Zap className="h-5 w-5" />}
        />
        <StatCard
          label="Avg latency"
          value={`${Math.round(usage.data?.avg_latency_ms ?? 0)} ms`}
          hint="EWMA-weighted provider selection"
          icon={<Gauge className="h-5 w-5" />}
        />
        <StatCard
          label="Tokens used"
          value={formatNumber(
            (usage.data?.prompt_tokens ?? 0) + (usage.data?.completion_tokens ?? 0),
          )}
          hint={`${formatNumber(usage.data?.prompt_tokens ?? 0)} prompt · ${formatNumber(usage.data?.completion_tokens ?? 0)} completion`}
          icon={<Activity className="h-5 w-5" />}
        />
      </div>

      <Card
        title="Provider catalog & live health"
        subtitle="OpenAI-compatible endpoints with adaptive failover, sliding-window rate limits and circuit breakers"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-nexus-700/60 text-[10px] uppercase tracking-wider text-slate-500">
                <th className="px-3 py-2">Provider</th>
                <th className="px-3 py-2">Default model</th>
                <th className="px-3 py-2">Key</th>
                <th className="px-3 py-2">Circuit</th>
                <th className="px-3 py-2">Rate window</th>
                <th className="px-3 py-2">EWMA latency</th>
                <th className="px-3 py-2">Requests</th>
              </tr>
            </thead>
            <tbody>
              {(catalog.data?.providers ?? []).map((provider) => (
                <tr
                  key={provider.provider_id}
                  className="border-b border-nexus-800/60 last:border-0"
                >
                  <td className="px-3 py-2.5">
                    <p className="font-medium text-slate-200">{provider.display_name}</p>
                    <p className="font-mono text-[10px] text-slate-600">{provider.base_url}</p>
                  </td>
                  <td className="px-3 py-2.5">
                    <p className="font-mono text-[11px] text-slate-300">
                      {provider.default_model}
                    </p>
                    <p className="text-[10px] text-slate-600">
                      {provider.supported_models.length} model(s) · max{" "}
                      {formatNumber(provider.max_tokens_limit)} tok
                    </p>
                  </td>
                  <td className="px-3 py-2.5">
                    {provider.key_configured ? (
                      <Badge tone={statusTone(provider.key_status ?? "active")}>
                        <ShieldCheck className="h-3 w-3" />
                        {provider.key_status ?? "active"}
                      </Badge>
                    ) : (
                      <Badge tone="neutral">no key</Badge>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge tone={statusTone(provider.circuit)}>{provider.circuit}</Badge>
                  </td>
                  <td className="px-3 py-2.5 text-slate-400">
                    {provider.requests_in_window}/{provider.rate_limit_max} per{" "}
                    {provider.rate_limit_window_seconds}s
                  </td>
                  <td className="px-3 py-2.5 text-slate-400">
                    {provider.ewma_latency_ms === null
                      ? "—"
                      : `${Math.round(provider.ewma_latency_ms)} ms`}
                  </td>
                  <td className="px-3 py-2.5 text-slate-400">
                    {provider.total_requests}{" "}
                    {provider.failed_requests > 0 && (
                      <span className="text-rose-400">
                        ({provider.failed_requests} failed)
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {catalog.error && (
          <p className="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
            {catalog.error}
          </p>
        )}
      </Card>
    </div>
  );
}
