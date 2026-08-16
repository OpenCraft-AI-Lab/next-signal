import { SettingsView } from "@/components/settings/settings-view";
import { getCodingAgentSettings } from "@/lib/actions/coding-agent-settings";
import { getEmbeddingPreferences } from "@/lib/actions/embedding";
import { getEnginePreferences } from "@/lib/actions/engine";
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
    schedule,
    scheduleStatus,
  ] = await Promise.all([
    getLocale(),
    getContentLanguage(),
    getCodingAgentSettings(),
    getCodingAgentAuthViews(),
    getEnginePreferences(),
    getEmbeddingPreferences(),
    getSchedule(),
    getScheduleStatus(),
  ]);
  const t = getDictionary(locale);
  // Presence from the credential store, resolved server-side. The custom
  // embedding endpoint names its own credential, so which extra name to report
  // is only knowable after reading the saved embedding state. Booleans cross to
  // the client — never a value, in whole or in part.
  const presence = await getCredentialPresence(
    embedding.openaiCompatible ? [embedding.openaiCompatible.apiKeyEnv] : [],
  );
  const deepSeekKey = presence.DEEPSEEK_API_KEY;
  const openAiKey = presence.OPENAI_API_KEY;
  const embeddingCompatibleKey = Boolean(
    embedding.openaiCompatible &&
      presence[embedding.openaiCompatible.apiKeyEnv],
  );

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
          deepSeekKey={deepSeekKey}
          embedding={embedding}
          openAiKey={openAiKey}
          embeddingCompatibleKey={embeddingCompatibleKey}
          credentialPresence={presence}
          schedule={schedule}
          scheduleStatus={scheduleStatus}
          runtimeTimezone={RADAR_TZ}
        />
      </div>
    </div>
  );
}
