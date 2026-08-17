"use client";

import { Check, Cloud, Server } from "lucide-react";
import { useState, type ComponentType } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { PaneActions } from "@/components/settings/engine-section";
import { InlineCredential } from "@/components/settings/inline-credential";
import { SettingsSectionShell } from "@/components/settings/section-shell";
import { Input } from "@/components/ui/input";
import { initializeGbrain } from "@/lib/actions/knowledge-embedding";
import {
  KNOWLEDGE_EMBEDDING_PROVIDERS,
  knowledgeEmbeddingCredential,
  type GbrainReadiness,
  type KnowledgeEmbeddingProvider,
} from "@/lib/knowledge-embedding";
import { cn } from "@/lib/utils";

const GLYPHS: Record<KnowledgeEmbeddingProvider, ComponentType<{ size?: number }>> = {
  openai: Cloud,
  voyage: Cloud,
  google: Cloud,
  ollama: Server,
  lmstudio: Server,
  "llama-server": Server,
};

/**
 * GBrain's embedding provider for knowledge-base search — independent of the
 * Radar Embedding section, which configures a different embedder for a
 * different vector space entirely.
 *
 * `next-signal knowledge gbrain-init` sizes GBrain's Postgres schema to the
 * chosen model permanently and refuses a second run, so this section locks
 * in full the moment initialization succeeds — there is no unlock path
 * through this UI, matching the backend's own refusal to reconfigure.
 */
export function KnowledgeEmbeddingSection({
  initial,
  credentialPresence,
  onCredentialChange,
}: {
  initial: GbrainReadiness;
  credentialPresence: Record<string, boolean>;
  onCredentialChange: (name: string, present: boolean) => void;
}) {
  const { t } = useI18n();
  const [readiness, setReadiness] = useState<GbrainReadiness>(initial);
  const locked = readiness.provider !== null;
  const [open, setOpen] = useState<KnowledgeEmbeddingProvider>(
    (readiness.provider as KnowledgeEmbeddingProvider | null) ??
      KNOWLEDGE_EMBEDDING_PROVIDERS[0],
  );

  const NAMES: Record<KnowledgeEmbeddingProvider, string> = {
    openai: t.settings.knowledgeEmbeddingOpenai,
    voyage: t.settings.knowledgeEmbeddingVoyage,
    google: t.settings.knowledgeEmbeddingGoogle,
    ollama: t.settings.knowledgeEmbeddingOllama,
    lmstudio: t.settings.knowledgeEmbeddingLmstudio,
    "llama-server": t.settings.knowledgeEmbeddingLlamaServer,
  };

  const statusLabel = (state: GbrainReadiness["state"]) => {
    switch (state) {
      case "ready":
        return t.settings.knowledgeEmbeddingStatusReady;
      case "credential_missing":
        return t.settings.knowledgeEmbeddingStatusCredentialMissing;
      case "indeterminate":
        return t.settings.knowledgeEmbeddingStatusIndeterminate;
      default:
        return t.settings.knowledgeEmbeddingStatusNotInitialized;
    }
  };

  const choose = (provider: KnowledgeEmbeddingProvider) => {
    if (locked) return;
    setOpen(provider);
  };

  /**
   * The one write this section ever makes: confirm the permanent choice, run
   * `gbrain-init`, and — only on success — lock the section. A failure
   * (including "already initialised") leaves it unlocked and unselected.
   */
  const initializeAndLock = async (
    provider: KnowledgeEmbeddingProvider,
    model: string,
  ) => {
    if (!window.confirm(t.settings.knowledgeEmbeddingConfirmPermanent)) return;
    const result = await initializeGbrain(provider, model);
    if (!result.ok) {
      throw new Error(result.message || t.settings.knowledgeEmbeddingInitFailed);
    }
    const credentialName = knowledgeEmbeddingCredential(provider);
    setReadiness({
      state: credentialName && !credentialPresence[credentialName] ? "credential_missing" : "ready",
      provider,
      model,
    });
    setOpen(provider);
  };

  const summary =
    readiness.provider === null ? (
      <span className="set-status idle">{statusLabel(readiness.state)}</span>
    ) : (
      <span className={`set-status ${readiness.state === "ready" ? "ok" : "warn"}`}>
        <span className="dot" />
        {NAMES[readiness.provider as KnowledgeEmbeddingProvider]} · {readiness.model} ·{" "}
        {statusLabel(readiness.state)}
      </span>
    );

  return (
    <SettingsSectionShell
      id="knowledge-embedding"
      label={t.settings.knowledgeEmbedding}
      hint={t.settings.knowledgeEmbeddingHint}
      summary={summary}
    >
      {!locked && (
        <p className="set-note">{t.settings.knowledgeEmbeddingUnselectedHint}</p>
      )}
      {locked && (
        <p className="set-note">{t.settings.knowledgeEmbeddingLockedHint}</p>
      )}

      <div className="set-engines">
        {KNOWLEDGE_EMBEDDING_PROVIDERS.map((provider) => {
          const Glyph = GLYPHS[provider];
          const active = readiness.provider === provider;
          const selectable = !locked || active;
          return (
            <button
              key={provider}
              type="button"
              aria-pressed={active}
              aria-disabled={!selectable}
              disabled={locked && !active}
              className={cn(
                "set-engine",
                active && "on",
                open === provider && !active && "set-engineopen",
              )}
              onClick={() => choose(provider)}
            >
              <div className="set-enginetop">
                <div className="set-engineid">
                  <span className="set-engineglyph">
                    <Glyph size={15} />
                  </span>
                  <span className="col">
                    <span className="set-enginename">{NAMES[provider]}</span>
                    <span className="set-enginekind">
                      {knowledgeEmbeddingCredential(provider)
                        ? t.settings.knowledgeEmbeddingKindHosted
                        : t.settings.knowledgeEmbeddingKindLocal}
                    </span>
                  </span>
                </div>
                <span className="set-check">
                  <Check size={10} strokeWidth={3.5} />
                </span>
              </div>
              {active && (
                <div className="row gap-8" style={{ justifyContent: "space-between" }}>
                  <span className={`set-status ${readiness.state === "ready" ? "ok" : "warn"}`}>
                    <span className="dot" />
                    {statusLabel(readiness.state)}
                  </span>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="set-detail">
        <div className="set-detailhead">
          <span className="eyebrow">{NAMES[open]}</span>
        </div>
        <KnowledgeEmbeddingPane
          provider={open}
          hasKey={
            (() => {
              const name = knowledgeEmbeddingCredential(open);
              return name ? Boolean(credentialPresence[name]) : true;
            })()
          }
          onKeyChange={(present) => {
            const name = knowledgeEmbeddingCredential(open);
            if (name) onCredentialChange(name, present);
          }}
          locked={locked}
          onSave={(model) => initializeAndLock(open, model)}
        />
      </div>
    </SettingsSectionShell>
  );
}

function KnowledgeEmbeddingPane({
  provider,
  hasKey,
  onKeyChange,
  locked,
  onSave,
}: {
  provider: KnowledgeEmbeddingProvider;
  hasKey: boolean;
  onKeyChange: (present: boolean) => void;
  locked: boolean;
  onSave: (model: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const credentialName = knowledgeEmbeddingCredential(provider);

  const save = async () => {
    setSaving(true);
    try {
      await onSave(value);
      toast.success(t.settings.knowledgeEmbeddingSaved);
    } catch (err) {
      // Shows the backend's actual message (e.g. "already initialised with
      // X") rather than a generic failure — that specific text is the reason
      // this pane doesn't reuse the shared `usePaneSave` helper.
      console.error("failed to initialize GBrain", err);
      toast.error(err instanceof Error ? err.message : t.settings.knowledgeEmbeddingInitFailed);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="set-form">
        <label htmlFor="knowledge-embedding-model">{t.settings.knowledgeEmbeddingModel}</label>
        <Input
          id="knowledge-embedding-model"
          className="mono"
          value={value}
          disabled={locked}
          placeholder="text-embedding-3-large"
          onChange={(e) => setValue(e.target.value)}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        {credentialName ? (
          <InlineCredential
            name={credentialName}
            label={credentialName}
            present={hasKey}
            onChange={onKeyChange}
            disabled={locked}
          />
        ) : null}
      </div>
      <p className="set-note">{t.settings.knowledgeEmbeddingModelHint}</p>
      <p className="set-note">
        {credentialName
          ? t.settings.knowledgeEmbeddingCredentialHint
          : t.settings.knowledgeEmbeddingLocalHint}
      </p>
      {!locked && <p className="set-note">{t.settings.knowledgeEmbeddingSaveToInitHint}</p>}
      {!locked && (
        <PaneActions
          dirty={Boolean(value.trim())}
          saving={saving}
          canSave={Boolean(value.trim() && (!credentialName || hasKey))}
          onSave={() => void save()}
          onReset={() => setValue("")}
        />
      )}
    </>
  );
}
