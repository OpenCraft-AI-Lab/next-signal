/**
 * The credential store, mirroring `next_signal.core.secrets`.
 *
 * Both sides read and write the same `~/.next-signal/secrets.json`, so a value
 * this file accepts must be a value the pipeline also accepts — the same
 * contract `embedding-preferences.ts` keeps with its Python counterpart.
 *
 * Unlike the other mirrors, this one handles secret values. Two rules hold
 * everywhere in this module and in everything that calls it:
 *
 * - a credential value never crosses to the browser, in whole or in part;
 * - a credential value is never logged, including inside an error.
 */

/** The credentials the system resolves by name. */
export const CREDENTIAL_NAMES = [
  "ANTHROPIC_API_KEY",
  "OPENAI_API_KEY",
  "GOOGLE_API_KEY",
  "DEEPSEEK_API_KEY",
  "OMLX_API_KEY",
  "GITHUB_TOKEN",
  "FOLO_TOKEN",
] as const;

export type CredentialName = (typeof CREDENTIAL_NAMES)[number];

/**
 * What each credential is for, and what stops working without it. Rendered by
 * the settings section so an empty field's consequence is visible before the
 * feature it powers fails.
 */
export const CREDENTIAL_USES: Record<CredentialName, string> = {
  ANTHROPIC_API_KEY: "claude",
  OPENAI_API_KEY: "openai",
  GOOGLE_API_KEY: "gemini",
  DEEPSEEK_API_KEY: "deepseek",
  OMLX_API_KEY: "omlx",
  GITHUB_TOKEN: "github",
  FOLO_TOKEN: "folo",
};

/** Presence per credential. This is the only shape that reaches the client. */
export type CredentialPresence = Record<string, boolean>;

/**
 * The store is not limited to the names above: an operator-defined
 * OpenAI-compatible embedding endpoint names its own credential through
 * `embedding.json::api_key_env`. Same pattern that file validates against, so a
 * name one accepts the other accepts.
 */
const VALID_NAME = /^[A-Z][A-Z0-9_]{0,63}$/;

export function isValidCredentialName(name: string): boolean {
  return VALID_NAME.test(name);
}

export function assertValidCredentialName(name: string): string {
  if (!isValidCredentialName(name)) {
    throw new Error(
      `credential name must be 1-64 uppercase letters, digits, or underscores, starting with a letter: ${name}`,
    );
  }
  return name;
}

/**
 * Parse the store. Strict in the same way the Python loader is: an absent file
 * is an empty store (a fresh install has no credentials), but a file that
 * exists and cannot be read must not degrade to "nothing configured" — that
 * would present a broken file as a missing key.
 */
export function parseSecrets(raw: string): Record<string, string> {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch (err) {
    throw new Error(
      `invalid credential store: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new Error("invalid credential store: must be a JSON object");
  }
  const entries = Object.entries(data as Record<string, unknown>);
  for (const [key, value] of entries) {
    if (typeof value !== "string") {
      throw new Error(
        `invalid credential store: ${key} is ${typeof value}, expected a string`,
      );
    }
  }
  return Object.fromEntries(entries as [string, string][]);
}

export function serializeSecrets(secrets: Record<string, string>): string {
  const sorted = Object.keys(secrets).sort();
  const ordered: Record<string, string> = {};
  for (const key of sorted) ordered[key] = secrets[key];
  return `${JSON.stringify(ordered, null, 2)}\n`;
}

/**
 * Reduce a store to presence booleans — the only representation allowed to
 * leave the server. Every known name is reported, so a credential that has
 * never been set reads as `false` rather than being absent from the map.
 */
export function credentialPresence(
  secrets: Record<string, string>,
  extraNames: string[] = [],
): CredentialPresence {
  const names = [...CREDENTIAL_NAMES, ...extraNames];
  const presence: CredentialPresence = {};
  for (const name of names) {
    presence[name] = Boolean(secrets[name]?.trim());
  }
  return presence;
}
