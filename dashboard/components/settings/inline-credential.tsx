"use client";

import { useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { deleteCredential, saveCredential } from "@/lib/actions/secrets";

/**
 * One credential's input, inline inside the functional section that consumes
 * it — the entry point every section now owns for itself, replacing the flat
 * Credentials section's shared input.
 *
 * Write-only, same as before centralization: a saved value is never held in
 * client state after the write, and no masked preview is ever rendered.
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
    <>
      <label htmlFor={`cred-${name}`}>{label}</label>
      <span className="row gap-8">
        <Input
          id={`cred-${name}`}
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={value}
          disabled={busy || disabled}
          aria-label={label}
          placeholder={
            present ? t.settings.credentialReplace : t.settings.credentialEnter
          }
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void save();
          }}
        />
        <span className={`set-status ${present ? "ok" : "warn"}`}>
          {present ? t.settings.credentialSet : t.settings.credentialUnset}
        </span>
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
      </span>
    </>
  );
}
