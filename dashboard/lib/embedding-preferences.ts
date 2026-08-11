/**
 * Live embedding selection: which embedder the info-radar dedup gate resolves
 * for each item, and the parameters of whichever provider is chosen.
 *
 * The mirror of `next_signal.core.embedding_preferences`, and deliberately just
 * as strict — both sides read and write the same `~/.next-signal/embedding.json`,
 * so a value this file accepts is a value the pipeline must also accept.
 *
 * `omlx` and `openai` have real baselines in `configs/models.yaml` under
 * `embedders:`, so an unset field reads back as whatever the repo is configured
 * with. `openai_compatible` describes an endpoint this repo has never seen — no
 * honest universal URL, model, key-variable name, or vector space exists for it
 * — so its section is optional and, once present, complete.
 *
 * Nothing here ever holds a credential. The generic section stores the *name* of
 * an environment variable, and its base URL is restricted to a plain API root so
 * a key cannot be smuggled in through userinfo or a query parameter.
 */

export const EMBEDDING_PROVIDERS = [
  "omlx",
  "openai",
  "openai_compatible",
] as const;

export type EmbeddingProvider = (typeof EMBEDDING_PROVIDERS)[number];

export interface OmlxEmbeddingSettings {
  model: string;
}

export interface OpenAIEmbeddingSettings {
  model: string;
}

export interface OpenAICompatibleEmbeddingSettings {
  baseUrl: string;
  model: string;
  apiKeyEnv: string;
  /**
   * The logical name of the vector space this endpoint produces. Separate from
   * `model` because two endpoints can advertise the same model name while
   * differing in weights, tokenizer, pooling, or quantization — comparing those
   * vectors would silently suppress genuinely novel items.
   */
  spaceId: string;
}

export interface EmbeddingPreferences {
  provider: EmbeddingProvider;
  omlx: OmlxEmbeddingSettings;
  openai: OpenAIEmbeddingSettings;
  openaiCompatible: OpenAICompatibleEmbeddingSettings | null;
}

const TOP_LEVEL_KEYS = new Set([
  "provider",
  "omlx",
  "openai",
  "openai_compatible",
  "updated_at",
  "updated_by",
]);
const OMLX_KEYS = new Set(["model"]);
const OPENAI_KEYS = new Set(["model"]);
const COMPATIBLE_KEYS = new Set([
  "base_url",
  "model",
  "api_key_env",
  "space_id",
]);

/** Same shape as every other model id the settings page accepts. */
const MODEL_ID = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;
const API_KEY_ENV = /^[A-Z][A-Z0-9_]{0,63}$/;
const SPACE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

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

function requiredString(
  value: Record<string, unknown>,
  key: string,
  scope: string,
): string {
  const selected = value[key];
  if (typeof selected !== "string") {
    throw new Error(`${scope}.${key} must be a string`);
  }
  return selected;
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

function checkedModel(value: string, provider: string): string {
  const model = value.trim();
  if (!MODEL_ID.test(model)) {
    throw new Error(`invalid ${provider} embedding model identifier: ${model}`);
  }
  return model;
}

/**
 * Accept only a plain API root the client can append `/embeddings` to.
 *
 * Restrictive on purpose: userinfo, a query string, and a fragment are all
 * places an API key fits, and this file is written to a plaintext state file
 * that the pipeline reads. A value already ending in `/embeddings` is the route
 * rather than the root, and would resolve to `…/embeddings/embeddings`.
 */
export function normalizeCompatibleBaseUrl(value: string): string {
  const selected = value.trim();
  let parsed: URL;
  try {
    parsed = new URL(selected);
  } catch {
    throw new Error(`embedding base URL must be an http(s) URL: ${selected}`);
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(`embedding base URL must be an http(s) URL: ${selected}`);
  }
  if (!parsed.hostname) {
    throw new Error(`embedding base URL must name a host: ${selected}`);
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error(
      "embedding base URL must be a plain API root — userinfo, query, and " +
        `fragment components are rejected: ${selected}`,
    );
  }
  const root = selected.replace(/\/+$/, "");
  if (root.endsWith("/embeddings")) {
    throw new Error(
      "embedding base URL is an API root, not the /embeddings route; drop the " +
        `trailing route: ${selected}`,
    );
  }
  return root;
}

/** Reject anything the pipeline would refuse to load back. */
export function validateEmbeddingPreferences(
  value: EmbeddingPreferences,
): EmbeddingPreferences {
  if (!EMBEDDING_PROVIDERS.includes(value.provider)) {
    throw new Error(`unknown embedding provider: ${value.provider}`);
  }

  const compatible = value.openaiCompatible;
  if (value.provider === "openai_compatible" && compatible === null) {
    throw new Error(
      "openai_compatible is selected but has no saved configuration; save " +
        "base_url, model, api_key_env, and space_id before selecting it",
    );
  }

  let checkedCompatible: OpenAICompatibleEmbeddingSettings | null = null;
  if (compatible !== null) {
    const apiKeyEnv = compatible.apiKeyEnv.trim();
    if (!API_KEY_ENV.test(apiKeyEnv)) {
      throw new Error(
        "api_key_env stores an environment variable NAME: 1-64 uppercase " +
          `letters, digits, or underscores, starting with a letter: ${apiKeyEnv}`,
      );
    }
    const spaceId = compatible.spaceId.trim();
    if (!SPACE_ID.test(spaceId)) {
      throw new Error(
        "space_id must be 1-128 letters, digits, dots, underscores, or " +
          `hyphens, starting with a letter or digit: ${spaceId}`,
      );
    }
    checkedCompatible = {
      baseUrl: normalizeCompatibleBaseUrl(compatible.baseUrl),
      model: checkedModel(compatible.model, "OpenAI-compatible"),
      apiKeyEnv,
      spaceId,
    };
  }

  return {
    provider: value.provider,
    omlx: { model: checkedModel(value.omlx.model, "OMLX") },
    openai: { model: checkedModel(value.openai.model, "OpenAI") },
    openaiCompatible: checkedCompatible,
  };
}

/**
 * Read the stored preferences, filling every absent OMLX/OpenAI field from
 * `base` — the values resolved from `configs/models.yaml`. The compatible
 * section has no baseline to fall back on, so it is read whole or not at all: a
 * partial section fails rather than silently completing itself from values this
 * file would have had to invent.
 */
export function parseEmbeddingPreferences(
  raw: string,
  base: EmbeddingPreferences,
): EmbeddingPreferences {
  const data: unknown = JSON.parse(raw);
  if (!isRecord(data)) {
    throw new Error("embedding preferences must be an object");
  }
  rejectUnknownKeys(data, TOP_LEVEL_KEYS, "embedding");
  for (const key of ["updated_at", "updated_by"]) {
    if (data[key] !== undefined && typeof data[key] !== "string") {
      throw new Error(`${key} must be a string`);
    }
  }

  const omlx = data.omlx ?? {};
  if (!isRecord(omlx)) throw new Error("omlx preferences must be an object");
  rejectUnknownKeys(omlx, OMLX_KEYS, "omlx");

  const openai = data.openai ?? {};
  if (!isRecord(openai)) throw new Error("openai preferences must be an object");
  rejectUnknownKeys(openai, OPENAI_KEYS, "openai");

  let openaiCompatible: OpenAICompatibleEmbeddingSettings | null = null;
  const rawCompatible = data.openai_compatible;
  if (rawCompatible !== undefined && rawCompatible !== null) {
    if (!isRecord(rawCompatible)) {
      throw new Error("openai_compatible preferences must be an object");
    }
    rejectUnknownKeys(rawCompatible, COMPATIBLE_KEYS, "openai_compatible");
    openaiCompatible = {
      baseUrl: requiredString(rawCompatible, "base_url", "openai_compatible"),
      model: requiredString(rawCompatible, "model", "openai_compatible"),
      apiKeyEnv: requiredString(rawCompatible, "api_key_env", "openai_compatible"),
      spaceId: requiredString(rawCompatible, "space_id", "openai_compatible"),
    };
  }

  return validateEmbeddingPreferences({
    provider: (optionalString(data, "provider", "embedding") ??
      base.provider) as EmbeddingProvider,
    omlx: { model: optionalString(omlx, "model", "omlx") ?? base.omlx.model },
    openai: {
      model: optionalString(openai, "model", "openai") ?? base.openai.model,
    },
    openaiCompatible,
  });
}

export function serializeEmbeddingPreferences(
  value: EmbeddingPreferences,
): string {
  const checked = validateEmbeddingPreferences(value);
  return JSON.stringify({
    provider: checked.provider,
    omlx: { model: checked.omlx.model },
    openai: { model: checked.openai.model },
    // Written as the four names only — never a resolved key value.
    ...(checked.openaiCompatible
      ? {
          openai_compatible: {
            base_url: checked.openaiCompatible.baseUrl,
            model: checked.openaiCompatible.model,
            api_key_env: checked.openaiCompatible.apiKeyEnv,
            space_id: checked.openaiCompatible.spaceId,
          },
        }
      : {}),
    updated_at: new Date().toISOString(),
    updated_by: "dashboard",
  });
}

/**
 * The stable vector-space id stamped onto every vector this selection produces.
 * Physical endpoints stay out of it, so moving one compatible service to a new
 * host does not park its dedup memory.
 */
export function embedderIdentity(value: EmbeddingPreferences): string {
  if (value.provider === "omlx") return `omlx:${value.omlx.model}`;
  if (value.provider === "openai") return `openai:${value.openai.model}`;
  return `openai_compatible:${value.openaiCompatible?.spaceId ?? ""}`;
}
