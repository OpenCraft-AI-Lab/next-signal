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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented, SegmentedItem } from "@/components/ui/segmented";
import {
  setClaudeSettings,
  setCodexSettings,
} from "@/lib/actions/coding-agent-settings";
import { setEnginePreferences } from "@/lib/actions/engine";
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
 * actions that already own it. Saving one never touches the other's file.
 *
 * Picking a card is a discrete choice and commits on click; an engine's own
 * parameters are an interdependent group and commit on Save. Selection commits
 * against the last *saved* provider settings, so switching engines mid-edit
 * cannot smuggle an unsaved draft onto disk.
 */
export function EngineSection({
  initial,
  codingAgents,
  codingAgentAuth,
  deepSeekKey,
}: {
  initial: EnginePreferences;
  codingAgents: CodingAgentSettings;
  codingAgentAuth: Record<CodingAgentAuthProvider, CodingAgentAuthView>;
  deepSeekKey: boolean;
}) {
  const { t } = useI18n();
  const [saved, setSaved] = useState<EnginePreferences>(initial);
  const [selected, setSelected] = useState<Engine>(initial.primary);
  const [codex, setCodex] = useState(codingAgents.codex);
  const [claude, setClaude] = useState(codingAgents.claude);
  const [auth, setAuth] = useState(codingAgentAuth);

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
      case "omlx":
        return {
          tone: "ok",
          label: t.settings.engineStatusConfigured,
          meta: saved.omlx.model,
        };
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

  /** Persist selection and fallback. Both are single, complete intents. */
  const commitSelection = async (next: Partial<EnginePreferences>) => {
    const merged = { ...saved, ...next };
    // The primary can never also be the fallback — picking one that already
    // held the fallback slot empties it rather than writing a loop.
    if (merged.fallback === merged.primary) merged.fallback = "none";
    const previous = saved;
    setSaved(merged); // optimistic
    try {
      await setEnginePreferences(merged);
      toast.success(t.settings.engineSaved);
    } catch (err) {
      console.error("failed to update engine preferences", err);
      setSaved(previous);
      toast.error(t.settings.saveFailed);
    }
  };

  const choose = (engine: Engine) => {
    setSelected(engine);
    if (engine !== saved.primary) void commitSelection({ primary: engine });
  };

  return (
    <section className="card pad set-card" id="engine">
      <div className="set-row" style={{ marginBottom: 12 }}>
        <div className="set-rowtext">
          <span className="set-label">{t.settings.engine}</span>
          <span className="set-hint">{t.settings.engineHint}</span>
        </div>
      </div>

      <div className="set-engines">
        {ENGINES.map((engine) => {
          const Glyph = GLYPHS[engine];
          const state = cardState(engine);
          return (
            <button
              key={engine}
              type="button"
              aria-pressed={selected === engine}
              className={cn("set-engine", selected === engine && "on")}
              onClick={() => choose(engine)}
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
          <span className="eyebrow">{NAMES[selected]}</span>
        </div>

        {selected === "omlx" && (
          <OmlxPane
            initial={saved.omlx}
            onSave={async (omlx) => {
              const next = { ...saved, omlx };
              await setEnginePreferences(next);
              setSaved(next);
            }}
          />
        )}
        {selected === "deepseek" && (
          <DeepSeekPane
            initial={saved.deepseek}
            hasKey={deepSeekKey}
            onSave={async (deepseek) => {
              const next = { ...saved, deepseek };
              await setEnginePreferences(next);
              setSaved(next);
            }}
          />
        )}
        {selected === "codex_cli" && (
          <CodexPane
            initial={codex}
            auth={auth.codex}
            onAuthChange={(next) =>
              setAuth((current) => ({ ...current, codex: next }))
            }
            onSave={async (next) => {
              await setCodexSettings(next);
              setCodex(next);
            }}
          />
        )}
        {selected === "claude_cli" && (
          <ClaudePane
            initial={claude}
            auth={auth.claude}
            onAuthChange={(next) =>
              setAuth((current) => ({ ...current, claude: next }))
            }
            onSave={async (next) => {
              await setClaudeSettings(next);
              setClaude(next);
            }}
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
            onChange={(e) =>
              void commitSelection({ fallback: e.target.value as Fallback })
            }
          >
            <option value="none">{t.settings.engineFallbackNone}</option>
            {/* The primary is removed rather than shown and rejected on save. */}
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
    </section>
  );
}

/**
 * Save/Reset footer shared by all four panes. Dirty state is the pane's, not
 * this component's — each pane knows what "changed" means for its own shape.
 *
 * Exported for the embedding section, which presents the same interaction and
 * should not drift from it. Only these two helpers are shared: the sections
 * themselves stay separate components with separate state files.
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
      <PaneActions
        dirty={dirty}
        saving={saving}
        canSave={Boolean(value.baseUrl.trim() && value.model.trim())}
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
  onSave: (value: DeepSeekSettings) => Promise<void>;
}) {
  const { t } = useI18n();
  const { saved, value, setValue, saving, save, reset } = usePaneSave(
    initial,
    onSave,
    t.settings.engineSaved,
  );
  const dirty =
    value.model !== saved.model || value.reasoning !== saved.reasoning;
  const REASONING_LABELS: Record<DeepSeekReasoning, string> = {
    off: t.settings.deepseekOff,
    low: t.settings.deepseekLow,
    high: t.settings.deepseekHigh,
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
        {!hasKey && (
          <div className="set-formwide">
            <span className="badge amber">
              <span className="dot" />
              {t.settings.engineStatusNoKey}
            </span>
          </div>
        )}
      </div>
      <p className="set-note">{t.settings.deepseekHint}</p>
      <p className="set-note">{t.settings.deepseekKeyHint}</p>
      <PaneActions
        dirty={dirty}
        saving={saving}
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
