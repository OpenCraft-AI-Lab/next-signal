"use server";

import { spawnPacaDetached } from "@/lib/actions/spawn-paca";
import {
  getDictionary,
  normalizeLocale,
  type Locale,
} from "@/lib/i18n/dictionaries";
import type { RecapKey } from "@/lib/radar/recap";

const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Trigger a recap generation and return immediately.
 *
 * Fire-and-forget on purpose: synthesizing a week's signals is a 30-60s local
 * inference job, far past what a request can hold open. The panel polls
 * `/api/radar/recap` for the row's status afterwards.
 *
 * Range values arrive from the client, so they're shape-checked before being
 * passed on. `spawnPacaDetached` uses an argv array rather than a shell, so
 * this is about failing fast on garbage rather than about injection.
 */
export async function generateRecap(
  key: RecapKey,
  regenerate: boolean,
  localeValue?: Locale,
): Promise<{ ok: boolean; message: string }> {
  const t = getDictionary(normalizeLocale(localeValue));
  if (!DAY_RE.test(key.since) || !DAY_RE.test(key.until)) {
    return { ok: false, message: t.radar.recap.badRange };
  }
  if (key.until < key.since) {
    return { ok: false, message: t.radar.recap.badRange };
  }

  const minScore = Math.min(100, Math.max(0, Math.round(key.minScore)));
  const argv = [
    "info-radar",
    "recap",
    "--since",
    key.since,
    "--until",
    key.until,
    "--min-score",
    String(minScore),
  ];
  if (key.novelOnly) argv.push("--novel-only");
  if (regenerate) argv.push("--regenerate");

  return spawnPacaDetached(argv, {
    verb: t.radar.recap.verb,
    logTag: "radar-recap",
  });
}
