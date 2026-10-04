import { useState } from "react";
import { ShieldPlus } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/EmptyState";
import type { ProviderRuntimeStatus } from "@/types";

/** Register (seal) a new provider API key inside the vault. */
export function ProviderKeyForm({
  providers,
  vaultUnlocked,
  onCreated,
}: {
  providers: ProviderRuntimeStatus[];
  vaultUnlocked: boolean;
  onCreated: () => void;
}) {
  const [providerId, setProviderId] = useState("");
  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await api.createKey({
        provider_id: providerId,
        label: label.trim() || `${providerId} key`,
        api_key: apiKey.trim(),
      });
      setSuccess("Key sealed with AES-256-GCM and bound to the router.");
      setApiKey("");
      setLabel("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to seal key");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="nexus-label" htmlFor="provider">
            Provider
          </label>
          <select
            id="provider"
            className="nexus-input"
            value={providerId}
            onChange={(event) => setProviderId(event.target.value)}
          >
            <option value="">Select a provider…</option>
            {providers.map((provider) => (
              <option key={provider.provider_id} value={provider.provider_id}>
                {provider.display_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="nexus-label" htmlFor="label">
            Label
          </label>
          <input
            id="label"
            className="nexus-input"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="e.g. production NIM key"
          />
        </div>
      </div>
      <div>
        <label className="nexus-label" htmlFor="apikey">
          API key (sealed at rest, never displayed again)
        </label>
        <input
          id="apikey"
          type="password"
          className="nexus-input font-mono"
          value={apiKey}
          minLength={8}
          onChange={(event) => setApiKey(event.target.value)}
          placeholder="nvapi-… / sk-…"
        />
      </div>
      {error && <ErrorNote message={error} />}
      {success && (
        <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
          {success}
        </p>
      )}
      <Button
        onClick={() => void submit()}
        loading={busy}
        disabled={!vaultUnlocked || !providerId || apiKey.trim().length < 8}
      >
        <ShieldPlus className="h-4 w-4" />
        Seal & register key
      </Button>
      {!vaultUnlocked && (
        <p className="text-xs text-amber-400">
          Unlock the vault above before registering keys.
        </p>
      )}
    </div>
  );
}
