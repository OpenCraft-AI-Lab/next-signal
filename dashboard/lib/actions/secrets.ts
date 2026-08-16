"use server";

import { readFile } from "node:fs/promises";

import { secretsStateFile } from "@/lib/paths";
import {
  assertValidCredentialName,
  credentialPresence,
  parseSecrets,
  serializeSecrets,
  type CredentialPresence,
} from "@/lib/secrets";
import { writeStateFile } from "@/lib/state-file";

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
 */
export async function saveCredential(
  name: string,
  value: string,
): Promise<void> {
  const trimmed = value.trim();
  if (!trimmed) throw new Error(`refusing to store an empty value for ${name}`);
  const secrets = await readSecrets();
  secrets[assertValidCredentialName(name)] = trimmed;
  await writeStateFile(secretsStateFile(), serializeSecrets(secrets), {
    mode: SECRETS_MODE,
  });
}

/** Remove one credential. Removing one that is not set is a no-op. */
export async function deleteCredential(name: string): Promise<void> {
  const secrets = await readSecrets();
  if (!(assertValidCredentialName(name) in secrets)) return;
  delete secrets[name];
  await writeStateFile(secretsStateFile(), serializeSecrets(secrets), {
    mode: SECRETS_MODE,
  });
}
