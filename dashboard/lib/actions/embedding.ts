"use server";

import { readFile } from "node:fs/promises";
import path from "node:path";
import YAML from "yaml";

import {
  parseEmbeddingPreferences,
  serializeEmbeddingPreferences,
  type EmbeddingPreferences,
} from "@/lib/embedding-preferences";
import { REPO_ROOT, embeddingStateFile } from "@/lib/paths";
import { writeStateFile } from "@/lib/state-file";

const MODELS_PATH = path.join(REPO_ROOT, "configs", "models.yaml");

/** The two embedder profiles that have a real shipped model suggestion. */
const OMLX_EMBEDDER = "local";
const OPENAI_EMBEDDER = "openai";

/**
 * Suggested model ids for a pane the operator is filling in.
 *
 * Prefill, not defaults: nothing here selects a provider or reaches the
 * pipeline. The endpoint is absent on purpose — a local server's address is the
 * one value this repo cannot guess, so its field starts empty.
 */
export interface EmbeddingPrefill {
  omlxModel: string;
  openaiModel: string;
}

/**
 * Last-resort suggestions, used only when `configs/models.yaml` cannot be read
 * at all. Kept in sync with that file's shipped `embedders` entries — a stale
 * literal here shows up in an empty form field, never in a run.
 */
const FALLBACK_PREFILL: EmbeddingPrefill = {
  omlxModel: "Qwen3-Embedding-0.6B-8bit",
  openaiModel: "text-embedding-3-small",
};

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function embedder(models: Record<string, unknown>, name: string) {
  return asRecord(asRecord(models.embedders)[name]);
}

/** What an unconfigured pane opens with, from the repo's own profiles. */
export async function getEmbeddingPrefill(): Promise<EmbeddingPrefill> {
  let models: Record<string, unknown>;
  try {
    models = asRecord(YAML.parse(await readFile(MODELS_PATH, "utf-8")));
  } catch (err) {
    console.error(`${MODELS_PATH} is unreadable, using shipped suggestions`, err);
    return FALLBACK_PREFILL;
  }

  return {
    omlxModel: String(
      embedder(models, OMLX_EMBEDDER).model_id ?? FALLBACK_PREFILL.omlxModel,
    ),
    openaiModel: String(
      embedder(models, OPENAI_EMBEDDER).model_id ?? FALLBACK_PREFILL.openaiModel,
    ),
  };
}

/** Nothing chosen and nothing configured — the fresh-install state. */
const UNSELECTED: EmbeddingPreferences = {
  provider: null,
  omlx: null,
  openai: null,
  openaiCompatible: null,
};

/**
 * Read the live embedding selection.
 *
 * Forgiving in the same way `getEnginePreferences` is: the settings page is
 * where an operator would go to repair a bad value, so a damaged file must not
 * stop it rendering. Falls back to unselected and logs. The pipeline stays
 * strict — it refuses to embed under state it cannot read.
 */
export async function getEmbeddingPreferences(): Promise<EmbeddingPreferences> {
  let raw: string;
  try {
    raw = await readFile(embeddingStateFile(), "utf-8");
  } catch {
    return UNSELECTED; // absent is normal — nobody has chosen an embedder yet
  }
  try {
    return parseEmbeddingPreferences(raw);
  } catch (err) {
    console.error(
      `${embeddingStateFile()} is unusable, showing nothing as selected`,
      err,
    );
    return UNSELECTED;
  }
}

/**
 * Write the live embedding selection. Atomic (temp file + rename) so an item
 * resolving its snapshot mid-write never reads a torn file.
 *
 * Writes only `embedding.json`: engine, coding-agent, schedule, and language
 * state are separate files owned by separate sections.
 *
 * Once a provider has been selected, this section is permanent: a changed
 * embedding model produces vectors that cannot be compared against ones
 * already stored. This check is defense in depth behind the disabled UI — the
 * section renders read-only once locked, but a stale client or a direct call
 * must not be able to smuggle a second write past that.
 */
export async function setEmbeddingPreferences(
  next: EmbeddingPreferences,
): Promise<void> {
  const current = await getEmbeddingPreferences();
  if (current.provider !== null) {
    throw new Error(
      "Radar Embedding is locked: an embedder has already been selected and cannot be changed.",
    );
  }
  await writeStateFile(embeddingStateFile(), serializeEmbeddingPreferences(next));
}
