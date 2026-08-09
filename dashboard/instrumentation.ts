/**
 * Runs once per server process start (Next.js instrumentation hook, stable
 * since Next 15 — no `experimental.instrumentationHook` flag needed).
 *
 * Seeds the shared content-language preference file if it doesn't exist yet,
 * so a freshly started dashboard — before anyone has ever touched the
 * language toggle — still leaves the pipeline in a defined state rather than
 * relying solely on `next_signal.core.language`'s hardcoded fallback. Never
 * overwrites an existing file (see `ensureContentLanguage`), so this can't
 * clobber a preference a user already set.
 */
export async function register(): Promise<void> {
  // Only runs in the Node.js runtime (not edge) — file I/O against the
  // shared /state volume isn't meaningful in an edge worker.
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  const { ensureContentLanguage } = await import("@/lib/actions/language");
  const { DEFAULT_LOCALE } = await import("@/lib/i18n/dictionaries");

  try {
    await ensureContentLanguage(DEFAULT_LOCALE);
  } catch (err) {
    // Startup must not crash the dashboard over a state-file seed failure —
    // the `global` policy's hardcoded fallback keeps the pipeline working
    // either way. Log loudly so it doesn't stay silently broken.
    console.error("failed to seed content-language preference file", err);
  }
}
