"use client";

import { Check, Cloud, Server, Share2 } from "lucide-react";
import { useState, type ComponentType } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { CredentialField } from "@/components/settings/credential-field";
import {
  PaneActions,
  usePaneSave,
} from "@/components/settings/engine-section";
import { SettingsSectionShell } from "@/components/settings/section-shell";
import { Input } from "@/components/ui/input";
import type { EmbeddingPrefill } from "@/lib/actions/embedding";
import { setEmbeddingPreferences } from "@/lib/actions/embedding";
import { saveCredential } from "@/lib/actions/secrets";
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

/** The credential name each provider's pane folds into its one commit, if any. */
const CREDENTIAL_NAME: Partial<Record<EmbeddingProvider, string>> = {
  openai: "RADAR_EMBEDDING_OPENAI_API_KEY",
  openai_compatible: "EMBEDDING_API_KEY",
};

/**
 * Which embedder the info-radar dedup gate resolves for each item.
 *
 * Reuses the engine section's cards, panes, and status vocabulary because the
 * interaction is similar — but the consequence is bigger: switching an
 * embedder changes the vector space, which parks every topic memorised under
 * the old identity. Rather than allowing a confirmed switch, this section
 * locks in full after its first save — the choice is permanent for the life
 * of this install, not a switchable preference. Every card and pane renders
 * read-only once locked; there is no unlock path through this UI.
 *
 * Nothing is selected on a fresh install. There is no provider this repo could
 * honestly pick on someone's behalf, so every card starts unselected, panes
 * open prefilled with suggestions, and the section says plainly that
 * deduplication is off until one is chosen and saved.
 */
export function EmbeddingSection({
  initial,
  prefill,
  credentialPresence,
  onCredentialChange,
}: {
  initial: EmbeddingPreferences;
  prefill: EmbeddingPrefill;
  credentialPresence: Record<string, boolean>;
  onCredentialChange: (name: string, present: boolean) => void;
}) {
  const { t } = useI18n();
  const radarOpenAiKey = Boolean(credentialPresence.RADAR_EMBEDDING_OPENAI_API_KEY);
  const compatibleKey = Boolean(credentialPresence.EMBEDDING_API_KEY);
  const [saved, setSaved] = useState<EmbeddingPreferences>(initial);
  const locked = saved.provider !== null;
  // Which pane is open. Once locked, only the locked provider's pane is ever
  // shown — there is nothing left to open.
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
      return {
        tone: "ok",
        label: t.settings.engineStatusConfigured,
        meta: saved.omlx!.model,
      };
    }
    const hasKey = provider === "openai" ? radarOpenAiKey : compatibleKey;
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

  const choose = (provider: EmbeddingProvider) => {
    if (locked) return; // the section renders read-only once a provider locks it
    setOpen(provider);
  };

  /**
   * Saving a pane's first complete provider is the one write this section ever
   * makes: it stores the pane's credential (if the operator typed a new one),
   * then the pane's fields, selects that provider, and locks the section. The
   * choice is confirmed once, here, because there is no way back through this
   * UI afterward.
   *
   * The credential writes first so a failure partway through is safely
   * retryable: if the preferences write fails after the credential succeeded,
   * `hasKey` already reads true on retry and an empty key input keeps it.
   *
   * Doesn't toast on success — the calling pane's own save wrapper does that
   * once, after this (and its own state update) resolves.
   */
  const saveAndSelect = async (
    provider: EmbeddingProvider,
    next: EmbeddingPreferences,
    apiKey?: string,
  ) => {
    if (!window.confirm(t.settings.embeddingConfirmPermanent)) return;
    const credentialName = CREDENTIAL_NAME[provider];
    const trimmedKey = apiKey?.trim();
    if (credentialName && trimmedKey) {
      await saveCredential(credentialName, trimmedKey);
      onCredentialChange(credentialName, true);
    }
    const selected = { ...next, provider };
    await setEmbeddingPreferences(selected);
    setSaved(selected);
    setOpen(provider);
  };

  const identity = embedderIdentity(saved);
  const summary = saved.provider === null ? (
    <span className="set-status idle">{t.settings.engineStatusUnset}</span>
  ) : (
    <span className="set-status ok">
      <span className="dot" />
      {NAMES[saved.provider]} · {identity}
    </span>
  );

  return (
    <SettingsSectionShell
      id="embedding"
      label={t.settings.embedding}
      hint={t.settings.embeddingHint}
      summary={summary}
    >
      {saved.provider === null && (
        <p className="set-note">{t.settings.embeddingUnselectedHint}</p>
      )}
      {locked && <p className="set-note">{t.settings.embeddingLockedHint}</p>}

      <div className="set-engines">
        {EMBEDDING_PROVIDERS.map((provider) => {
          const Glyph = GLYPHS[provider];
          const state = cardState(provider);
          const active = saved.provider === provider;
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
            locked={locked}
            onSave={(omlx) => saveAndSelect("omlx", { ...saved, omlx })}
          />
        )}
        {open === "openai" && (
          <OpenAIEmbeddingPane
            initial={saved.openai ?? { model: prefill.openaiModel }}
            hasKey={radarOpenAiKey}
            configured={saved.openai !== null}
            locked={locked}
            onSave={(openai, apiKey) =>
              saveAndSelect("openai", { ...saved, openai }, apiKey)
            }
          />
        )}
        {open === "openai_compatible" && (
          <CompatibleEmbeddingPane
            initial={
              saved.openaiCompatible ?? { baseUrl: "", model: "", spaceId: "" }
            }
            hasKey={compatibleKey}
            configured={saved.openaiCompatible !== null}
            locked={locked}
            onSave={(openaiCompatible, apiKey) =>
              saveAndSelect(
                "openai_compatible",
                { ...saved, openaiCompatible },
                apiKey,
              )
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

      <p className="set-note">{t.settings.embeddingLegacyHint}</p>
    </SettingsSectionShell>
  );
}

function OmlxEmbeddingPane({
  initial,
  configured,
  locked,
  onSave,
}: {
  initial: OmlxEmbeddingSettings;
  configured: boolean;
  locked: boolean;
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
          disabled={locked}
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
          disabled={locked}
          onChange={(e) => setValue({ ...value, model: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
      </div>
      <p className="set-note">{t.settings.embeddingOmlxEndpointHint}</p>
      <p className="set-note">{t.settings.embeddingOmlxHint}</p>
      {!configured && <p className="set-note">{t.settings.embeddingSaveToSelectHint}</p>}
      {!locked && (
        <PaneActions
          dirty={value.baseUrl !== saved.baseUrl || value.model !== saved.model}
          saving={saving}
          canSave={Boolean(value.baseUrl.trim() && value.model.trim())}
          onSave={() => void save()}
          onReset={reset}
        />
      )}
    </>
  );
}

function OpenAIEmbeddingPane({
  initial,
  hasKey,
  configured,
  locked,
  onSave,
}: {
  initial: OpenAIEmbeddingSettings;
  hasKey: boolean;
  configured: boolean;
  locked: boolean;
  /** `apiKey` is the freshly typed value, empty when the operator left it
   * blank to keep whatever is already stored under `hasKey`. */
  onSave: (value: OpenAIEmbeddingSettings, apiKey: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const [saved, setSaved] = useState(initial);
  const [value, setValue] = useState(initial);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  // An unconfigured pane opens prefilled with a valid suggestion, so `value`
  // already equals `saved` — dirty-gating alone would leave no way to commit
  // that first, unedited default.
  const dirty = !configured || value.model !== saved.model || apiKey.trim() !== "";

  const save = async () => {
    setSaving(true);
    try {
      await onSave(value, apiKey);
      setSaved(value);
      setApiKey("");
      toast.success(t.settings.embeddingSaved);
    } catch (err) {
      console.error("failed to save embedding settings", err);
      toast.error(t.settings.saveFailed);
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setValue(saved);
    setApiKey("");
  };

  return (
    <>
      <div className="set-form">
        <label htmlFor="embedding-openai-model">{t.settings.omlxModel}</label>
        <Input
          id="embedding-openai-model"
          className="mono"
          value={value.model}
          disabled={locked}
          onChange={(e) => setValue({ model: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <CredentialField
          name="RADAR_EMBEDDING_OPENAI_API_KEY"
          label="RADAR_EMBEDDING_OPENAI_API_KEY"
          value={apiKey}
          onValueChange={setApiKey}
          present={hasKey}
          disabled={locked || saving}
        />
      </div>
      <p className="set-note">{t.settings.embeddingHostedHint}</p>
      <p className="set-note">{t.settings.embeddingOpenaiKeyHint}</p>
      <p className="set-note">{t.settings.embeddingWidthHint}</p>
      {!configured && <p className="set-note">{t.settings.embeddingSaveToSelectHint}</p>}
      {!locked && (
        <PaneActions
          dirty={dirty}
          saving={saving}
          canSave={Boolean(value.model.trim() && (hasKey || apiKey.trim()))}
          onSave={() => void save()}
          onReset={reset}
        />
      )}
    </>
  );
}

function CompatibleEmbeddingPane({
  initial,
  hasKey,
  configured,
  locked,
  onSave,
}: {
  initial: OpenAICompatibleEmbeddingSettings;
  hasKey: boolean;
  configured: boolean;
  locked: boolean;
  /** `apiKey` is the freshly typed value, empty when the operator left it
   * blank to keep whatever is already stored under `hasKey`. */
  onSave: (
    value: OpenAICompatibleEmbeddingSettings,
    apiKey: string,
  ) => Promise<void>;
}) {
  const { t } = useI18n();
  const [saved, setSaved] = useState(initial);
  const [value, setValue] = useState(initial);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const dirty =
    value.baseUrl !== saved.baseUrl ||
    value.model !== saved.model ||
    value.spaceId !== saved.spaceId ||
    apiKey.trim() !== "";

  const save = async () => {
    setSaving(true);
    try {
      await onSave(value, apiKey);
      setSaved(value);
      setApiKey("");
      toast.success(t.settings.embeddingSaved);
    } catch (err) {
      console.error("failed to save embedding settings", err);
      toast.error(t.settings.saveFailed);
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setValue(saved);
    setApiKey("");
  };

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
          disabled={locked}
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
          disabled={locked}
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
          disabled={locked}
          onChange={(e) => setValue({ ...value, spaceId: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <CredentialField
          name="EMBEDDING_API_KEY"
          label="EMBEDDING_API_KEY"
          value={apiKey}
          onValueChange={setApiKey}
          present={hasKey}
          disabled={locked || saving}
        />
      </div>
      <p className="set-note">{t.settings.embeddingBaseUrlHint}</p>
      <p className="set-note">{t.settings.embeddingCompatibleKeyHint}</p>
      <p className="set-note">{t.settings.embeddingSpaceIdHint}</p>
      <p className="set-note">{t.settings.embeddingHostedHint}</p>
      <p className="set-note">{t.settings.embeddingWidthHint}</p>
      {!configured && (
        <p className="set-note">{t.settings.embeddingCompatibleSaveHint}</p>
      )}
      {!locked && (
        <PaneActions
          dirty={dirty}
          saving={saving}
          // No inherit path: a partial endpoint cannot be sent anywhere, and
          // the credential must already be saved (or freshly typed) before
          // this pane can lock the section.
          canSave={Boolean(
            value.baseUrl.trim() &&
              value.model.trim() &&
              value.spaceId.trim() &&
              (hasKey || apiKey.trim()),
          )}
          onSave={() => void save()}
          onReset={reset}
        />
      )}
    </>
  );
}
