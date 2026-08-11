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

/** The two embedder profiles that have a real shipped default. */
const OMLX_EMBEDDER = "local";
const OPENAI_EMBEDDER = "openai";

/**
 * Last-resort baseline, used only when `configs/models.yaml` cannot be read at
 * all. Kept in sync with that file's shipped `embedders` entries — a stale
 * literal here is visible in the panel, never silently applied to a run.
 *
 * There is no compatible entry, here or in the YAML: its URL, key variable, and
 * vector-space id have no honest default, and inventing one would let a card
 * look configured while pointing nowhere.
 */
const UNCONFIGURED: EmbeddingPreferences = {
  provider: "omlx",
  omlx: { model: "Qwen3-Embedding-0.6B-8bit" },
  openai: { model: "text-embedding-3-small" },
  openaiCompatible: null,
};

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function embedder(models: Record<string, unknown>, name: string) {
  return asRecord(asRecord(models.embedders)[name]);
}

/**
 * The baseline every unset field reads back as: what the repo is actually
 * configured with, from the same `embedders:` profiles the pipeline reads.
 */
async function configuredDefaults(): Promise<EmbeddingPreferences> {
  let models: Record<string, unknown>;
  try {
    models = asRecord(YAML.parse(await readFile(MODELS_PATH, "utf-8")));
  } catch (err) {
    console.error(`${MODELS_PATH} is unreadable, using shipped defaults`, err);
    return UNCONFIGURED;
  }

  return {
    provider: UNCONFIGURED.provider,
    omlx: {
      model: String(
        embedder(models, OMLX_EMBEDDER).model_id ?? UNCONFIGURED.omlx.model,
      ),
    },
    openai: {
      model: String(
        embedder(models, OPENAI_EMBEDDER).model_id ?? UNCONFIGURED.openai.model,
      ),
    },
    openaiCompatible: null,
  };
}

/**
 * Read the live embedding selection.
 *
 * Forgiving in the same way `getEnginePreferences` is: the settings page is
 * where an operator would go to repair a bad value, so a damaged file must not
 * stop it rendering. Falls back to the configured baseline and logs. The
 * pipeline stays strict — it refuses to embed under state it cannot read.
 */
export async function getEmbeddingPreferences(): Promise<EmbeddingPreferences> {
  const base = await configuredDefaults();
  let raw: string;
  try {
    raw = await readFile(embeddingStateFile(), "utf-8");
  } catch {
    return base; // absent is normal — nobody has chosen an embedder yet
  }
  try {
    return parseEmbeddingPreferences(raw, base);
  } catch (err) {
    console.error(
      `${embeddingStateFile()} is unusable, using the configured baseline`,
      err,
    );
    return base;
  }
}

/**
 * Write the live embedding selection. Atomic (temp file + rename) so an item
 * resolving its snapshot mid-write never reads a torn file.
 *
 * Writes only `embedding.json`: engine, coding-agent, schedule, and language
 * state are separate files owned by separate sections.
 */
export async function setEmbeddingPreferences(
  next: EmbeddingPreferences,
): Promise<void> {
  await writeStateFile(embeddingStateFile(), serializeEmbeddingPreferences(next));
}
