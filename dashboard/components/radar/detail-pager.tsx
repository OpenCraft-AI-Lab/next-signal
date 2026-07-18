import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { ScoreChip } from "@/components/radar/badges";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import {
  serializeRadarFilters,
  type RadarFilters,
} from "@/lib/radar/filter-params";
import {
  getFilteredTodayList,
  getLastFeedBounds,
  todayInRadarTz,
} from "@/lib/radar/queries";

export async function DetailPager({
  itemId,
  filters,
  position,
}: {
  itemId: number;
  filters: RadarFilters;
  position: "top" | "bottom";
}) {
  const locale = await getLocale();
  const t = getDictionary(locale);
  const today = todayInRadarTz();
  const day = filters.day ?? today;
  const useLastFeed =
    filters.lastFeedOnly && (filters.day === null || filters.day === today);
  const { analyzeStart } = useLastFeed
    ? await getLastFeedBounds(day)
    : { analyzeStart: null };
  const list = await getFilteredTodayList(filters, analyzeStart, day);
  const idx = list.findIndex((item) => item.id === itemId);
  const inFilter = idx !== -1;
  const prev = inFilter && idx > 0 ? list[idx - 1] : null;
  const next = inFilter ? (list[idx + 1] ?? null) : null;
  const remaining = inFilter ? Math.max(list.length - idx - 1, 0) : 0;
  const suffix = serializeRadarFilters(filters);

  // When the current item isn't in the filtered list (e.g. operator
  // followed a deep link to a low-score item under default minScore=65),
  // show an honest out-of-set notice rather than fabricating a "X left"
  // counter or shipping Next buttons that jump to an unrelated row.
  if (!inFilter) {
    if (position === "bottom") {
      return (
        <div className="nextcard-end">
          <span className="mono muted-2" style={{ fontSize: 12.5 }}>
            {t.radar.pager.outside(list.length)}
          </span>
          <Link className="btn ghost sm" href={`/radar${suffix}`}>
            {t.radar.detail.back}
          </Link>
        </div>
      );
    }
    return (
      <div className="detailnav">
        <span
          className="mono detailnav-count"
          title="Not in the current filter set"
        >
          {t.radar.pager.notInFilter(list.length)}
        </span>
        <Link className="btn ghost sm" href={`/radar${suffix}`}>
          {t.radar.detail.back}
        </Link>
      </div>
    );
  }

  if (position === "bottom") {
    return next ? (
      <Link
        className="nextcard card hoverable"
        href={`/radar/${next.id}${suffix}`}
      >
        <div className="col" style={{ gap: 4, minWidth: 0, textAlign: "left" }}>
          <span className="eyebrow">{t.radar.pager.nextItem(remaining)}</span>
          <span className="nextcard-title elip">{next.title}</span>
        </div>
        <div
          className="row gap-12"
          style={{ alignItems: "center", flexShrink: 0 }}
        >
          <ScoreChip value={next.score} size="sm" />
          <ChevronRight size={18} className="muted-2" />
        </div>
      </Link>
    ) : (
      <div className="nextcard-end">
        <span className="mono muted-2" style={{ fontSize: 12.5 }}>
          {t.radar.pager.last}
        </span>
        <Link className="btn ghost sm" href={`/radar${suffix}`}>
          {t.radar.detail.back}
        </Link>
      </div>
    );
  }

  return (
    <div className="detailnav">
      <span className="mono detailnav-count">
        {t.radar.pager.of(idx + 1, list.length)}
        <span className="detailnav-left">
          · {t.radar.pager.left(remaining)}
        </span>
      </span>
      <div className="row" style={{ gap: 6 }}>
        {prev ? (
          <Link
            className="btn icon sm"
            title={t.radar.pager.previousTitle(prev.title)}
            href={`/radar/${prev.id}${suffix}`}
          >
            <ChevronRight size={14} style={{ transform: "rotate(180deg)" }} />
          </Link>
        ) : (
          <button
            className="btn icon sm"
            disabled
            title={t.radar.pager.noPrevious}
          >
            <ChevronRight size={14} style={{ transform: "rotate(180deg)" }} />
          </button>
        )}
        {next ? (
          <Link
            className="btn sm"
            title={t.radar.pager.nextTitle(next.title)}
            href={`/radar/${next.id}${suffix}`}
          >
            {t.radar.pager.next} <ChevronRight size={14} />
          </Link>
        ) : (
          <button className="btn sm" disabled title={t.radar.pager.noMore}>
            {t.radar.pager.next} <ChevronRight size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
