/**
 * Knowledge retention ramp — shared by the review histogram and the
 * design-system swatches. Same shape as `lib/score.ts`, on its own token group:
 * the score ramp encodes the radar's *verdict*, so reusing it here would render
 * a doc at the 120-day stage green, reading as "scored well" rather than
 * "consolidated".
 *
 *   fragile (pale in light / dim in dark) → consolidated (deep / bright)
 *
 * The lightness endpoints come from CSS variables (`--kb-l-lo`, `--kb-l-hi`), so
 * one call site is correct in both themes. That is what lets the histogram stay
 * a server component: the server cannot know the reader's theme, so the theme
 * has to resolve in the cascade rather than in JS.
 */

const clamp01 = (t: number) => Math.max(0, Math.min(1, t));

/** Ramp colour at position `t` (0 = fragile, 1 = consolidated). */
export function retentionColor(t: number): string {
  const p = Number(clamp01(t).toFixed(4));
  return `hsl(var(--kb-h) var(--kb-s) calc(var(--kb-l-lo) + (var(--kb-l-hi) - var(--kb-l-lo)) * ${p}))`;
}

/**
 * Docs past the final stage. Deliberately off the ramp — they are neither
 * decaying nor scheduled, so the deep end of a continuum they have left would
 * read as "most consolidated" on a scale they no longer sit on.
 */
export const RETENTION_HELD = "var(--kb-held)";
