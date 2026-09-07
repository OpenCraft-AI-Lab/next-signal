"use server";

import { readFile } from "node:fs/promises";

import { getEmbeddingPreferences } from "@/lib/actions/embedding";
import { secretsStateFile } from "@/lib/paths";
import {
  assertValidCredentialName,
  credentialPresence,
  parseSecrets,
  serializeSecrets,
  type CredentialPresence,
} from "@/lib/secrets";
import { writeStateFile } from "@/lib/state-file";

/** Radar Embedding's hosted credentials — locked once any provider is committed. */
const RADAR_EMBEDDING_CREDENTIALS = new Set([
  "RADAR_EMBEDDING_OPENAI_API_KEY",
  "EMBEDDING_API_KEY",
]);

/** Knowledge Embedding's hosted credentials — locked once GBrain is initialised. */
const KNOWLEDGE_EMBEDDING_CREDENTIALS = new Set([
  "OPENAI_API_KEY",
  "VOYAGE_API_KEY",
  "GOOGLE_GENERATIVE_AI_API_KEY",
]);

/**
 * Whether `name` belongs to a section that has already committed and locked
 * — defense in depth behind the disabled UI, matching the check
 * `setEmbeddingPreferences` already has for the provider/model half of the
 * same lock. A credential with no lock concept (`DEEPSEEK_API_KEY`,
 * `FOLO_TOKEN`) is never locked.
 *
 * Knowledge Embedding's readiness check is imported dynamically: that
 * module imports `getCredentialPresence` from this one, and a static import
 * here would close that into a cycle. The dynamic import defers resolution
 * past both modules' initial evaluation, which is enough to break it.
 */
async function isCredentialLocked(name: string): Promise<boolean> {
  if (RADAR_EMBEDDING_CREDENTIALS.has(name)) {
    const preferences = await getEmbeddingPreferences();
    return preferences.provider !== null;
  }
  if (KNOWLEDGE_EMBEDDING_CREDENTIALS.has(name)) {
    const { getGbrainReadiness } = await import(
      "@/lib/actions/knowledge-embedding"
    );
    const readiness = await getGbrainReadiness();
    return readiness.provider !== null;
  }
  return false;
}

/** Owner-only. The other state files hold settings; this one holds secrets. */
const SECRETS_MODE = 0o600;

/**
 * Read the whole store. Private to this module on purpose: no exported action
 * returns a credential value, so this is the only place values exist, and they
 * exist only long enough to rewrite the file.
 */
async function readSecrets(): Promise<Record<string, string>> {
  let raw: string;
  try {
    raw = await readFile(secretsStateFile(), "utf-8");
  } catch {
    return {}; // absent is normal — a fresh install has no credentials
  }
  return parseSecrets(raw);
}

/**
 * Which credentials are configured. The only credential-derived value that
 * crosses to the client: a boolean per name, never a value and never a masked
 * fragment of one.
 *
 * `extraNames` carries the operator-defined name an OpenAI-compatible embedding
 * endpoint uses, which is only knowable after reading `embedding.json`.
 *
 * Unlike the settings page's other readers, a damaged store is *not* swallowed
 * here: presence is the thing the section exists to report, and defaulting a
 * broken file to "nothing configured" would tell the operator to re-enter
 * credentials that are already there.
 */
export async function getCredentialPresence(
  extraNames: string[] = [],
): Promise<CredentialPresence> {
  return credentialPresence(await readSecrets(), extraNames);
}

/**
 * Store one credential. Atomic and `0600`, so a pipeline process reading
 * mid-write sees either the old file or the new one, never a torn one.
 *
 * Writes only `secrets.json`: engine, embedding, schedule, coding-agent, and
 * language state are separate files owned by separate sections.
 *
 * Rejects a write to a credential whose owning section has already locked —
 * defense in depth behind the disabled UI; see `isCredentialLocked`.
 */
export async function saveCredential(
  name: string,
  value: string,
): Promise<void> {
  const trimmed = value.trim();
  if (!trimmed) throw new Error(`refusing to store an empty value for ${name}`);
  const validName = assertValidCredentialName(name);
  if (await isCredentialLocked(validName)) {
    throw new Error(`${validName} belongs to a locked section and cannot be changed.`);
  }
  const secrets = await readSecrets();
  secrets[validName] = trimmed;
  await writeStateFile(secretsStateFile(), serializeSecrets(secrets), {
    mode: SECRETS_MODE,
  });
}

/**
 * Remove one credential. Removing one that is not set is a no-op. Rejects a
 * delete of a credential whose owning section has already locked, same as
 * `saveCredential`.
 */
export async function deleteCredential(name: string): Promise<void> {
  const validName = assertValidCredentialName(name);
  const secrets = await readSecrets();
  if (!(validName in secrets)) return;
  if (await isCredentialLocked(validName)) {
    throw new Error(`${validName} belongs to a locked section and cannot be changed.`);
  }
  delete secrets[validName];
  await writeStateFile(secretsStateFile(), serializeSecrets(secrets), {
    mode: SECRETS_MODE,
  });
}
