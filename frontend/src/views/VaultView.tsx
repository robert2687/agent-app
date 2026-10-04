import { api } from "@/api/client";
import { useApi } from "@/hooks/useApi";
import { Card } from "@/components/ui/Card";
import { VaultStatusBar } from "@/components/vault/VaultStatusBar";
import { ProviderKeyForm } from "@/components/vault/ProviderKeyForm";
import { ProviderKeyList } from "@/components/vault/ProviderKeyList";

export function VaultView() {
  const statusQuery = useApi(() => api.vaultStatus(), []);
  const keysQuery = useApi(() => api.listKeys(), []);
  const providersQuery = useApi(() => api.providerCatalog(), []);

  const refreshAll = () => {
    statusQuery.refresh();
    keysQuery.refresh();
    providersQuery.refresh();
  };

  const unlocked = statusQuery.data?.state === "unlocked";

  return (
    <div className="space-y-6">
      <VaultStatusBar status={statusQuery.data} onChanged={refreshAll} />

      <Card
        title="Register provider API key"
        subtitle="Sealed with AES-256-GCM (per-record salt + nonce, PBKDF2/Argon2 key derivation)"
      >
        <ProviderKeyForm
          providers={providersQuery.data?.providers ?? []}
          vaultUnlocked={unlocked}
          onCreated={refreshAll}
        />
      </Card>

      <Card
        title="Sealed keys"
        subtitle="Fingerprints only — plaintext never leaves the vault after sealing"
      >
        {keysQuery.error && (
          <p className="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
            {keysQuery.error}
          </p>
        )}
        <ProviderKeyList keys={keysQuery.data ?? []} onChanged={refreshAll} />
      </Card>
    </div>
  );
}
