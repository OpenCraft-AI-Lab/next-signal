/**
 * Pure filter primitives shared by server-side loader / serializer
 * (`filter-params.ts`) and the client-side `<FilterBar />` control.
 *
 * Keep this file free of `nuqs/server`: client controls import it too.
 */
export const SORT_OPTIONS = ["score-desc", "score-asc", "newest"] as const;
export type RadarSort = (typeof SORT_OPTIONS)[number];

export const SORT_LABELS: Record<RadarSort, string> = {
  "score-desc": "Score ↓",
  "score-asc": "Score ↑",
  newest: "Newest",
};

export const DEFAULT_MIN_SCORE = 65;

export function parseBoolValue(value: string): boolean {
  return value === "1" || value.toLowerCase() === "true";
}

export function serializeBoolValue(value: boolean): string {
  return value ? "1" : "0";
}

export function parseMinScoreValue(value: string): number | null {
  const n = Number.parseInt(value, 10);
  if (!Number.isFinite(n)) return null;
  return Math.max(0, Math.min(100, Math.round(n / 5) * 5));
}

export function parseDayValue(value: string): string | null {
  // Accept ISO YYYY-MM-DD only; anything else means today.
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
}
