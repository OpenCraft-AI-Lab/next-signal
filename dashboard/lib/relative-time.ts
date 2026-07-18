import { getDictionary, type Locale } from "@/lib/i18n/dictionaries";

/**
 * "X ago" formatter for the nav last-run hint. Shows the most relevant
 * unit (sec / min / hr / day) without bothering with full timestamps —
 * the operator just needs a quick sanity check that the pipeline ran.
 */
export function timeAgo(
  iso: string | null | undefined,
  now: Date = new Date(),
  locale: Locale = "en",
): string {
  const t = getDictionary(locale).relativeTime;
  if (!iso) return t.never;
  const then = new Date(iso);
  const diffMs = now.getTime() - then.getTime();
  if (Number.isNaN(diffMs)) return t.invalid;
  if (diffMs < 0) return t.justNow;
  const secs = Math.round(diffMs / 1000);
  if (secs < 60) return t.seconds(secs);
  const mins = Math.round(secs / 60);
  if (mins < 60) return t.minutes(mins);
  const hours = Math.round(mins / 60);
  if (hours < 24) return t.hours(hours);
  const days = Math.round(hours / 24);
  if (days < 30) return t.days(days);
  const months = Math.round(days / 30);
  return t.months(months);
}
