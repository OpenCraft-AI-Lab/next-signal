/**
 * Live embedding selection: which embedder the info-radar dedup gate resolves
 * for each item, and the parameters of whichever provider is chosen.
 *
 * The mirror of `next_signal.core.embedding_preferences`, and deliberately just
 * as strict — both sides read and write the same `~/.next-signal/embedding.json`,
 * so a value this file accepts is a value the pipeline must also accept.
 *
 * Nothing is selected until an operator selects it: `provider: null` is the
 * fresh-install state, not an error. `configs/models.yaml` supplies suggestions
 * for a pane someone is filling in, never a value that runs. Every section is
 * therefore optional and, once present, complete — there is no baseline for a
 * partial one to inherit.
 *
 * Nothing here ever holds a credential, or names one: each provider's key has a
 * fixed name in the credential store. Base URLs are restricted to a plain API
 * root so a key cannot be smuggled in through userinfo or a query parameter.
 */

export const EMBEDDING_PROVIDERS = [
  "omlx",
  "openai",
  "openai_compatible",
] as const;

export type EmbeddingProvider = (typeof EMBEDDING_PROVIDERS)[number];

export interface OmlxEmbeddingSettings {
  /**
   * The embedding server's own address. Separate from the engine section's
   * local endpoint: one mlx-lm process serves one model, so a chat model and an
   * embedding model are two ports.
   */
  baseUrl: string;
  model: string;
}

export interface OpenAIEmbeddingSettings {
  model: string;
}

export interface OpenAICompatibleEmbeddingSettings {
  baseUrl: string;
  model: string;
  /**
   * The logical name of the vector space this endpoint produces. Separate from
   * `model` because two endpoints can advertise the same model name while
   * differing in weights, tokenizer, pooling, or quantization — comparing those
   * vectors would silently suppress genuinely novel items.
   */
  spaceId: string;
}

export interface EmbeddingPreferences {
  /** `null` until an operator chooses one. Dedup is inactive until they do. */
  provider: EmbeddingProvider | null;
  omlx: OmlxEmbeddingSettings | null;
  openai: OpenAIEmbeddingSettings | null;
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
const OMLX_KEYS = new Set(["base_url", "model"]);
const OPENAI_KEYS = new Set(["model"]);
const COMPATIBLE_KEYS = new Set(["base_url", "model", "space_id"]);

/** Same shape as every other model id the settings page accepts. */
const MODEL_ID = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;
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
  if (value.provider !== null && !EMBEDDING_PROVIDERS.includes(value.provider)) {
    throw new Error(`unknown embedding provider: ${value.provider}`);
  }

  const checkedOmlx: OmlxEmbeddingSettings | null = value.omlx
    ? {
        baseUrl: normalizeCompatibleBaseUrl(value.omlx.baseUrl),
        model: checkedModel(value.omlx.model, "OMLX"),
      }
    : null;

  const checkedOpenAI: OpenAIEmbeddingSettings | null = value.openai
    ? { model: checkedModel(value.openai.model, "OpenAI") }
    : null;

  let checkedCompatible: OpenAICompatibleEmbeddingSettings | null = null;
  if (value.openaiCompatible !== null) {
    const spaceId = value.openaiCompatible.spaceId.trim();
    if (!SPACE_ID.test(spaceId)) {
      throw new Error(
        "space_id must be 1-128 letters, digits, dots, underscores, or " +
          `hyphens, starting with a letter or digit: ${spaceId}`,
      );
    }
    checkedCompatible = {
      baseUrl: normalizeCompatibleBaseUrl(value.openaiCompatible.baseUrl),
      model: checkedModel(value.openaiCompatible.model, "OpenAI-compatible"),
      spaceId,
    };
  }

  const sections = {
    omlx: checkedOmlx,
    openai: checkedOpenAI,
    openai_compatible: checkedCompatible,
  };
  if (value.provider !== null && sections[value.provider] === null) {
    throw new Error(
      `${value.provider} is selected but has no saved configuration; save its ` +
        "settings before selecting it",
    );
  }

  return {
    provider: value.provider,
    omlx: checkedOmlx,
    openai: checkedOpenAI,
    openaiCompatible: checkedCompatible,
  };
}

/**
 * Read the stored preferences.
 *
 * Every section is read whole or not at all: with nothing to inherit from, a
 * partial section fails rather than silently completing itself from values this
 * file would have had to invent.
 */
export function parseEmbeddingPreferences(raw: string): EmbeddingPreferences {
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

  let omlx: OmlxEmbeddingSettings | null = null;
  const rawOmlx = data.omlx;
  if (rawOmlx !== undefined && rawOmlx !== null) {
    if (!isRecord(rawOmlx)) throw new Error("omlx preferences must be an object");
    rejectUnknownKeys(rawOmlx, OMLX_KEYS, "omlx");
    omlx = {
      baseUrl: requiredString(rawOmlx, "base_url", "omlx"),
      model: requiredString(rawOmlx, "model", "omlx"),
    };
  }

  let openai: OpenAIEmbeddingSettings | null = null;
  const rawOpenAI = data.openai;
  if (rawOpenAI !== undefined && rawOpenAI !== null) {
    if (!isRecord(rawOpenAI)) {
      throw new Error("openai preferences must be an object");
    }
    rejectUnknownKeys(rawOpenAI, OPENAI_KEYS, "openai");
    openai = { model: requiredString(rawOpenAI, "model", "openai") };
  }

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
      spaceId: requiredString(rawCompatible, "space_id", "openai_compatible"),
    };
  }

  const provider = optionalString(data, "provider", "embedding") ?? null;
  return validateEmbeddingPreferences({
    provider: provider as EmbeddingProvider | null,
    omlx,
    openai,
    openaiCompatible,
  });
}

export function serializeEmbeddingPreferences(
  value: EmbeddingPreferences,
): string {
  const checked = validateEmbeddingPreferences(value);
  return JSON.stringify({
    ...(checked.provider ? { provider: checked.provider } : {}),
    ...(checked.omlx
      ? { omlx: { base_url: checked.omlx.baseUrl, model: checked.omlx.model } }
      : {}),
    ...(checked.openai ? { openai: { model: checked.openai.model } } : {}),
    // Written as endpoint parameters only — the credential lives under a fixed
    // name in the store, so nothing here even references one.
    ...(checked.openaiCompatible
      ? {
          openai_compatible: {
            base_url: checked.openaiCompatible.baseUrl,
            model: checked.openaiCompatible.model,
            space_id: checked.openaiCompatible.spaceId,
          },
        }
      : {}),
    updated_at: new Date().toISOString(),
    updated_by: "dashboard",
  });
}

/**
 * The stable vector-space id stamped onto every vector this selection produces,
 * or `null` while nothing is selected. Physical endpoints stay out of it, so
 * moving one compatible service to a new host does not park its dedup memory.
 */
export function embedderIdentity(value: EmbeddingPreferences): string | null {
  if (value.provider === "omlx" && value.omlx) {
    return `omlx:${value.omlx.model}`;
  }
  if (value.provider === "openai" && value.openai) {
    return `openai:${value.openai.model}`;
  }
  if (value.provider === "openai_compatible" && value.openaiCompatible) {
    return `openai_compatible:${value.openaiCompatible.spaceId}`;
  }
  return null;
}

/** Which fixed credential a provider needs, or `null` when it needs none. */
export function embeddingCredentialName(
  provider: EmbeddingProvider,
): string | null {
  if (provider === "openai") return "OPENAI_API_KEY";
  if (provider === "openai_compatible") return "EMBEDDING_API_KEY";
  // A local OMLX server usually has no key at all, so its own is optional.
  return null;
}
