"use client";

import {
  Box,
  Check,
  Cloud,
  Copy,
  ExternalLink,
  LogIn,
  LogOut,
  Server,
  Square,
  Terminal,
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { CredentialField } from "@/components/settings/credential-field";
import { SettingsSectionShell } from "@/components/settings/section-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented, SegmentedItem } from "@/components/ui/segmented";
import {
  setClaudeSettings,
  setCodexSettings,
} from "@/lib/actions/coding-agent-settings";
import { setEnginePreferences } from "@/lib/actions/engine";
import { saveCredential } from "@/lib/actions/secrets";
import {
  CLAUDE_EFFORTS,
  CODEX_REASONING_EFFORTS,
  type ClaudeEffort,
  type ClaudeSettings,
  type CodexReasoningEffort,
  type CodexServiceTier,
  type CodexSettings,
  type CodingAgentSettings,
} from "@/lib/coding-agent-preferences";
import type {
  CodingAgentAuthProvider,
  CodingAgentAuthView,
} from "@/lib/coding-agent-auth-types";
import {
  DEEPSEEK_REASONING,
  ENGINES,
  OMLX_PARALLEL,
  type DeepSeekReasoning,
  type DeepSeekSettings,
  type Engine,
  type EnginePreferences,
  type Fallback,
  type OmlxParallel,
  type OmlxSettings,
} from "@/lib/engine-preferences";
import { cn } from "@/lib/utils";

const CODEX_MODEL_SUGGESTIONS = [
  "gpt-5.6-sol",
  "gpt-5.6",
  "gpt-5.6-terra",
  "gpt-5.6-luna",
  "gpt-5.3-codex-spark",
];

const CLAUDE_MODEL_SUGGESTIONS = [
  "default",
  "opus",
  "sonnet",
  "haiku",
  "opusplan",
  "opus[1m]",
  "sonnet[1m]",
];

const GLYPHS: Record<Engine, ComponentType<{ size?: number }>> = {
  omlx: Server,
  deepseek: Cloud,
  codex_cli: Terminal,
  claude_cli: Box,
};

type CardState = {
  tone: "ok" | "warn" | "idle" | "down";
  label: string;
  meta: string;
};

/**
 * Which engine next-signal calls, and the settings of whichever one is chosen.
 *
 * The four are peers to the operator but not on disk: `omlx` and `deepseek` are
 * agno model providers and land in `~/.next-signal/engine.json`, while the two
 * CLI engines keep writing `~/.next-signal/coding-agents.json` through the
 * actions that already own it.
 *
 * Two independent decisions, two independent actions, no shared draft:
 * "Use as primary" (and the Fallback selector) write the active-engine
 * pointer straight to `engine.json` the instant they're used — no staging,
 * no confirm, fully reversible. A pane's own "Save configuration" writes only
 * that engine's own fields (and DeepSeek's credential, if changed) and never
 * touches the pointer. Opening a card only shows that engine's settings; it
 * never proposes a primary change, so an operator can reconfigure a
 * non-active engine (rotate DeepSeek's key, pre-fill a fallback's model)
 * without ever touching which one is active. An earlier version staged the
 * pointer under the pane's own Save button — reverted after hands-on use
 * showed that read as one commit serving two decisions, not one.
 */
export function EngineSection({
  initial,
  codingAgents,
  codingAgentAuth,
  credentialPresence,
  onCredentialChange,
}: {
  initial: EnginePreferences;
  codingAgents: CodingAgentSettings;
  codingAgentAuth: Record<CodingAgentAuthProvider, CodingAgentAuthView>;
  /** Owned by the settings page, shared with every other section and the
   * read-only summary — a save here is visible everywhere immediately. */
  credentialPresence: Record<string, boolean>;
  onCredentialChange: (name: string, present: boolean) => void;
}) {
  const deepSeekKey = Boolean(credentialPresence.DEEPSEEK_API_KEY);
  const { t } = useI18n();
  const [saved, setSaved] = useState<EnginePreferences>(initial);
  // Which pane is showing — pure navigation, changed only by clicking a card.
  const [open, setOpen] = useState<Engine>(initial.primary ?? "omlx");
  const [codex, setCodex] = useState(codingAgents.codex);
  const [claude, setClaude] = useState(codingAgents.claude);
  const [auth, setAuth] = useState(codingAgentAuth);
  const [pointerSaving, setPointerSaving] = useState(false);

  /**
   * Whether `engine` is complete enough to become primary, evaluated against
   * its last-*saved* configuration — never a pane's current unsaved draft,
   * since "Use as primary" implies no save of its own.
   */
  const engineReady = (engine: Engine): boolean => {
    switch (engine) {
      case "omlx":
        return Boolean(saved.omlx.model.trim());
      case "deepseek":
        return Boolean(saved.deepseek.model.trim() && deepSeekKey);
      case "codex_cli":
        return Boolean(
          codex.model.trim() &&
            codex.modelReasoningEffort &&
            codex.serviceTier &&
            auth.codex.connected,
        );
      case "claude_cli":
        return Boolean(claude.model.trim() && claude.effort && auth.claude.connected);
    }
  };

  /**
   * Writes the primary/fallback pointer immediately — the one write both
   * `activatePrimary` and the Fallback selector make. The primary can never also
   * be the fallback: picking a fallback that already held the primary slot
   * (or promoting the engine currently held as fallback) empties the other
   * slot rather than writing a loop.
   */
  const writePointer = async (primary: Engine | null, fallback: Fallback) => {
    const effectiveFallback = fallback === primary ? "none" : fallback;
    setPointerSaving(true);
    try {
      const next = { ...saved, primary, fallback: effectiveFallback };
      await setEnginePreferences(next);
      setSaved(next);
      toast.success(t.settings.enginePrimarySaved);
    } catch (err) {
      console.error("failed to update engine preferences", err);
      toast.error(t.settings.saveFailed);
    } finally {
      setPointerSaving(false);
    }
  };

  const activatePrimary = (engine: Engine) => writePointer(engine, saved.fallback);
  const changeFallback = (fallback: Fallback) => writePointer(saved.primary, fallback);

  const NAMES: Record<Engine, string> = {
    omlx: t.settings.engineOmlx,
    deepseek: t.settings.engineDeepseek,
    codex_cli: t.settings.engineCodex,
    claude_cli: t.settings.engineClaude,
  };
  const KINDS: Record<Engine, string> = {
    omlx: t.settings.engineKindLocal,
    deepseek: t.settings.engineKindCloud,
    codex_cli: t.settings.engineKindCli,
    claude_cli: t.settings.engineKindCli,
  };

  /**
   * Status is what the dashboard can actually observe: a key present in the
   * environment, a model chosen. Nothing here pings an endpoint, so nothing
   * here claims an engine is reachable.
   */
  const cardState = (engine: Engine): CardState => {
    switch (engine) {
      case "omlx": {
        const hasEndpoint = Boolean(saved.omlx.baseUrl?.trim());
        return {
          tone: hasEndpoint ? "ok" : "warn",
          label: hasEndpoint
            ? t.settings.engineStatusConfigured
            : t.settings.engineStatusUnset,
          meta: saved.omlx.model,
        };
      }
      case "deepseek":
        return {
          tone: deepSeekKey ? "ok" : "warn",
          label: deepSeekKey
            ? t.settings.engineStatusKeySet
            : t.settings.engineStatusNoKey,
          meta: saved.deepseek.model,
        };
      case "codex_cli":
        return {
          tone: auth.codex.connected
            ? "ok"
            : auth.codex.available
              ? "warn"
              : "down",
          label: auth.codex.connected
            ? t.settings.authConnected
            : auth.codex.available
              ? t.settings.authNotConnected
              : t.settings.authUnavailable,
          meta: codex.model || "—",
        };
      case "claude_cli":
        return {
          tone: auth.claude.connected
            ? "ok"
            : auth.claude.available
              ? "warn"
              : "down",
          label: auth.claude.connected
            ? t.settings.authConnected
            : auth.claude.available
              ? t.settings.authNotConnected
              : t.settings.authUnavailable,
          meta: claude.model || "—",
        };
    }
  };

  /**
   * Each pane's own commit — fields only, never the primary/fallback
   * pointer. `omlx`/`deepseek` share `engine.json` with the pointer but
   * write only their own section of it, carrying the rest of `saved`
   * forward unchanged.
   */
  const commitOmlx = async (fields: OmlxSettings) => {
    const next: EnginePreferences = { ...saved, omlx: fields };
    await setEnginePreferences(next);
    setSaved(next);
  };

  /** `apiKey` is the freshly typed value, empty when the operator left it
   * blank to keep whatever is already stored under `hasKey`. Written first
   * so a failure partway through is safely retryable. */
  const commitDeepSeek = async (fields: DeepSeekSettings, apiKey: string) => {
    const trimmedKey = apiKey.trim();
    if (trimmedKey) {
      await saveCredential("DEEPSEEK_API_KEY", trimmedKey);
      onCredentialChange("DEEPSEEK_API_KEY", true);
    }
    const next: EnginePreferences = { ...saved, deepseek: fields };
    await setEnginePreferences(next);
    setSaved(next);
  };

  const commitCodex = async (fields: CodexSettings) => {
    await setCodexSettings(fields);
    setCodex(fields);
  };

  const commitClaude = async (fields: ClaudeSettings) => {
    await setClaudeSettings(fields);
    setClaude(fields);
  };

  const summary =
    saved.primary === null ? (
      <span className="set-status idle">{t.settings.engineStatusUnset}</span>
    ) : (
      <span className="set-status ok">
        <span className="dot" />
        {NAMES[saved.primary]}
      </span>
    );

  return (
    <SettingsSectionShell
      id="engine"
      label={t.settings.engine}
      hint={t.settings.engineHint}
      summary={summary}
    >
      {saved.primary === null && (
        <p className="set-note">{t.settings.engineUnselectedHint}</p>
      )}
      <div className="set-engines">
        {ENGINES.map((engine) => {
          const Glyph = GLYPHS[engine];
          const state = cardState(engine);
          const active = saved.primary === engine;
          return (
            <button
              key={engine}
              type="button"
              aria-pressed={active}
              className={cn(
                "set-engine",
                active && "on",
                open === engine && !active && "set-engineopen",
              )}
              onClick={() => setOpen(engine)}
            >
              <div className="set-enginetop">
                <div className="set-engineid">
                  <span className="set-engineglyph">
                    <Glyph size={15} />
                  </span>
                  <span className="col">
                    <span className="set-enginename">{NAMES[engine]}</span>
                    <span className="set-enginekind">{KINDS[engine]}</span>
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
          {saved.primary === open ? (
            <span className="set-status ok">
              <span className="dot" />
              {t.settings.enginePrimaryBadge}
            </span>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={pointerSaving || !engineReady(open)}
              onClick={() => void activatePrimary(open)}
            >
              {pointerSaving ? t.settings.saving : t.settings.engineUsePrimary}
            </Button>
          )}
        </div>

        {open === "omlx" && (
          <OmlxPane initial={saved.omlx} onSave={commitOmlx} />
        )}
        {open === "deepseek" && (
          <DeepSeekPane
            initial={saved.deepseek}
            hasKey={deepSeekKey}
            onSave={commitDeepSeek}
          />
        )}
        {open === "codex_cli" && (
          <CodexPane
            initial={codex}
            auth={auth.codex}
            onAuthChange={(next) =>
              setAuth((current) => ({ ...current, codex: next }))
            }
            onSave={commitCodex}
          />
        )}
        {open === "claude_cli" && (
          <ClaudePane
            initial={claude}
            auth={auth.claude}
            onAuthChange={(next) =>
              setAuth((current) => ({ ...current, claude: next }))
            }
            onSave={commitClaude}
          />
        )}
      </div>

      <div className="set-sub set-row">
        <div className="set-rowtext">
          <span className="set-label">{t.settings.engineFallback}</span>
          <span className="set-hint">{t.settings.engineFallbackHint}</span>
        </div>
        <div className="set-rowctl">
          <select
            className="input mono"
            style={{ width: 210 }}
            value={saved.fallback}
            disabled={pointerSaving}
            onChange={(e) => void changeFallback(e.target.value as Fallback)}
          >
            <option value="none">{t.settings.engineFallbackNone}</option>
            {/* Commits the instant it changes, so the list only ever needs to
                exclude the real saved primary — there is nothing staged to
                reconcile. */}
            {ENGINES.filter((engine) => engine !== saved.primary).map(
              (engine) => (
                <option key={engine} value={engine}>
                  {NAMES[engine]}
                </option>
              ),
            )}
          </select>
        </div>
      </div>
    </SettingsSectionShell>
  );
}

/**
 * Save/Reset footer shared by every pane across Engine, Radar Embedding, and
 * Knowledge Embedding. Dirty state is the pane's, not this component's — each
 * pane knows what "changed" means for its own shape, including (for Engine)
 * whatever is staged at the section level.
 */
export function PaneActions({
  dirty,
  saving,
  canSave = true,
  onSave,
  onReset,
}: {
  dirty: boolean;
  saving: boolean;
  canSave?: boolean;
  onSave: () => void;
  onReset: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="set-actions">
      {dirty && <span className="set-dirty">{t.settings.unsaved}</span>}
      <Button
        type="button"
        size="sm"
        disabled={!dirty || saving}
        onClick={onReset}
      >
        {t.settings.reset}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="primary"
        disabled={!dirty || saving || !canSave}
        onClick={onSave}
      >
        {saving ? t.settings.saving : t.settings.save}
      </Button>
    </div>
  );
}

/** Wraps a pane's save round-trip so every pane reports identically. */
export function usePaneSave<T>(
  initial: T,
  onSave: (value: T) => Promise<void>,
  message: string,
) {
  const { t } = useI18n();
  const [saved, setSaved] = useState(initial);
  const [value, setValue] = useState(initial);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await onSave(value);
      setSaved(value);
      toast.success(message);
    } catch (err) {
      console.error("failed to save settings pane", err);
      toast.error(t.settings.saveFailed);
    } finally {
      setSaving(false);
    }
  };

  return { saved, value, setValue, saving, save, reset: () => setValue(saved) };
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <span className="set-formlabel">{label}</span>
      {children}
    </>
  );
}

function OmlxPane({
  initial,
  onSave,
}: {
  initial: OmlxSettings;
  onSave: (value: OmlxSettings) => Promise<void>;
}) {
  const { t } = useI18n();
  const { saved, value, setValue, saving, save, reset } = usePaneSave(
    initial,
    onSave,
    t.settings.engineSaved,
  );
  const dirty =
    value.baseUrl !== saved.baseUrl ||
    value.model !== saved.model ||
    value.parallel !== saved.parallel;

  return (
    <>
      <div className="set-form">
        <label htmlFor="omlx-endpoint">{t.settings.omlxEndpoint}</label>
        <Input
          id="omlx-endpoint"
          className="mono"
          value={value.baseUrl}
          placeholder="http://host.docker.internal:8000/v1"
          onChange={(e) => setValue({ ...value, baseUrl: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <label htmlFor="omlx-model">{t.settings.omlxModel}</label>
        <Input
          id="omlx-model"
          className="mono"
          value={value.model}
          onChange={(e) => setValue({ ...value, model: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <Field label={t.settings.omlxParallel}>
          <Segmented style={{ justifySelf: "start" }}>
            {OMLX_PARALLEL.map((n) => (
              <SegmentedItem
                key={n}
                active={value.parallel === n}
                onClick={() =>
                  setValue({ ...value, parallel: n as OmlxParallel })
                }
              >
                {String(n)}
              </SegmentedItem>
            ))}
          </Segmented>
        </Field>
      </div>
      <p className="set-note">{t.settings.omlxHint}</p>
      <p className="set-note">{t.settings.omlxEndpointHint}</p>
      <PaneActions
        dirty={dirty}
        saving={saving}
        // An empty endpoint is savable: it is how an operator says they have no
        // local server, which sends OMLX profiles to their cloud fallback.
        canSave={Boolean(value.model.trim())}
        onSave={() => void save()}
        onReset={reset}
      />
    </>
  );
}

function DeepSeekPane({
  initial,
  hasKey,
  onSave,
}: {
  initial: DeepSeekSettings;
  hasKey: boolean;
  /** `apiKey` is the freshly typed value, empty when the operator left it
   * blank to keep whatever is already stored under `hasKey`. */
  onSave: (value: DeepSeekSettings, apiKey: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const [saved, setSaved] = useState(initial);
  const [value, setValue] = useState(initial);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const dirty =
    value.model !== saved.model ||
    value.reasoning !== saved.reasoning ||
    apiKey.trim() !== "";
  const REASONING_LABELS: Record<DeepSeekReasoning, string> = {
    off: t.settings.deepseekOff,
    low: t.settings.deepseekLow,
    high: t.settings.deepseekHigh,
  };

  const save = async () => {
    setSaving(true);
    try {
      await onSave(value, apiKey);
      setSaved(value);
      setApiKey("");
      toast.success(t.settings.engineSaved);
    } catch (err) {
      console.error("failed to save settings pane", err);
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
        <label htmlFor="deepseek-model">{t.settings.deepseekModel}</label>
        <Input
          id="deepseek-model"
          className="mono"
          value={value.model}
          onChange={(e) => setValue({ ...value, model: e.target.value })}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <Field label={t.settings.deepseekReasoning}>
          <Segmented style={{ justifySelf: "start" }}>
            {DEEPSEEK_REASONING.map((level) => (
              <SegmentedItem
                key={level}
                active={value.reasoning === level}
                onClick={() => setValue({ ...value, reasoning: level })}
              >
                {REASONING_LABELS[level]}
              </SegmentedItem>
            ))}
          </Segmented>
        </Field>
        <CredentialField
          name="DEEPSEEK_API_KEY"
          label="DEEPSEEK_API_KEY"
          value={apiKey}
          onValueChange={setApiKey}
          present={hasKey}
          disabled={saving}
        />
      </div>
      <p className="set-note">{t.settings.deepseekHint}</p>
      <p className="set-note">{t.settings.deepseekKeyHint}</p>
      <PaneActions
        dirty={dirty}
        saving={saving}
        // Saving DeepSeek's own fields never requires a key — the key is
        // only required to become primary, checked separately by
        // `engineReady` when "Use as primary" is clicked.
        canSave={Boolean(value.model.trim())}
        onSave={() => void save()}
        onReset={reset}
      />
    </>
  );
}

function CodexPane({
  initial,
  auth,
  onAuthChange,
  onSave,
}: {
  initial: CodexSettings;
  auth: CodingAgentAuthView;
  onAuthChange: (value: CodingAgentAuthView) => void;
  onSave: (value: CodexSettings) => Promise<void>;
}) {
  const { t } = useI18n();
  const { saved, value, setValue, saving, save, reset } = usePaneSave(
    initial,
    onSave,
    t.settings.codexSaved,
  );
  const dirty =
    value.model !== saved.model ||
    value.modelReasoningEffort !== saved.modelReasoningEffort ||
    value.serviceTier !== saved.serviceTier;

  return (
    <>
      <AuthControls provider="codex" value={auth} onChange={onAuthChange} />
      <div className="set-form">
        <label htmlFor="codex-model">{t.settings.codexModel}</label>
        <span>
          <Input
            id="codex-model"
            className="mono"
            list="codex-model-suggestions"
            value={value.model}
            onChange={(e) => setValue({ ...value, model: e.target.value })}
            placeholder={t.settings.codexRequired}
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />
          <datalist id="codex-model-suggestions">
            {CODEX_MODEL_SUGGESTIONS.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        </span>
        <label htmlFor="codex-effort">{t.settings.codexEffort}</label>
        <select
          id="codex-effort"
          className="input mono"
          value={value.modelReasoningEffort}
          onChange={(e) =>
            setValue({
              ...value,
              modelReasoningEffort: e.target.value as CodexReasoningEffort,
            })
          }
        >
          <option value="" disabled>
            {t.settings.codexSelect}
          </option>
          {CODEX_REASONING_EFFORTS.map((effort) => (
            <option key={effort} value={effort}>
              {effort}
            </option>
          ))}
        </select>
        <Field label={t.settings.codexSpeed}>
          <Segmented style={{ justifySelf: "start" }}>
            {(
              [
                ["default", t.settings.codexStandard],
                ["fast", t.settings.codexFast],
              ] as const
            ).map(([tier, label]) => (
              <SegmentedItem
                key={tier}
                active={value.serviceTier === tier}
                onClick={() =>
                  setValue({ ...value, serviceTier: tier as CodexServiceTier })
                }
              >
                {label}
              </SegmentedItem>
            ))}
          </Segmented>
        </Field>
      </div>
      <p className="set-note">{t.settings.codexHint}</p>
      <PaneActions
        dirty={dirty}
        saving={saving}
        // Codex has no inherit path: a partial combination cannot be sent.
        // Becoming primary additionally requires an authenticated session,
        // checked separately by `engineReady` when "Use as primary" is
        // clicked.
        canSave={Boolean(
          value.model.trim() && value.modelReasoningEffort && value.serviceTier,
        )}
        onSave={() => void save()}
        onReset={reset}
      />
    </>
  );
}

function ClaudePane({
  initial,
  auth,
  onAuthChange,
  onSave,
}: {
  initial: ClaudeSettings;
  auth: CodingAgentAuthView;
  onAuthChange: (value: CodingAgentAuthView) => void;
  onSave: (value: ClaudeSettings) => Promise<void>;
}) {
  const { t } = useI18n();
  const { saved, value, setValue, saving, save, reset } = usePaneSave(
    initial,
    onSave,
    t.settings.claudeSaved,
  );
  const dirty = value.model !== saved.model || value.effort !== saved.effort;

  return (
    <>
      <AuthControls provider="claude" value={auth} onChange={onAuthChange} />
      <div className="set-form">
        <label htmlFor="claude-model">{t.settings.claudeModel}</label>
        <span>
          <Input
            id="claude-model"
            className="mono"
            list="claude-model-suggestions"
            value={value.model}
            onChange={(e) => setValue({ ...value, model: e.target.value })}
            placeholder={t.settings.codexRequired}
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />
          <datalist id="claude-model-suggestions">
            {CLAUDE_MODEL_SUGGESTIONS.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        </span>
        <label htmlFor="claude-effort">{t.settings.claudeEffort}</label>
        <select
          id="claude-effort"
          className="input mono"
          value={value.effort}
          onChange={(e) =>
            setValue({ ...value, effort: e.target.value as ClaudeEffort | "" })
          }
        >
          <option value="" disabled>
            {t.settings.codexSelect}
          </option>
          {CLAUDE_EFFORTS.map((effort) => (
            <option key={effort} value={effort}>
              {effort}
            </option>
          ))}
        </select>
      </div>
      <p className="set-note">{t.settings.claudeHint}</p>
      <PaneActions
        dirty={dirty}
        saving={saving}
        // Becoming primary additionally requires an authenticated session,
        // checked separately by `engineReady` when "Use as primary" is
        // clicked.
        canSave={Boolean(value.model.trim() && value.effort)}
        onSave={() => void save()}
        onReset={reset}
      />
    </>
  );
}

function AuthControls({
  provider,
  value,
  onChange,
}: {
  provider: CodingAgentAuthProvider;
  value: CodingAgentAuthView;
  onChange: (value: CodingAgentAuthView) => void;
}) {
  const { t } = useI18n();
  const popup = useRef<Window | null>(null);
  const openedUrl = useRef<string | null>(null);
  const [authorizationCode, setAuthorizationCode] = useState("");
  const session = value.session;
  const running = session?.phase === "running";

  const request = async (
    url: string,
    init?: RequestInit,
  ): Promise<CodingAgentAuthView> => {
    const response = await fetch(url, { cache: "no-store", ...init });
    const body = (await response.json()) as CodingAgentAuthView & {
      error?: string;
    };
    if (!response.ok) throw new Error(body.error || t.settings.authFailed);
    return body;
  };

  const refresh = async () => {
    try {
      onChange(await request(`/api/coding-agents/auth/${provider}`));
    } catch (error) {
      console.error("failed to refresh coding-agent authentication", error);
    }
  };

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => void refresh(), 750);
    return () => window.clearInterval(timer);
    // Polling is controlled only by terminal phase; `refresh` intentionally
    // changes identity on each render and must not restart this timer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, running]);

  useEffect(() => {
    const url = session?.loginUrl;
    if (!url || openedUrl.current === url) return;
    openedUrl.current = url;
    if (popup.current && !popup.current.closed) {
      popup.current.location.replace(url);
      popup.current = null;
    }
  }, [session?.loginUrl]);

  const connect = async () => {
    openedUrl.current = null;
    popup.current = window.open(
      "about:blank",
      `${provider}-login`,
      "popup,width=720,height=780",
    );
    if (popup.current) popup.current.opener = null;
    try {
      const next = await request(`/api/coding-agents/auth/${provider}`, {
        method: "POST",
      });
      onChange(next);
      toast.success(t.settings.authStarted);
    } catch (error) {
      popup.current?.close();
      popup.current = null;
      toast.error(
        error instanceof Error ? error.message : t.settings.authFailed,
      );
    }
  };

  const cancel = async () => {
    try {
      await request(`/api/coding-agents/auth/${provider}`, {
        method: "DELETE",
      });
      await refresh();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.settings.authFailed,
      );
    }
  };

  const disconnect = async () => {
    try {
      onChange(
        await request(`/api/coding-agents/auth/${provider}/logout`, {
          method: "POST",
        }),
      );
      toast.success(t.settings.authDisconnected);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.settings.authFailed,
      );
    }
  };

  const submitCode = async () => {
    if (!session || !authorizationCode.trim()) return;
    try {
      const response = await fetch(`/api/coding-agents/auth/${provider}`, {
        method: "PUT",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId: session.id,
          value: authorizationCode.trim(),
        }),
      });
      const body = (await response.json()) as { error?: string };
      if (!response.ok) throw new Error(body.error || t.settings.authFailed);
      setAuthorizationCode("");
      toast.success(t.settings.authCodeSent);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.settings.authFailed,
      );
    }
  };

  const statusLabel = running
    ? t.settings.authConnecting
    : value.connected
      ? t.settings.authConnected
      : value.available
        ? t.settings.authNotConnected
        : t.settings.authUnavailable;
  const statusTone = running
    ? "warn"
    : value.connected
      ? "ok"
      : value.available
        ? "idle"
        : "down";

  return (
    <div className="set-auth">
      <div className="set-authhead">
        <span className="set-formlabel">{t.settings.authAccount}</span>
        <span className={`set-status ${statusTone}`}>
          <span className="dot" />
          {statusLabel}
        </span>
      </div>
      <p className="set-note">{t.settings.authHint}</p>
      <div className="set-authactions">
        {running ? (
          <Button type="button" size="sm" onClick={() => void cancel()}>
            <Square size={12} />
            {t.settings.authCancel}
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="primary"
            disabled={!value.available}
            onClick={() => void connect()}
          >
            <LogIn size={13} />
            {value.connected
              ? t.settings.authReconnect
              : t.settings.authConnect}
          </Button>
        )}
        {value.connected && !running && (
          <Button type="button" size="sm" onClick={() => void disconnect()}>
            <LogOut size={13} />
            {t.settings.authDisconnect}
          </Button>
        )}
      </div>

      {session?.loginUrl && (
        <div className="set-authurl">
          <a href={session.loginUrl} target="_blank" rel="noreferrer">
            <ExternalLink size={12} />
            {t.settings.authOpenLogin}
          </a>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              void navigator.clipboard.writeText(session.loginUrl ?? "");
              toast.success(t.settings.authLinkCopied);
            }}
          >
            <Copy size={12} />
            {t.settings.authCopyLink}
          </Button>
        </div>
      )}

      {provider === "claude" && running && session?.loginUrl && (
        <div className="set-authcode">
          <Input
            type="password"
            value={authorizationCode}
            maxLength={4096}
            placeholder={t.settings.authCodePlaceholder}
            aria-label={t.settings.authCodePlaceholder}
            onChange={(event) => setAuthorizationCode(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void submitCode();
            }}
          />
          <Button
            type="button"
            size="sm"
            disabled={!authorizationCode.trim()}
            onClick={() => void submitCode()}
          >
            {t.settings.authSubmitCode}
          </Button>
        </div>
      )}

      {session?.transcript && (
        <pre className="set-authlog">{session.transcript}</pre>
      )}
      {session?.error && <p className="set-autherror">{session.error}</p>}
    </div>
  );
}
