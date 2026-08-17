"use client";

import { useI18n } from "@/components/i18n-provider";
import { SettingsSectionShell } from "@/components/settings/section-shell";
import { CREDENTIAL_NAMES, type CredentialPresence } from "@/lib/secrets";

/**
 * A read-only, presence-only summary of every credential the sections above
 * resolve. No longer an input surface — a credential is entered inline in
 * the functional section that consumes it (Engine, Radar Embedding,
 * Knowledge Embedding, RSS). This exists so an operator can see the whole
 * configured surface at a glance without hunting through sections. Collapsed
 * by default like every other section — an operator who has already set
 * everything up inline has no ongoing reason to look at this list.
 */
export function CredentialsSection({
  presence,
}: {
  presence: CredentialPresence;
}) {
  const { t } = useI18n();
  const setCount = CREDENTIAL_NAMES.filter((name) => presence[name]).length;

  return (
    <SettingsSectionShell
      id="credentials"
      label={t.settings.credentials}
      hint={t.settings.credentialsHint}
      summary={
        <span className={`set-status ${setCount === CREDENTIAL_NAMES.length ? "ok" : "idle"}`}>
          {t.settings.credentialsSummary(setCount, CREDENTIAL_NAMES.length)}
        </span>
      }
    >
      {CREDENTIAL_NAMES.map((name) => {
        const present = presence[name] ?? false;
        return (
          <div className="set-row" key={name}>
            <div className="set-rowtext">
              <span className="set-label">{name}</span>
              <span className="set-hint">{t.settings.credentialPowers[name]}</span>
            </div>
            <div className="set-rowctl">
              <span className={`set-status ${present ? "ok" : "warn"}`}>
                <span className="dot" />
                {present ? t.settings.credentialSet : t.settings.credentialUnset}
              </span>
            </div>
          </div>
        );
      })}
    </SettingsSectionShell>
  );
}
