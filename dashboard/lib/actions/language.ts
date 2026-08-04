"use server";

import { access, mkdir, readFile, rename, writeFile } from "node:fs/promises";

import { DEFAULT_LOCALE, type Locale } from "@/lib/i18n/dictionaries";
import { languageStateFile, stateRoot } from "@/lib/paths";

const RECOGNIZED = new Set(["zh", "en"]);

/**
 * Read the live content-language preference.
 *
 * Deliberately more forgiving than `paca.core.language`, which raises on a
 * corrupt or unrecognized file: this value is read on every page render (the
 * nav is in the root layout), so raising here would take the whole dashboard
 * down over a state file — including the settings panel the operator would
 * use to rewrite it. Falls back to `DEFAULT_LOCALE` and logs. The loud path
 * still exists where it matters: pipeline runs raise, and `paca doctor`
 * reports the file.
 */
export async function getContentLanguage(): Promise<Locale> {
  let raw: string;
  try {
    raw = await readFile(languageStateFile(), "utf-8");
  } catch {
    return DEFAULT_LOCALE; // absent is normal (never seeded, or fresh volume)
  }
  try {
    const lang = String(JSON.parse(raw).content_language ?? "").trim().toLowerCase();
    if (!RECOGNIZED.has(lang)) {
      throw new Error(`unrecognized content_language: ${lang || "(empty)"}`);
    }
    return lang as Locale;
  } catch (err) {
    console.error(`${languageStateFile()} is unusable, falling back to ${DEFAULT_LOCALE}`, err);
    return DEFAULT_LOCALE;
  }
}

/**
 * Write the live content-language preference, read by every `paca` pipeline
 * container's `global` policy (`paca.core.language.global_language`).
 *
 * Called from the nav settings panel. This is NOT the UI-chrome locale — that
 * one lives in the `paca_locale` cookie and is set by `LanguageToggle`. The
 * two are independent settings and may hold different values. Atomic write
 * (temp file + rename) so a concurrent read never sees a torn file.
 */
export async function setContentLanguage(lang: string): Promise<void> {
  if (!RECOGNIZED.has(lang)) {
    throw new Error(`unrecognized content language: ${lang}`);
  }
  await mkdir(stateRoot(), { recursive: true });
  const target = languageStateFile();
  const tmp = `${target}.tmp`;
  const payload = JSON.stringify({
    content_language: lang,
    updated_at: new Date().toISOString(),
    updated_by: "dashboard",
  });
  await writeFile(tmp, payload, "utf-8");
  await rename(tmp, target);
}

/**
 * Seed the preference file with `seed` if it doesn't exist yet. Used once per
 * container start (see `instrumentation.ts`) — never overwrites an existing
 * file, so it can't clobber a preference a user already set.
 */
export async function ensureContentLanguage(seed: string): Promise<void> {
  const target = languageStateFile();
  try {
    await access(target);
    return; // already exists — never overwrite
  } catch {
    // fall through and create it
  }
  await setContentLanguage(RECOGNIZED.has(seed) ? seed : "en");
}
