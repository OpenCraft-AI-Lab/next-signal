import { SettingsView } from "@/components/settings/settings-view";
import { getCodingAgentSettings } from "@/lib/actions/coding-agent-settings";
import {
  getEmbeddingPrefill,
  getEmbeddingPreferences,
} from "@/lib/actions/embedding";
import { getEnginePreferences } from "@/lib/actions/engine";
import { getGbrainReadiness } from "@/lib/actions/knowledge-embedding";
import { getContentLanguage } from "@/lib/actions/language";
import { getSchedule, getScheduleStatus } from "@/lib/actions/schedule";
import { getCredentialPresence } from "@/lib/actions/secrets";
import { getCodingAgentAuthViews } from "@/lib/coding-agent-auth";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import { RADAR_TZ } from "@/lib/radar/queries";

export const dynamic = "force-dynamic";

/**
 * Every setting next-signal exposes, on one page.
 *
 * It replaced a nav popover: four sections stacked in a 22rem panel left the
 * engine section with nowhere to go, and a page is also the only place a
 * scrollable rail earns its keep. The nav gear now links here.
 *
 * All state resolves server-side, as it did in the popover, so the controls
 * paint their real values on first render with no fetch on mount.
 */
export default async function SettingsPage() {
  const [
    locale,
    contentLanguage,
    codingAgentSettings,
    codingAgentAuth,
    engine,
    embedding,
    embeddingPrefill,
    knowledgeEmbeddingReadiness,
    schedule,
    scheduleStatus,
    // Presence from the credential store, resolved server-side. Every
    // credential now has a fixed name, so this needs nothing from the embedding
    // state. Booleans cross to the client — never a value, in whole or in part.
    presence,
  ] = await Promise.all([
    getLocale(),
    getContentLanguage(),
    getCodingAgentSettings(),
    getCodingAgentAuthViews(),
    getEnginePreferences(),
    getEmbeddingPreferences(),
    getEmbeddingPrefill(),
    getGbrainReadiness(),
    getSchedule(),
    getScheduleStatus(),
    getCredentialPresence(),
  ]);
  const t = getDictionary(locale);

  return (
    <div className="page page-enter">
      <div className="shell">
        <div style={{ maxWidth: 980, margin: "0 auto" }}>
          <h1 className="page-title">{t.settings.heading}</h1>
          <p className="page-sub">{t.settings.subtitle}</p>
        </div>
        <SettingsView
          contentLanguage={contentLanguage}
          codingAgentSettings={codingAgentSettings}
          codingAgentAuth={codingAgentAuth}
          engine={engine}
          embedding={embedding}
          embeddingPrefill={embeddingPrefill}
          knowledgeEmbeddingReadiness={knowledgeEmbeddingReadiness}
          credentialPresence={presence}
          schedule={schedule}
          scheduleStatus={scheduleStatus}
          runtimeTimezone={RADAR_TZ}
        />
      </div>
    </div>
  );
}
