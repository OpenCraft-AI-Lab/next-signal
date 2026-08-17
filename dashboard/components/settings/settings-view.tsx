"use client";

import { Clock, Cpu, Database, KeyRound, Languages, Rss, Waypoints } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/components/i18n-provider";
import { CredentialsSection } from "@/components/settings/credentials-section";
import { EmbeddingSection } from "@/components/settings/embedding-section";
import { EngineSection } from "@/components/settings/engine-section";
import { KnowledgeEmbeddingSection } from "@/components/settings/knowledge-embedding-section";
import { LanguageSection } from "@/components/settings/language-section";
import { RssSection } from "@/components/settings/rss-section";
import { ScheduleSection } from "@/components/settings/schedule-section";
import type { EmbeddingPrefill } from "@/lib/actions/embedding";
import type { GbrainReadiness } from "@/lib/knowledge-embedding";
import type { Schedule, ScheduleStatus } from "@/lib/actions/schedule";
import type {
  CodingAgentAuthProvider,
  CodingAgentAuthView,
} from "@/lib/coding-agent-auth-types";
import type { CodingAgentSettings } from "@/lib/coding-agent-preferences";
import type { EmbeddingPreferences } from "@/lib/embedding-preferences";
import type { EnginePreferences } from "@/lib/engine-preferences";
import type { Locale } from "@/lib/i18n/dictionaries";
import type { CredentialPresence } from "@/lib/secrets";
import { cn } from "@/lib/utils";

const SECTIONS = [
  "language",
  "schedule",
  "engine",
  "embedding",
  "knowledge-embedding",
  "rss",
  "credentials",
] as const;
type SectionId = (typeof SECTIONS)[number];

/**
 * The settings page's shell: a sticky rail of anchors beside the sections.
 *
 * ## Persistence contract
 *
 * Inherited from the popover this replaced, because it is a property of the
 * control rather than of the container:
 *
 * - **Discrete choice** (segmented: language, on/off, skip/catch-up, engine
 *   parallelism) — the click is the commit. One interaction is already a
 *   complete, valid intent, so a Save button would be pure ceremony.
 * - **Typed value** (a schedule time) — a keystroke is *not* a commit. A native
 *   time input emits a complete value per segment edit, so persisting every
 *   change would publish half-typed times; it commits on blur/Enter.
 * - **Interdependent group** (an engine's model + effort, where a partial
 *   combination is invalid and cannot be sent) — commit is an explicit Save.
 * - **A section's own primary selection** (which engine is primary, which
 *   embedder is selected) — also an explicit commit, not commit-on-click:
 *   picking a card only proposes it, and an Apply/Save action is what writes
 *   it, unlike the plain discrete choices above.
 *
 * Either way a successful write is acknowledged with a toast and a failed one
 * rolls the control back: an optimistic control moves whether or not the write
 * landed, so without the acknowledgement "did that save?" has no answer.
 */
export function SettingsView({
  contentLanguage,
  codingAgentSettings,
  codingAgentAuth,
  engine,
  embedding,
  embeddingPrefill,
  knowledgeEmbeddingReadiness,
  credentialPresence: initialCredentialPresence,
  schedule,
  scheduleStatus,
  runtimeTimezone,
}: {
  contentLanguage: Locale;
  codingAgentSettings: CodingAgentSettings;
  codingAgentAuth: Record<CodingAgentAuthProvider, CodingAgentAuthView>;
  engine: EnginePreferences;
  embedding: EmbeddingPreferences;
  embeddingPrefill: EmbeddingPrefill;
  knowledgeEmbeddingReadiness: GbrainReadiness;
  credentialPresence: CredentialPresence;
  schedule: Schedule;
  scheduleStatus: ScheduleStatus;
  runtimeTimezone: string;
}) {
  const { t } = useI18n();
  const [active, setActive] = useState<SectionId>("language");
  const visible = useRef<Partial<Record<SectionId, boolean>>>({});

  // The one place credential presence lives on the client. Every section that
  // owns a credential reads its own name out of this map and reports back
  // through `onCredentialChange` on save/clear — so a save in, say, the
  // Engine section's DeepSeek pane is reflected immediately in that pane,
  // the Engine card's status badge, and the read-only summary at the bottom,
  // all three, without a page reload. Before this, each of those read a
  // separate, server-resolved-once value that never moved after first paint.
  const [credentialPresence, setCredentialPresence] =
    useState<CredentialPresence>(initialCredentialPresence);
  const onCredentialChange = (name: string, present: boolean) =>
    setCredentialPresence((p) => ({ ...p, [name]: present }));

  useEffect(() => {
    // Track the whole intersecting set and highlight the topmost member.
    // Toggling per entry instead lets whichever callback fired last win, which
    // on first paint is the *second* section — the rail would open pointing at
    // the wrong place.
    const spy = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          visible.current[entry.target.id as SectionId] = entry.isIntersecting;
        }
        setActive(SECTIONS.find((id) => visible.current[id]) ?? SECTIONS[0]);
      },
      { rootMargin: "-76px 0px -60% 0px" },
    );
    for (const id of SECTIONS) {
      const node = document.getElementById(id);
      if (node) spy.observe(node);
    }
    return () => spy.disconnect();
  }, []);

  const rail: [SectionId, string, typeof Clock][] = [
    ["language", t.settings.railLanguage, Languages],
    ["schedule", t.settings.railSchedule, Clock],
    ["engine", t.settings.railEngine, Cpu],
    ["embedding", t.settings.railRadarEmbedding, Waypoints],
    ["knowledge-embedding", t.settings.railKnowledgeEmbedding, Database],
    ["rss", t.settings.railRss, Rss],
    ["credentials", t.settings.railCredentials, KeyRound],
  ];

  return (
    <div className="set-grid">
      <div className="set-rail">
        {rail.map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            className={cn("set-railitem", active === id && "on")}
            onClick={() =>
              document
                .getElementById(id)
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      <div className="set-sections">
        <LanguageSection initial={contentLanguage} />
        <ScheduleSection
          initial={schedule}
          status={scheduleStatus}
          runtimeTimezone={runtimeTimezone}
        />
        <EngineSection
          initial={engine}
          codingAgents={codingAgentSettings}
          codingAgentAuth={codingAgentAuth}
          credentialPresence={credentialPresence}
          onCredentialChange={onCredentialChange}
        />
        <EmbeddingSection
          initial={embedding}
          prefill={embeddingPrefill}
          credentialPresence={credentialPresence}
          onCredentialChange={onCredentialChange}
        />
        <KnowledgeEmbeddingSection
          initial={knowledgeEmbeddingReadiness}
          credentialPresence={credentialPresence}
          onCredentialChange={onCredentialChange}
        />
        <RssSection
          credentialPresence={credentialPresence}
          onCredentialChange={onCredentialChange}
        />
        <CredentialsSection presence={credentialPresence} />
      </div>
    </div>
  );
}
