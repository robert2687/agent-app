import { useState } from "react";
import { KeyRound, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "@/api/client";
import { Badge, statusTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDateTime } from "@/lib/format";
import type { ProviderKey } from "@/types";

export function ProviderKeyList({
  keys,
  onChanged,
}: {
  keys: ProviderKey[];
  onChanged: () => void;
}) {
  const [verifying, setVerifying] = useState<string | null>(null);
  const [verifyResult, setVerifyResult] = useState<Record<string, string>>({});

  const verify = async (id: string) => {
    setVerifying(id);
    try {
      const result = await api.verifyKey(id);
      setVerifyResult((previous) => ({
        ...previous,
        [id]: `${result.ok ? "✓" : "✗"} ${result.message} (${Math.round(result.latency_ms)}ms)`,
      }));
      onChanged();
    } catch (err) {
      setVerifyResult((previous) => ({
        ...previous,
        [id]: err instanceof Error ? err.message : "verification failed",
      }));
    } finally {
      setVerifying(null);
    }
  };

  const remove = async (id: string) => {
    await api.deleteKey(id).catch(() => undefined);
    onChanged();
  };

  if (keys.length === 0) {
    return (
      <EmptyState
        icon={<KeyRound className="h-8 w-8" />}
        title="No sealed keys yet"
        description="Register a provider API key — it will be encrypted with AES-256-GCM (random salt + nonce per record) before touching disk."
      />
    );
  }

  return (
    <ul className="space-y-3">
      {keys.map((key) => (
        <li
          key={key.id}
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-nexus-700/60 bg-nexus-900/60 p-3.5"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-medium text-slate-200">{key.label}</p>
              <Badge tone={statusTone(key.status)}>{key.status}</Badge>
            </div>
            <p className="mt-0.5 font-mono text-[11px] text-slate-500">
              {key.provider_id} · fp {key.masked_hint}
            </p>
            <p className="text-[11px] text-slate-600">
              sealed {formatDateTime(key.created_at)}
              {key.last_verified_at
                ? ` · verified ${formatDateTime(key.last_verified_at)}`
                : ""}
            </p>
            {verifyResult[key.id] && (
              <p className="mt-1 text-[11px] text-slate-400">{verifyResult[key.id]}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              loading={verifying === key.id}
              onClick={() => void verify(key.id)}
            >
              <ShieldCheck className="h-3.5 w-3.5" /> Verify
            </Button>
            <Button variant="danger" size="sm" onClick={() => void remove(key.id)}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
