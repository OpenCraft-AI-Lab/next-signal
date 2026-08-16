"use client";

import { Check, Cloud, Server, Share2 } from "lucide-react";
import { useState, type ComponentType } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import {
  PaneActions,
  usePaneSave,
} from "@/components/settings/engine-section";
import { Input } from "@/components/ui/input";
import type { EmbeddingPrefill } from "@/lib/actions/embedding";
import { setEmbeddingPreferences } from "@/lib/actions/embedding";
import {
  EMBEDDING_PROVIDERS,
  embedderIdentity,
  type EmbeddingPreferences,
  type EmbeddingProvider,
  type OmlxEmbeddingSettings,
  type OpenAICompatibleEmbeddingSettings,
  type OpenAIEmbeddingSettings,
} from "@/lib/embedding-preferences";
import { cn } from "@/lib/utils";

const GLYPHS: Record<EmbeddingProvider, ComponentType<{ size?: number }>> = {
  omlx: Server,
  openai: Cloud,
  openai_compatible: Share2,
};

/**
 * Which embedder the info-radar dedup gate resolves for each item.
 *
 * Reuses the engine section's cards, panes, and status vocabulary because the
 * interaction is the same one — but the consequence is not. Switching an LLM
 * engine changes who answers a question; switching an embedder changes the
 * vector space, which parks every topic memorised under the old identity until
 * the operator switches back. That is why a switch is confirmed rather than
 * committed on click, and why the exact active identity is displayed verbatim.
 *
 * Nothing is selected on a fresh install. There is no provider this repo could
 * honestly pick on someone's behalf — the local one needs an address only they
 * know, the hosted ones need a key and spend money — so every card starts
 * unselected, panes open prefilled with suggestions, and the section says
 * plainly that deduplication is off until one is chosen. All three cards behave
 * identically: a card commits only once its section is complete.
 */
export function EmbeddingSection({
  initial,
  prefill,
  openAiKey,
  compatibleKey,
}: {
  initial: EmbeddingPreferences;
  prefill: EmbeddingPrefill;
  openAiKey: boolean;
  compatibleKey: boolean;
}) {
  const { t } = useI18n();
  const [saved, setSaved] = useState<EmbeddingPreferences>(initial);
  // Which pane is open. Starts on the saved provider, or the local card when
  // nothing is chosen — an open pane is an invitation, not a selection.
  const [open, setOpen] = useState<EmbeddingProvider>(initial.provider ?? "omlx");

  const NAMES: Record<EmbeddingProvider, string> = {
    omlx: t.settings.embeddingOmlx,
    openai: t.settings.embeddingOpenai,
    openai_compatible: t.settings.embeddingCompatible,
  };
  const KINDS: Record<EmbeddingProvider, string> = {
    omlx: t.settings.engineKindLocal,
    openai: t.settings.engineKindCloud,
    openai_compatible: t.settings.embeddingKindEndpoint,
  };

  const section = (provider: EmbeddingProvider) =>
    provider === "omlx"
      ? saved.omlx
      : provider === "openai"
        ? saved.openai
        : saved.openaiCompatible;

  /** A card can only be selected once its own settings have been saved. */
  const configured = (provider: EmbeddingProvider) => section(provider) !== null;

  const cardState = (provider: EmbeddingProvider) => {
    if (!configured(provider)) {
      return { tone: "idle", label: t.settings.engineStatusUnset, meta: "—" };
    }
    if (provider === "omlx") {
      // A local server usually has no key at all, so the endpoint it was saved
      // with is the whole story.
      return {
        tone: "ok",
        label: t.settings.engineStatusConfigured,
        meta: saved.omlx!.model,
      };
    }
    const hasKey = provider === "openai" ? openAiKey : compatibleKey;
    return {
      tone: hasKey ? "ok" : "warn",
      label: hasKey
        ? t.settings.engineStatusKeySet
        : t.settings.engineStatusNoKey,
      meta:
        provider === "openai"
          ? saved.openai!.model
          : saved.openaiCompatible!.spaceId,
    };
  };

  const commit = async (next: EmbeddingPreferences) => {
    const previous = saved;
    setSaved(next); // optimistic
    try {
      await setEmbeddingPreferences(next);
      toast.success(t.settings.embeddingSaved);
    } catch (err) {
      console.error("failed to update embedding preferences", err);
      setSaved(previous);
      toast.error(t.settings.saveFailed);
    }
  };

  /**
   * Confirm before changing which vector space new items land in.
   *
   * Unconditional rather than conditioned on whether stored vectors exist: a
   * database read to choose between two wordings buys accuracy nobody acts on,
   * and the consequence is worth stating either way.
   */
  const confirmSwitch = (provider: EmbeddingProvider) =>
    saved.provider === null ||
    saved.provider === provider ||
    window.confirm(t.settings.embeddingSwitchConfirm);

  const choose = (provider: EmbeddingProvider) => {
    setOpen(provider);
    // An unconfigured card has nothing valid to select, so it only opens its
    // pane and writes nothing. Its Save is the commit instead.
    if (provider === saved.provider || !configured(provider)) return;
    if (!confirmSwitch(provider)) return;
    void commit({ ...saved, provider });
  };

  /** Saving a pane stores its settings and selects that provider. */
  const saveAndSelect = async (
    provider: EmbeddingProvider,
    next: EmbeddingPreferences,
  ) => {
    if (!confirmSwitch(provider)) return;
    const selected = { ...next, provider };
    await setEmbeddingPreferences(selected);
    setSaved(selected);
  };

  const identity = embedderIdentity(saved);

  return (
    <section className="card pad set-card" id="embedding">
      <div className="set-row" style={{ marginBottom: 12 }}>
        <div className="set-rowtext">
          <span className="set-label">{t.settings.embedding}</span>
          <span className="set-hint">{t.settings.embeddingHint}</span>
        </div>
      </div>

      {saved.provider === null && (
        <p className="set-note">{t.settings.embeddingUnselectedHint}</p>
      )}

      <div className="set-engines">
        {EMBEDDING_PROVIDERS.map((provider) => {
          const Glyph = GLYPHS[provider];
          const state = cardState(provider);
          const active = saved.provider === provider;
          return (
            <button
              key={provider}
              type="button"
              aria-pressed={active}
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
                    <span className="set-enginekind">{KINDS[provider]}</span>
                  </span>
                </div>
                <span className="set-check">
                  <Check size={10} strokeWidth={3.5} />
                </span>
              </div>
              <div
                className="row gap-8"
                style={{ justifyContent: "space-between" }}
              >
                <span className="set-enginemeta">{state.meta}</span>
                <span className={`set-status ${state.tone}`}>
                  <span className="dot" />
                  {state.label}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      <div className="set-detail">
        <div className="set-detailhead">
          <span className="eyebrow">{NAMES[open]}</span>
        </div>

        {open === "omlx" && (
          <OmlxEmbeddingPane
            initial={
              saved.omlx ?? { baseUrl: "", model: prefill.omlxModel }
            }
            configured={saved.omlx !== null}
            onSave={(omlx) => saveAndSelect("omlx", { ...saved, omlx })}
          />
        )}
        {open === "openai" && (
          <OpenAIEmbeddingPane
            initial={saved.openai ?? { model: prefill.openaiModel }}
            hasKey={openAiKey}
            configured={saved.openai !== null}
            onSave={(openai) => saveAndSelect("openai", { ...saved, openai })}
          />
        )}
        {open === "openai_compatible" && (
          <CompatibleEmbeddingPane
            initial={
              saved.openaiCompatible ?? { baseUrl: "", model: "", spaceId: "" }
            }
            hasKey={compatibleKey}
            configured={saved.openaiCompatible !== null}
            onSave={(openaiCompatible) =>
              saveAndSelect("openai_compatible", { ...saved, openaiCompatible })
            }
          />
        )}
      </div>

      <div className="set-sub set-row">
        <div className="set-rowtext">
          <span className="set-label">{t.settings.embeddingIdentity}</span>
          <span className="set-hint">{t.settings.embeddingIdentityHint}</span>
        </div>
        <div className="set-rowctl">
          <span className="mono">
            {identity ?? t.settings.embeddingIdentityNone}
          </span>
        </div>
      </div>

      <p className="set-note">{t.settings.embeddingSwitchHint}</p>
      <p className="set-note">{t.settings.embeddingLegacyHint}</p>
    </section>
  );
}

function OmlxEmbeddingPane({
  initial,
  configured,
  onSave,
}: {
  initial: OmlxEmbeddingSettings;
  configured: boolean;
  onSave: (value: OmlxEmbeddingSettings) => Promise<void>;
}) {
  const { t } = useI18n();
  const { saved, value, setValue, saving, save, reset } = usePaneSave(
    initial,
    onSave,
    t.settings.embeddingSaved,
  );

  return (
    <>
      <div className="set-form">
        <label htmlFor="embedding-omlx-url">{t.settings.embeddingBaseUrl}</label>
        <Input
          id="embedding-omlx-url"
          className="mono"
          value={value.baseUrl}
          placeholder="http://host.docker.internal:8081/v1"
          onChange={(e) => setValue({ ...value, baseUrl: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <label htmlFor="embedding-omlx-model">{t.settings.omlxModel}</label>
        <Input
          id="embedding-omlx-model"
          className="mono"
          value={value.model}
          onChange={(e) => setValue({ ...value, model: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
      </div>
      <p className="set-note">{t.settings.embeddingOmlxEndpointHint}</p>
      <p className="set-note">{t.settings.embeddingOmlxHint}</p>
      {!configured && <p className="set-note">{t.settings.embeddingSaveToSelectHint}</p>}
      <PaneActions
        dirty={value.baseUrl !== saved.baseUrl || value.model !== saved.model}
        saving={saving}
        canSave={Boolean(value.baseUrl.trim() && value.model.trim())}
        onSave={() => void save()}
        onReset={reset}
      />
    </>
  );
}

function OpenAIEmbeddingPane({
  initial,
  hasKey,
  configured,
  onSave,
}: {
  initial: OpenAIEmbeddingSettings;
  hasKey: boolean;
  configured: boolean;
  onSave: (value: OpenAIEmbeddingSettings) => Promise<void>;
}) {
  const { t } = useI18n();
  const { saved, value, setValue, saving, save, reset } = usePaneSave(
    initial,
    onSave,
    t.settings.embeddingSaved,
  );

  return (
    <>
      <div className="set-form">
        <label htmlFor="embedding-openai-model">{t.settings.omlxModel}</label>
        <Input
          id="embedding-openai-model"
          className="mono"
          value={value.model}
          onChange={(e) => setValue({ model: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        {!hasKey && (
          <div className="set-formwide">
            <span className="badge amber">
              <span className="dot" />
              {t.settings.engineStatusNoKey}
            </span>
          </div>
        )}
      </div>
      <p className="set-note">{t.settings.embeddingHostedHint}</p>
      <p className="set-note">{t.settings.embeddingOpenaiKeyHint}</p>
      <p className="set-note">{t.settings.embeddingWidthHint}</p>
      {!configured && <p className="set-note">{t.settings.embeddingSaveToSelectHint}</p>}
      <PaneActions
        dirty={value.model !== saved.model}
        saving={saving}
        canSave={Boolean(value.model.trim())}
        onSave={() => void save()}
        onReset={reset}
      />
    </>
  );
}

function CompatibleEmbeddingPane({
  initial,
  hasKey,
  configured,
  onSave,
}: {
  initial: OpenAICompatibleEmbeddingSettings;
  hasKey: boolean;
  configured: boolean;
  onSave: (value: OpenAICompatibleEmbeddingSettings) => Promise<void>;
}) {
  const { t } = useI18n();
  const { saved, value, setValue, saving, save, reset } = usePaneSave(
    initial,
    onSave,
    t.settings.embeddingSaved,
  );
  const dirty =
    value.baseUrl !== saved.baseUrl ||
    value.model !== saved.model ||
    value.spaceId !== saved.spaceId;

  return (
    <>
      <div className="set-form">
        <label htmlFor="embedding-compatible-url">
          {t.settings.embeddingBaseUrl}
        </label>
        <Input
          id="embedding-compatible-url"
          className="mono"
          value={value.baseUrl}
          placeholder="https://host.example/v1"
          onChange={(e) => setValue({ ...value, baseUrl: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <label htmlFor="embedding-compatible-model">
          {t.settings.omlxModel}
        </label>
        <Input
          id="embedding-compatible-model"
          className="mono"
          value={value.model}
          onChange={(e) => setValue({ ...value, model: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <label htmlFor="embedding-compatible-space">
          {t.settings.embeddingSpaceId}
        </label>
        <Input
          id="embedding-compatible-space"
          className="mono"
          value={value.spaceId}
          onChange={(e) => setValue({ ...value, spaceId: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        {configured && !hasKey && (
          <div className="set-formwide">
            <span className="badge amber">
              <span className="dot" />
              {t.settings.engineStatusNoKey}
            </span>
          </div>
        )}
      </div>
      <p className="set-note">{t.settings.embeddingBaseUrlHint}</p>
      <p className="set-note">{t.settings.embeddingCompatibleKeyHint}</p>
      <p className="set-note">{t.settings.embeddingSpaceIdHint}</p>
      <p className="set-note">{t.settings.embeddingHostedHint}</p>
      <p className="set-note">{t.settings.embeddingWidthHint}</p>
      {!configured && (
        <p className="set-note">{t.settings.embeddingCompatibleSaveHint}</p>
      )}
      <PaneActions
        dirty={dirty}
        saving={saving}
        // No inherit path: a partial endpoint cannot be sent anywhere.
        canSave={Boolean(
          value.baseUrl.trim() && value.model.trim() && value.spaceId.trim(),
        )}
        onSave={() => void save()}
        onReset={reset}
      />
    </>
  );
}
