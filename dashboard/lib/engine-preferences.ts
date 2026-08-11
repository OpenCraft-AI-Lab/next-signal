/**
 * Live engine selection: which backend next-signal calls, and the parameters of
 * the two that are not already owned by `coding-agent-preferences`.
 *
 * The four engines are presented as peers in the settings page, but they are
 * not peers on disk. `omlx` and `deepseek` are agno model providers configured
 * in `configs/models.yaml`; `codex_cli` and `claude_cli` are external CLI
 * workers whose model and effort live in `~/.next-signal/coding-agents.json`.
 * This file owns only the selection plus the two model-provider sections, so
 * saving here never touches the coding-agent file and vice versa.
 *
 * Engine ids are deliberately NOT the `provider` values from `models.yaml`:
 * `claude` there means the Anthropic API, while the engine a user picks here
 * is the Claude Code CLI. Suffixing the two CLI engines keeps a future
 * Anthropic-API engine addable without a silent collision.
 */

export const ENGINES = ["omlx", "deepseek", "codex_cli", "claude_cli"] as const;
export const FALLBACKS = ["none", ...ENGINES] as const;
/** Local inference is single-process; the ceiling matches `models.yaml`. */
export const OMLX_PARALLEL = [1, 2, 4] as const;
export const DEEPSEEK_REASONING = ["off", "low", "high"] as const;

export type Engine = (typeof ENGINES)[number];
export type Fallback = (typeof FALLBACKS)[number];
export type OmlxParallel = (typeof OMLX_PARALLEL)[number];
export type DeepSeekReasoning = (typeof DEEPSEEK_REASONING)[number];

export interface OmlxSettings {
  baseUrl: string;
  model: string;
  parallel: OmlxParallel;
}

export interface DeepSeekSettings {
  model: string;
  reasoning: DeepSeekReasoning;
}

export interface EnginePreferences {
  primary: Engine;
  fallback: Fallback;
  omlx: OmlxSettings;
  deepseek: DeepSeekSettings;
}

const TOP_LEVEL_KEYS = new Set([
  "primary",
  "fallback",
  "omlx",
  "deepseek",
  "updated_at",
  "updated_by",
]);
const OMLX_KEYS = new Set(["base_url", "model", "parallel"]);
const DEEPSEEK_KEYS = new Set(["model", "reasoning"]);

/** Same shape as the Codex/Claude model ids: an identifier, not free text. */
const MODEL_ID = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function rejectUnknownKeys(
  value: Record<string, unknown>,
  allowed: Set<string>,
  scope: string,
): void {
  const unknown = Object.keys(value).find((key) => !allowed.has(key));
  if (unknown) throw new Error(`unknown ${scope} preference: ${unknown}`);
}

function optionalString(
  value: Record<string, unknown>,
  key: string,
  scope: string,
): string | undefined {
  const selected = value[key];
  if (selected === undefined) return undefined;
  if (typeof selected !== "string") {
    throw new Error(`${scope}.${key} must be a string`);
  }
  return selected;
}

/**
 * Reject anything that would send work somewhere unreachable, or nowhere.
 * Called on both read and write: the file is small enough to hand-edit, and a
 * primary that is also its own fallback is a loop, not a preference.
 */
export function validateEnginePreferences(
  value: EnginePreferences,
): EnginePreferences {
  if (!ENGINES.includes(value.primary)) {
    throw new Error(`unknown engine: ${value.primary}`);
  }
  if (!FALLBACKS.includes(value.fallback)) {
    throw new Error(`unknown fallback engine: ${value.fallback}`);
  }
  if (value.fallback === value.primary) {
    throw new Error(`${value.primary} cannot fall back to itself`);
  }

  const baseUrl = value.omlx.baseUrl.trim();
  // A bare host would be accepted by the OpenAI client and then fail at call
  // time with a confusing 404, so the scheme is required here instead.
  if (!/^https?:\/\/\S+$/.test(baseUrl)) {
    throw new Error(`OMLX endpoint must be an http(s) URL: ${baseUrl}`);
  }
  const omlxModel = value.omlx.model.trim();
  if (!MODEL_ID.test(omlxModel)) {
    throw new Error(`invalid OMLX model identifier: ${omlxModel}`);
  }
  if (!OMLX_PARALLEL.includes(value.omlx.parallel)) {
    throw new Error(`unsupported OMLX parallelism: ${value.omlx.parallel}`);
  }

  const deepseekModel = value.deepseek.model.trim();
  if (!MODEL_ID.test(deepseekModel)) {
    throw new Error(`invalid DeepSeek model identifier: ${deepseekModel}`);
  }
  if (!DEEPSEEK_REASONING.includes(value.deepseek.reasoning)) {
    throw new Error(`unknown DeepSeek reasoning level: ${value.deepseek.reasoning}`);
  }

  return {
    primary: value.primary,
    fallback: value.fallback,
    omlx: { baseUrl, model: omlxModel, parallel: value.omlx.parallel },
    deepseek: { model: deepseekModel, reasoning: value.deepseek.reasoning },
  };
}

/**
 * Read the stored preferences, filling every absent field from `base` — the
 * values resolved from `configs/models.yaml` and the environment. A field the
 * operator has never touched should read as whatever the repo is actually
 * configured with, not as a value this file invented.
 */
export function parseEnginePreferences(
  raw: string,
  base: EnginePreferences,
): EnginePreferences {
  const data: unknown = JSON.parse(raw);
  if (!isRecord(data)) {
    throw new Error("engine preferences must be an object");
  }
  rejectUnknownKeys(data, TOP_LEVEL_KEYS, "engine");
  for (const key of ["updated_at", "updated_by"]) {
    if (data[key] !== undefined && typeof data[key] !== "string") {
      throw new Error(`${key} must be a string`);
    }
  }

  const omlx = data.omlx ?? {};
  if (!isRecord(omlx)) throw new Error("omlx preferences must be an object");
  rejectUnknownKeys(omlx, OMLX_KEYS, "omlx");
  if (omlx.parallel !== undefined && typeof omlx.parallel !== "number") {
    throw new Error("omlx.parallel must be a number");
  }

  const deepseek = data.deepseek ?? {};
  if (!isRecord(deepseek)) {
    throw new Error("deepseek preferences must be an object");
  }
  rejectUnknownKeys(deepseek, DEEPSEEK_KEYS, "deepseek");

  return validateEnginePreferences({
    primary: (optionalString(data, "primary", "engine") ?? base.primary) as Engine,
    fallback: (optionalString(data, "fallback", "engine") ??
      base.fallback) as Fallback,
    omlx: {
      baseUrl: optionalString(omlx, "base_url", "omlx") ?? base.omlx.baseUrl,
      model: optionalString(omlx, "model", "omlx") ?? base.omlx.model,
      parallel: (omlx.parallel ?? base.omlx.parallel) as OmlxParallel,
    },
    deepseek: {
      model: optionalString(deepseek, "model", "deepseek") ?? base.deepseek.model,
      reasoning: (optionalString(deepseek, "reasoning", "deepseek") ??
        base.deepseek.reasoning) as DeepSeekReasoning,
    },
  });
}

export function serializeEnginePreferences(value: EnginePreferences): string {
  const checked = validateEnginePreferences(value);
  return JSON.stringify({
    primary: checked.primary,
    fallback: checked.fallback,
    omlx: {
      base_url: checked.omlx.baseUrl,
      model: checked.omlx.model,
      parallel: checked.omlx.parallel,
    },
    deepseek: {
      model: checked.deepseek.model,
      reasoning: checked.deepseek.reasoning,
    },
    updated_at: new Date().toISOString(),
    updated_by: "dashboard",
  });
}
