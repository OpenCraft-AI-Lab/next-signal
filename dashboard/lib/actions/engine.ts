"use server";

import { readFile } from "node:fs/promises";
import path from "node:path";
import YAML from "yaml";

import {
  parseEnginePreferences,
  serializeEnginePreferences,
  type Engine,
  type EnginePreferences,
  type Fallback,
  type OmlxParallel,
} from "@/lib/engine-preferences";
import { REPO_ROOT, engineStateFile } from "@/lib/paths";
import { writeStateFile } from "@/lib/state-file";

const MODELS_PATH = path.join(REPO_ROOT, "configs", "models.yaml");

/** Profiles the settings page surfaces, one per model-provider engine. */
const OMLX_PROFILE = "local";
const DEEPSEEK_PROFILE = "deepseek_smart";

/**
 * Last-resort baseline, used only when `configs/models.yaml` cannot be read at
 * all. Kept in sync with that file's shipped `local` / `deepseek_smart`
 * profiles — a stale literal here is visible in the panel, never silently
 * applied to a run.
 */
const UNCONFIGURED: EnginePreferences = {
  primary: "omlx",
  fallback: "deepseek",
  omlx: {
    // Empty until an operator points next-signal at a local server: no value
    // this repo could ship would be right, and borrowing one from the
    // environment would show the dashboard container's answer while the
    // scheduler resolves its own.
    baseUrl: "",
    model: "Qwen3.5-122B-A10B-mlx-oQ4",
    parallel: 2,
  },
  deepseek: { model: "deepseek-v4-flash", reasoning: "low" },
};

/** `models.yaml` provider names → the engine ids this page selects between. */
const PROVIDER_ENGINE: Record<string, Engine> = {
  omlx: "omlx",
  deepseek: "deepseek",
};

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function profile(models: Record<string, unknown>, name: string) {
  return asRecord(asRecord(models.profiles)[name]);
}

/**
 * The baseline every unset field reads back as: what the repo is actually
 * configured with, from `configs/models.yaml`. The local endpoint is not part
 * of it — that answer lives only in `engine.json`, so a fresh install shows an
 * empty field rather than a value read from this container's environment.
 */
async function configuredDefaults(): Promise<EnginePreferences> {
  let models: Record<string, unknown>;
  try {
    models = asRecord(YAML.parse(await readFile(MODELS_PATH, "utf-8")));
  } catch (err) {
    console.error(`${MODELS_PATH} is unreadable, using shipped defaults`, err);
    return UNCONFIGURED;
  }

  const local = profile(models, OMLX_PROFILE);
  const deepseek = profile(models, DEEPSEEK_PROFILE);
  // The local profile's own `fallback_profile` is already the answer to "where
  // does work go when the local box is down", so read it rather than inventing
  // a default. A fallback pointing at a provider with no engine here (openai,
  // gemini, the Anthropic API) is not representable, and reads as none.
  const fallbackProvider = String(
    profile(models, String(local.fallback_profile ?? "")).provider ?? "",
  );

  return {
    primary: PROVIDER_ENGINE[String(local.provider ?? "")] ?? UNCONFIGURED.primary,
    fallback: (PROVIDER_ENGINE[fallbackProvider] ?? "none") as Fallback,
    omlx: {
      baseUrl: UNCONFIGURED.omlx.baseUrl,
      model: String(local.model_id ?? UNCONFIGURED.omlx.model),
      parallel: (Number(asRecord(models.concurrency).omlx) ||
        UNCONFIGURED.omlx.parallel) as OmlxParallel,
    },
    deepseek: {
      model: String(deepseek.model_id ?? UNCONFIGURED.deepseek.model),
      reasoning: UNCONFIGURED.deepseek.reasoning,
    },
  };
}

/**
 * Read the live engine selection.
 *
 * Forgiving in the same way `getSchedule` is: the settings page is where an
 * operator would go to repair a bad value, so a damaged file must not stop it
 * rendering. Falls back to the configured baseline and logs.
 */
export async function getEnginePreferences(): Promise<EnginePreferences> {
  const base = await configuredDefaults();
  let raw: string;
  try {
    raw = await readFile(engineStateFile(), "utf-8");
  } catch {
    return base; // absent is normal — nobody has chosen an engine yet
  }
  try {
    return parseEnginePreferences(raw, base);
  } catch (err) {
    console.error(`${engineStateFile()} is unusable, using the configured baseline`, err);
    return base;
  }
}

/**
 * Write the live engine selection. Atomic (temp file + rename) so a concurrent
 * read never sees a torn file, matching the other state writers.
 *
 * No `revalidatePath`: `/settings` is `force-dynamic`, and the controls hold
 * their own state, so invalidating would only risk fighting an optimistic
 * update for a payload the next visit re-reads anyway.
 */
export async function setEnginePreferences(
  next: EnginePreferences,
): Promise<void> {
  await writeStateFile(engineStateFile(), serializeEnginePreferences(next));
}
