"use server";

import { revalidatePath } from "next/cache";

import { spawnPacaDetached } from "@/lib/actions/spawn-paca";
import {
  getDictionary,
  normalizeLocale,
  type Locale,
} from "@/lib/i18n/dictionaries";
import { advanceReview } from "@/lib/knowledge/review";
import { wikiRoot } from "@/lib/paths";

/**
 * Mark a due review card seen: advance its stage and revalidate the page so the
 * card leaves the due list. A plain DB write with no LLM, so it completes in the
 * request. MUST stay a POST (server action) — a GET could let a prefetch or a
 * crawler advance the curve.
 *
 * `docPath` comes from a card the server itself rendered, but it is shape-checked
 * before hitting the DB rather than trusted blindly.
 */
export async function markReviewSeen(
  docPath: string,
): Promise<{ ok: boolean }> {
  if (!docPath || !docPath.endsWith(".md") || docPath.split(/[\\/]/).includes("..")) {
    return { ok: false };
  }
  try {
    await advanceReview(docPath);
  } catch {
    // A transient DB error must not leave the button hung on "saving"; the card
    // stays due and the reader can retry.
    return { ok: false };
  }
  revalidatePath("/knowledge");
  return { ok: true };
}

/**
 * Kick off `paca knowledge review`: reconcile the wiki against the review table
 * (enroll new docs, unenroll gone ones). Detached and returns immediately —
 * walking the wiki is fast, but the shared launcher's contract is fire-and-report
 * "started", and this keeps the "seen" path and this path uniform.
 */
export async function refreshReviews(
  localeValue?: Locale,
): Promise<{ ok: boolean; message: string }> {
  const t = getDictionary(normalizeLocale(localeValue));
  const result = await spawnPacaDetached(["knowledge", "review"], {
    extraEnv: { PACA_WIKI_DIR: wikiRoot() },
    verb: t.knowledge.review.refreshVerb,
    logTag: "knowledge-review",
  });
  return result.ok
    ? { ok: true, message: t.knowledge.review.refreshStarted }
    : result;
}
