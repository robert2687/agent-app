import { useState } from "react";
import { AlertTriangle, KeyRound, Lock, Unlock } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ErrorNote } from "@/components/ui/EmptyState";
import type { VaultStatus } from "@/types";

/** Header card summarizing vault state, with inline unlock/lock controls. */
export function VaultStatusBar({
  status,
  onChanged,
}: {
  status: VaultStatus | null;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const unlock = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.unlockVault(passphrase);
      setPassphrase("");
      setOpen(false);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unlock failed");
    } finally {
      setBusy(false);
    }
  };

  const lock = async () => {
    await api.lockVault().catch(() => undefined);
    onChanged();
  };

  const unlocked = status?.state === "unlocked";

  return (
    <div className="nexus-panel flex flex-wrap items-center justify-between gap-3 p-4">
      <div className="flex items-center gap-3">
        <div
          className={
            unlocked
              ? "flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-300"
              : "flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/15 text-amber-300"
          }
        >
          {unlocked ? <Unlock className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-200">
            Key Vault {unlocked ? "· Unlocked" : "· Locked"}
          </p>
          <p className="text-xs text-slate-500">
            {status
              ? `${status.kdf_algorithm.toUpperCase()} · ${status.pbkdf2_iterations.toLocaleString()} iterations · ${status.active_key_count}/${status.key_count} active keys`
              : "loading…"}
          </p>
        </div>
      </div>
      {unlocked ? (
        <Button variant="secondary" size="sm" onClick={() => void lock()}>
          <Lock className="h-3.5 w-3.5" /> Lock vault
        </Button>
      ) : (
        <Button size="sm" onClick={() => setOpen(true)}>
          <KeyRound className="h-3.5 w-3.5" /> Unlock vault
        </Button>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Unlock the key vault">
        <div className="space-y-4">
          <p className="text-xs leading-relaxed text-slate-400">
            The master passphrase is stretched through{" "}
            {status?.kdf_algorithm?.toUpperCase() ?? "PBKDF2"} into an AES-256-GCM
            key. Provider API keys are decrypted only in memory while unlocked.
          </p>
          <div>
            <label className="nexus-label" htmlFor="passphrase">
              Master passphrase
            </label>
            <input
              id="passphrase"
              type="password"
              className="nexus-input"
              value={passphrase}
              minLength={8}
              onChange={(event) => setPassphrase(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && passphrase.length >= 8) void unlock();
              }}
              placeholder="••••••••••••"
              autoFocus
            />
          </div>
          {error && <ErrorNote message={error} />}
          <div className="flex items-start gap-2 rounded-lg bg-amber-500/10 p-2.5">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
            <p className="text-[11px] leading-snug text-amber-300/90">
              Lost passphrases cannot be recovered — sealed keys become
              undecryptable. This matches the at-rest AES-256-GCM design.
            </p>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              loading={busy}
              disabled={passphrase.length < 8}
              onClick={() => void unlock()}
            >
              Derive key & unlock
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
