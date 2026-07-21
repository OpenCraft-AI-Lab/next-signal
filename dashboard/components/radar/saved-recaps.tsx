import Link from "next/link";

import type { getDictionary, Locale } from "@/lib/i18n/dictionaries";
import { serializeBoolValue } from "@/lib/radar/filter-shared";
import { displayDay } from "@/lib/radar/queries";
import type { RecapSummary } from "@/lib/radar/recap";

type Dict = ReturnType<typeof getDictionary>;

/**
 * Browse list of previously-generated recaps. Each row links back to the
 * recap panel (`#recap`) with the stored range AND gate — the gate is part of
 * the recap's identity, so it has to travel in the URL for the panel to resolve
 * the same cached row. Because `minScore` / `novelOnly` are shared with the
 * filter bar, opening a recap also re-filters the item list to match, keeping
 * the recap and the items it summarizes the same population.
 *
 * Reuses the `.card` + `.pastrow` shell the Past days rows use, so it needs no
 * new design-system class.
 */
export function SavedRecaps({
  recaps,
  locale,
  t,
}: {
  recaps: RecapSummary[];
  locale: Locale;
  t: Dict;
}) {
  return (
    <>
      <div className="sec-head">
        <h2 className="sec-title">{t.radar.recap.savedTitle}</h2>
        <span className="sec-sub">{t.radar.recap.savedSub}</span>
      </div>
      <div className="col gap-8">
        {recaps.map((recap) => (
          <Link
            key={`${recap.since}:${recap.until}:${recap.minScore}:${recap.novelOnly}`}
            href={hrefFor(recap)}
            className="card"
            style={{ overflow: "hidden", textDecoration: "none" }}
          >
            <div className="pastrow">
              <span className="mono" style={{ fontWeight: 600, fontSize: 13 }}>
                {rangeLabel(recap, locale)}
              </span>
              {recap.itemCount != null && (
                <span className="chip mono" style={{ fontSize: 10 }}>
                  {t.radar.recap.savedSignals(recap.itemCount)}
                </span>
              )}
              {recap.minScore > 0 && (
                <span className="chip mono" style={{ fontSize: 10 }}>
                  ≥{recap.minScore}
                </span>
              )}
              {recap.novelOnly && (
                <span className="chip mono" style={{ fontSize: 10 }}>
                  {t.radar.recap.savedNovel}
                </span>
              )}
              {recap.headline && (
                <span
                  className="elip muted"
                  style={{ flex: 1, minWidth: 0, fontSize: 13 }}
                >
                  {recap.headline}
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}

function rangeLabel(recap: RecapSummary, locale: Locale): string {
  const since = displayDay(recap.since, locale);
  if (recap.since === recap.until) return since;
  return `${since} – ${displayDay(recap.until, locale)}`;
}

function hrefFor(recap: RecapSummary): string {
  // Deliberately omit `day` so opening a recap keeps the reader on today's item
  // view; the panel (#recap) resolves the recap from these params.
  const params = new URLSearchParams({
    minScore: String(recap.minScore),
    novelOnly: serializeBoolValue(recap.novelOnly),
    recapSince: recap.since,
    recapUntil: recap.until,
  });
  return `/radar?${params.toString()}#recap`;
}
