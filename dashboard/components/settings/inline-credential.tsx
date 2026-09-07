"use client";

import { useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { CredentialField } from "@/components/settings/credential-field";
import { Button } from "@/components/ui/button";
import { deleteCredential, saveCredential } from "@/lib/actions/secrets";

/**
 * One credential's input, inline inside the functional section that consumes
 * it — the entry point every section now owns for itself, replacing the flat
 * Credentials section's shared input.
 *
 * Write-only, same as before centralization: a saved value is never held in
 * client state after the write, and no masked preview is ever rendered.
 *
 * Saves and clears immediately, independent of anything else in its section —
 * only right for a credential with no section-level commit to fold into
 * (RSS/Folo's token today). A credential that lives inside a section with its
 * own single commit action uses `CredentialField` directly instead, so its
 * value joins that section's draft rather than writing on its own.
 */
export function InlineCredential({
  name,
  label,
  present,
  onChange,
  disabled,
}: {
  name: string;
  label: string;
  present: boolean;
  onChange: (present: boolean) => void;
  /** Once a locked section renders read-only, this input locks with it. */
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    const trimmed = value.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      await saveCredential(name, trimmed);
      setValue("");
      onChange(true);
      toast.success(t.settings.credentialSaved);
    } catch (err) {
      console.error(`failed to save ${name}`, err);
      toast.error(t.settings.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await deleteCredential(name);
      onChange(false);
      toast.success(t.settings.credentialCleared);
    } catch (err) {
      console.error(`failed to clear ${name}`, err);
      toast.error(t.settings.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <CredentialField
      name={name}
      label={label}
      value={value}
      onValueChange={setValue}
      present={present}
      disabled={busy || disabled}
      onEnter={() => void save()}
      actions={
        <>
          <Button
            type="button"
            size="sm"
            disabled={busy || disabled || !value.trim()}
            onClick={() => void save()}
          >
            {t.settings.credentialSave}
          </Button>
          {present && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={busy || disabled}
              onClick={() => void clear()}
            >
              {t.settings.credentialClear}
            </Button>
          )}
        </>
      }
    />
  );
}
