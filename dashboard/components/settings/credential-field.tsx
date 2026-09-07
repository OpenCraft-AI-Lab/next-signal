"use client";

import type { ReactNode } from "react";

import { useI18n } from "@/components/i18n-provider";
import { Input } from "@/components/ui/input";

/**
 * One credential's masked input plus its presence status badge. Purely
 * controlled — no save/clear of its own, no local value state — so a caller
 * can fold the typed value into a larger draft it commits on its own
 * schedule. `InlineCredential` builds its immediate-save behavior on top of
 * this for the one case that still wants it (a credential with no
 * section-level commit to fold into).
 */
export function CredentialField({
  name,
  label,
  value,
  onValueChange,
  present,
  disabled,
  onEnter,
  actions,
}: {
  name: string;
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  present: boolean;
  disabled?: boolean;
  onEnter?: () => void;
  /** Extra controls in the same row, e.g. `InlineCredential`'s own Save/Clear. */
  actions?: ReactNode;
}) {
  const { t } = useI18n();
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
          disabled={disabled}
          aria-label={label}
          placeholder={
            present ? t.settings.credentialReplace : t.settings.credentialEnter
          }
          onChange={(e) => onValueChange(e.target.value)}
          onKeyDown={
            onEnter
              ? (e) => {
                  if (e.key === "Enter") onEnter();
                }
              : undefined
          }
        />
        <span className={`set-status ${present ? "ok" : "warn"}`}>
          {present ? t.settings.credentialSet : t.settings.credentialUnset}
        </span>
        {actions}
      </span>
    </>
  );
}
