"use server";

import { readFile } from "node:fs/promises";

import { runCliAwaited } from "@/lib/actions/spawn-cli";
import { getCredentialPresence } from "@/lib/actions/secrets";
import {
  PROVIDER_CREDENTIAL,
  type GbrainReadiness,
  type KnowledgeEmbeddingProvider,
} from "@/lib/knowledge-embedding";
import { gbrainConfigFile } from "@/lib/paths";

const UNKNOWN: GbrainReadiness = { state: "indeterminate", provider: null, model: null };
const UNINITIALIZED: GbrainReadiness = { state: "not_initialized", provider: null, model: null };

/**
 * GBrain's three-state readiness (plus "indeterminate" for an unreadable
 * config), computed dashboard-natively by reading `.gbrain/config.json`
 * directly — mirroring `next_signal.integrations.gbrain.brain_initialised()`
 * / `configured_embedding_model()` — rather than shelling out to
 * `next-signal doctor` or `gbrain doctor --fast`, which reports a healthy
 * brain even when none exists.
 */
export async function getGbrainReadiness(): Promise<GbrainReadiness> {
  const configPath = gbrainConfigFile();
  if (!configPath) return UNKNOWN; // GBRAIN_HOME unset — cannot determine

  let raw: string;
  try {
    raw = await readFile(configPath, "utf-8");
  } catch {
    return UNINITIALIZED; // no config file — the expected fresh-install state
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return UNKNOWN; // present but unreadable — not the same as "not initialized"
  }
  if (typeof parsed !== "object" || parsed === null) return UNKNOWN;

  const embeddingModel = (parsed as Record<string, unknown>).embedding_model;
  if (typeof embeddingModel !== "string" || !embeddingModel.trim()) return UNKNOWN;

  const [provider, ...rest] = embeddingModel.trim().split(":");
  const model = rest.join(":");
  const credentialName = PROVIDER_CREDENTIAL[provider as KnowledgeEmbeddingProvider];
  if (!credentialName) {
    return { state: "ready", provider, model };
  }
  const presence = await getCredentialPresence();
  return {
    state: presence[credentialName] ? "ready" : "credential_missing",
    provider,
    model,
  };
}

/**
 * Run `next-signal knowledge gbrain-init --embedding-model <provider>:<model>`
 * to completion. Awaited, not detached — the caller needs the actual result
 * to decide whether to lock its section. A failure (including "already
 * initialised", which the CLI reports as one) is never treated as success.
 */
export async function initializeGbrain(
  provider: KnowledgeEmbeddingProvider,
  model: string,
): Promise<{ ok: boolean; message: string }> {
  const embeddingModel = `${provider}:${model.trim()}`;
  const result = await runCliAwaited([
    "knowledge",
    "gbrain-init",
    "--embedding-model",
    embeddingModel,
  ]);
  if (result.ok) {
    return { ok: true, message: result.stdout.trim() || `GBrain initialised with ${embeddingModel}.` };
  }
  return { ok: false, message: (result.stderr || result.stdout).trim().slice(0, 2000) };
}
