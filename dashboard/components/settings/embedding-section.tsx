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

/** A blank draft for a section that has never been saved. Never written. */
const BLANK_COMPATIBLE: OpenAICompatibleEmbeddingSettings = {
  baseUrl: "",
  model: "",
  apiKeyEnv: "",
  spaceId: "",
};

/**
 * Which embedder the info-radar dedup gate resolves for each item.
 *
 * Reuses the engine section's cards, panes, and status vocabulary because the
 * interaction is the same one — but the consequence is not. Switching an LLM
 * engine changes who answers a question; switching an embedder changes the
 * vector space, which parks every topic memorised under the old identity until
 * the operator switches back. The notes below say so before the click, and the
 * exact active identity is displayed verbatim.
 *
 * One asymmetry with the engine section: `openai_compatible` has no baseline
 * anywhere in the repo, so its card cannot commit a selection on click until its
 * four fields have been saved. Until then the card only opens its pane.
 */
export function EmbeddingSection({
  initial,
  openAiKey,
  compatibleKey,
}: {
  initial: EmbeddingPreferences;
  openAiKey: boolean;
  compatibleKey: boolean;
}) {
  const { t } = useI18n();
  const [saved, setSaved] = useState<EmbeddingPreferences>(initial);
  const [selected, setSelected] = useState<EmbeddingProvider>(initial.provider);

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

  /** Only the generic provider can be present-but-unusable. */
  const configured = (provider: EmbeddingProvider) =>
    provider !== "openai_compatible" || saved.openaiCompatible !== null;

  const cardState = (provider: EmbeddingProvider) => {
    switch (provider) {
      case "omlx":
        return {
          tone: "ok",
          label: t.settings.engineStatusConfigured,
          meta: saved.omlx.model,
        };
      case "openai":
        return {
          tone: openAiKey ? "ok" : "warn",
          label: openAiKey
            ? t.settings.engineStatusKeySet
            : t.settings.engineStatusNoKey,
          meta: saved.openai.model,
        };
      case "openai_compatible":
        if (!saved.openaiCompatible) {
          return {
            tone: "idle",
            label: t.settings.engineStatusUnset,
            meta: "—",
          };
        }
        return {
          tone: compatibleKey ? "ok" : "warn",
          label: compatibleKey
            ? t.settings.engineStatusKeySet
            : t.settings.engineStatusNoKey,
          meta: saved.openaiCompatible.spaceId,
        };
    }
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

  const choose = (provider: EmbeddingProvider) => {
    setSelected(provider);
    // An unconfigured generic endpoint has nothing valid to select, so its card
    // opens the pane and writes nothing. Its Save is the commit instead.
    if (provider !== saved.provider && configured(provider)) {
      void commit({ ...saved, provider });
    }
  };

  return (
    <section className="card pad set-card" id="embedding">
      <div className="set-row" style={{ marginBottom: 12 }}>
        <div className="set-rowtext">
          <span className="set-label">{t.settings.embedding}</span>
          <span className="set-hint">{t.settings.embeddingHint}</span>
        </div>
      </div>

      <div className="set-engines">
        {EMBEDDING_PROVIDERS.map((provider) => {
          const Glyph = GLYPHS[provider];
          const state = cardState(provider);
          return (
            <button
              key={provider}
              type="button"
              aria-pressed={selected === provider}
              className={cn("set-engine", selected === provider && "on")}
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
          <span className="eyebrow">{NAMES[selected]}</span>
        </div>

        {selected === "omlx" && (
          <OmlxEmbeddingPane
            initial={saved.omlx}
            onSave={async (omlx) => {
              const next = { ...saved, omlx };
              await setEmbeddingPreferences(next);
              setSaved(next);
            }}
          />
        )}
        {selected === "openai" && (
          <OpenAIEmbeddingPane
            initial={saved.openai}
            hasKey={openAiKey}
            onSave={async (openai) => {
              const next = { ...saved, openai };
              await setEmbeddingPreferences(next);
              setSaved(next);
            }}
          />
        )}
        {selected === "openai_compatible" && (
          <CompatibleEmbeddingPane
            initial={saved.openaiCompatible ?? BLANK_COMPATIBLE}
            hasKey={compatibleKey}
            configured={saved.openaiCompatible !== null}
            onSave={async (openaiCompatible) => {
              // Saving a complete pane is also the selection — the card could
              // not commit one earlier because there was nothing to select.
              const next: EmbeddingPreferences = {
                ...saved,
                openaiCompatible,
                provider: "openai_compatible",
              };
              await setEmbeddingPreferences(next);
              setSaved(next);
            }}
          />
        )}
      </div>

      <div className="set-sub set-row">
        <div className="set-rowtext">
          <span className="set-label">{t.settings.embeddingIdentity}</span>
          <span className="set-hint">{t.settings.embeddingIdentityHint}</span>
        </div>
        <div className="set-rowctl">
          <span className="mono">{embedderIdentity(saved)}</span>
        </div>
      </div>

      <p className="set-note">{t.settings.embeddingSwitchHint}</p>
      <p className="set-note">{t.settings.embeddingLegacyHint}</p>
    </section>
  );
}

function OmlxEmbeddingPane({
  initial,
  onSave,
}: {
  initial: OmlxEmbeddingSettings;
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
        <label htmlFor="embedding-omlx-model">{t.settings.omlxModel}</label>
        <Input
          id="embedding-omlx-model"
          className="mono"
          value={value.model}
          onChange={(e) => setValue({ model: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
      </div>
      <p className="set-note">{t.settings.embeddingOmlxHint}</p>
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

function OpenAIEmbeddingPane({
  initial,
  hasKey,
  onSave,
}: {
  initial: OpenAIEmbeddingSettings;
  hasKey: boolean;
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
    value.apiKeyEnv !== saved.apiKeyEnv ||
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
        <label htmlFor="embedding-compatible-key">
          {t.settings.embeddingApiKeyEnv}
        </label>
        <Input
          id="embedding-compatible-key"
          className="mono"
          value={value.apiKeyEnv}
          placeholder="MY_EMBEDDING_API_KEY"
          onChange={(e) => setValue({ ...value, apiKeyEnv: e.target.value })}
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
      <p className="set-note">{t.settings.embeddingApiKeyEnvHint}</p>
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
          value.baseUrl.trim() &&
            value.model.trim() &&
            value.apiKeyEnv.trim() &&
            value.spaceId.trim(),
        )}
        onSave={() => void save()}
        onReset={reset}
      />
    </>
  );
}
