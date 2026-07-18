/**
 * Continuous score-color ramp shared by ScoreChip, the histogram, the
 * filter-bar range slider, and the design-system gradient stripe.
 * Mirrors `dashboard/design/data.js::PACA.scoreHue / scoreLOff`.
 *
 *   orange(low ~28°) → yellow(~55°) → green(high ~143°)
 *
 * Saturation / lightness come from CSS variables (`--score-s`, `--score-l`)
 * so the same hue reads correctly in both light and dark themes.
 */

const clamp01 = (t: number) => Math.max(0, Math.min(1, t));

/** Hue (deg) for a 0..100 score. */
export function scoreHue(s: number): number {
  const t = clamp01(s / 100);
  return t < 0.5
    ? 28 + (55 - 28) * (t / 0.5)
    : 55 + (143 - 55) * ((t - 0.5) / 0.5);
}

/**
 * Lightness offset (percentage) to *subtract* from `var(--score-l)` so the
 * green (upper) half reads darker / more saturated than a naive HSL ramp.
 * Returns 0 for the lower half.
 */
export function scoreLOff(s: number): number {
  const t = clamp01(s / 100);
  return t < 0.5 ? 0 : Math.round(((t - 0.5) / 0.5) * 15);
}

/**
 * Inline-style helper: returns the `hsl(...)` color expression for a score,
 * using the active theme's `--score-s` / `--score-l` variables.
 */
export function scoreColor(s: number): string {
  return `hsl(${scoreHue(s)} var(--score-s) calc(var(--score-l) - ${scoreLOff(s)}%))`;
}

/** Same color but as a translucent tint (`/ var(--score-tint-a)`). */
export function scoreTint(s: number): string {
  return `hsl(${scoreHue(s)} var(--score-s) calc(var(--score-l) - ${scoreLOff(s)}%) / var(--score-tint-a))`;
}
