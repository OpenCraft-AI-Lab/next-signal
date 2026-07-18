"use client";

import { ChevronLeft, Download } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type CSSProperties } from "react";
import { createParser, parseAsStringLiteral, useQueryStates } from "nuqs";

import { useI18n } from "@/components/i18n-provider";
import { Segmented, SegmentedItem } from "@/components/ui/segmented";
import { scoreColor } from "@/lib/score";
import {
  DEFAULT_MIN_SCORE,
  parseBoolValue,
  parseDayValue,
  parseMinScoreValue,
  serializeBoolValue,
  SORT_OPTIONS,
} from "@/lib/radar/filter-shared";

const parseBool = createParser({
  parse: parseBoolValue,
  serialize: serializeBoolValue,
});

const parseMinScore = createParser({
  parse: parseMinScoreValue,
  serialize: String,
});

const parseDay = createParser({
  parse: parseDayValue,
  serialize: String,
});

const radarFilterParsers = {
  sort: parseAsStringLiteral(SORT_OPTIONS).withDefault("score-desc"),
  novelOnly: parseBool.withDefault(true),
  minScore: parseMinScore.withDefault(DEFAULT_MIN_SCORE),
  day: parseDay,
  lastFeedOnly: parseBool.withDefault(false),
};

export function FilterBar({
  total,
  shown,
  isToday,
  today,
}: {
  total: number;
  shown: number;
  isToday: boolean;
  today: string;
}) {
  const { t } = useI18n();
  const [filters, setFilters] = useQueryStates(radarFilterParsers, {
    shallow: false,
  });
  const searchParams = useSearchParams();
  const sliderColor =
    filters.minScore > 0 ? scoreColor(filters.minScore) : "var(--text-4)";

  // Download the current view: the live URL params already encode the active
  // filter, so the export route resolves the same items the page shows.
  const exportHref = (format: "md" | "pdf") => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("export");
    params.set("format", format);
    return `/api/radar/export?${params.toString()}`;
  };

  return (
    <>
      <div className="sec-head">
        <h2 className="sec-title">
          {isToday ? t.radar.filters.todayTitle : t.radar.filters.itemsTitle}
        </h2>
        <span className="sec-sub">{t.radar.filters.shownOf(shown, total)}</span>
      </div>
      <div className="filterbar">
        <Segmented>
          {SORT_OPTIONS.map((sort) => (
            <SegmentedItem
              key={sort}
              active={filters.sort === sort}
              onClick={() => setFilters({ sort })}
            >
              {t.radar.filters.sort[sort]}
            </SegmentedItem>
          ))}
        </Segmented>
        <div className="vdiv" />
        <button
          type="button"
          className={`f-toggle${filters.novelOnly ? " on" : ""}`}
          aria-pressed={filters.novelOnly}
          onClick={() => setFilters({ novelOnly: !filters.novelOnly })}
          title={t.radar.filters.novelOnlyTitle}
        >
          <span className="dot" />
          {t.radar.filters.novelOnly}
        </button>
        {isToday && (
          <button
            type="button"
            className={`f-toggle${filters.lastFeedOnly ? " on" : ""}`}
            aria-pressed={filters.lastFeedOnly}
            onClick={() => setFilters({ lastFeedOnly: !filters.lastFeedOnly })}
            title={t.radar.filters.lastFeedTitle}
          >
            <span className="dot" />
            {t.radar.filters.lastFeed}
          </button>
        )}
        <label className="rangewrap">
          <span className="rlabel">{t.radar.filters.score}</span>
          <input
            className="scorerange"
            type="range"
            min="0"
            max="100"
            step="5"
            value={filters.minScore}
            onChange={(event) =>
              setFilters({ minScore: Number(event.target.value) })
            }
            style={{ "--score-thumb": sliderColor } as CSSProperties}
          />
          <span className="rval" style={{ color: sliderColor }}>
            {filters.minScore}
          </span>
        </label>
        <div className="row gap-6" style={{ marginLeft: "auto" }}>
          <a
            className="btn ghost sm"
            href={exportHref("md")}
            download
            title={t.radar.filters.downloadMd}
          >
            <Download size={13} />
            MD
          </a>
          <a
            className="btn ghost sm"
            href={exportHref("pdf")}
            download
            title={t.radar.filters.downloadPdf}
          >
            <Download size={13} />
            PDF
          </a>
        </div>
        {!isToday && (
          <Link
            href="/radar"
            className="btn ghost sm"
            title={t.radar.filters.backTodayTitle(today)}
          >
            <ChevronLeft size={13} />
            {t.radar.filters.backToday}
          </Link>
        )}
      </div>
    </>
  );
}
