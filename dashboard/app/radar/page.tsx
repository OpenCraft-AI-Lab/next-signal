import { cookies } from "next/headers";

import { RadarAlpaca } from "@/components/brand/radar-alpaca";
import { DayGroup } from "@/components/radar/day-group";
import { FilterBar } from "@/components/radar/filter-bar";
import { MarkdownText } from "@/components/radar/markdown-text";
import { PullAnalyzeButton } from "@/components/radar/pull-analyze-button";
import { RecapControls } from "@/components/radar/recap-controls";
import { RecapPanel } from "@/components/radar/recap-panel";
import { RunProgress } from "@/components/radar/run-progress";
import { SavedRecaps } from "@/components/radar/saved-recaps";
import { SmartRecapSection } from "@/components/radar/smart-recap-section";
import { SignalCard } from "@/components/radar/signal-card";
import { TodayTracker } from "@/components/radar/today-tracker";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import { loadRadarFilters } from "@/lib/radar/filter-params";
import { getRecap, listRecaps } from "@/lib/radar/recap";
import {
  displayDay,
  getDayGroups,
  getItemsForDay,
  getLastFeedBounds,
  getLastFeedSummary,
  todayInRadarTz,
} from "@/lib/radar/queries";
import { RECAP_COLLAPSED_COOKIE } from "@/lib/radar/recap-ui";
import { getRunState } from "@/lib/radar/run-state";
import { timeAgo } from "@/lib/relative-time";

export default async function RadarPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [filters, locale] = await Promise.all([
    loadRadarFilters(searchParams),
    getLocale(),
  ]);
  const t = getDictionary(locale);
  // `?export=1` renders a print-only variant (header + signal cards, no
  // interactive chrome) for headless-Chrome PDF capture; see the export route.
  const raw = await searchParams;
  const exportMode = raw.export === "1";
  const today = todayInRadarTz();
  const pinnedDay = filters.day;
  const focusDay = pinnedDay ?? today;
  const isToday = pinnedDay === null || pinnedDay === today;

  // "Last feed only" needs both click/run starts: the pull timestamp bounds
  // `pulled_by_source`, the analyze timestamp bounds everything else.
  // Lazy-resolve only when the filter is active.
  const useLastFeed = isToday && filters.lastFeedOnly;
  const { analyzeStart, pullStart } = useLastFeed
    ? await getLastFeedBounds(focusDay)
    : { analyzeStart: null, pullStart: null };

  // Recap range: presets resolve server-side so "last 7 days" means the radar
  // timezone's last 7 days, not the browser's. The quality gate is inherited
  // from the filter bar, so the recap and the item list describe the same
  // population — and a different gate is a different cached recap.
  const recapPresets = {
    last7: { since: shiftDay(today, -6), until: today },
    last30: { since: shiftDay(today, -29), until: today },
  };
  const recapKey = {
    since: asDay(raw.recapSince) ?? recapPresets.last7.since,
    until: asDay(raw.recapUntil) ?? recapPresets.last7.until,
    minScore: filters.minScore,
    novelOnly: filters.novelOnly,
  };
  // Collapse preference persists in a cookie so it survives the full re-render
  // a filter change triggers. Force open when the URL targets a specific recap
  // (a saved-recap click) so reopening one never lands on a collapsed header.
  const hasExplicitRange =
    asDay(raw.recapSince) !== null || asDay(raw.recapUntil) !== null;
  const recapCollapsed = (await cookies()).get(RECAP_COLLAPSED_COOKIE)?.value === "1";
  const recapOpen = hasExplicitRange || !recapCollapsed;

  const [items, unfilteredItems, pastDays, lastFeed, runState, recap, savedRecaps] =
    await Promise.all([
      getItemsForDay(focusDay, filters, analyzeStart),
      // Used for the "N kept" subtitle + the X/Y counter in the filter bar.
      // Bounded by the analyze cluster when `lastFeedOnly` is on so the
      // counter matches the surrounding view.
      getItemsForDay(
        focusDay,
        { ...filters, novelOnly: false, minScore: 0 },
        analyzeStart,
      ),
      isToday ? getDayGroups(14) : Promise.resolve([]),
      getLastFeedSummary(),
      getRunState(),
      exportMode ? Promise.resolve(null) : getRecap(recapKey),
      isToday && !exportMode ? listRecaps() : Promise.resolve([]),
    ]);

  return (
    <div className={exportMode ? "page export-mode" : "page page-enter"}>
      {!exportMode && (
      <PullAnalyzeButton
        lastPull={
          lastFeed.pull.latestAt
            ? {
                ago: timeAgo(lastFeed.pull.latestAt, new Date(), locale),
                count: lastFeed.pull.count,
              }
            : null
        }
        lastAnalyze={
          lastFeed.analyze.latestAt
            ? {
                ago: timeAgo(lastFeed.analyze.latestAt, new Date(), locale),
                count: lastFeed.analyze.count,
              }
            : null
        }
        unanalyzed={lastFeed.unanalyzed}
      />
      )}
      <div className="shell">
        <div
          className="row"
          style={{
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 18,
          }}
        >
          <div className="row gap-16" style={{ alignItems: "center" }}>
            <RadarAlpaca size={72} />
            <div>
              <h1 className="page-title">
                {t.radar.title}{" "}
                {!isToday && (
                  <span style={{ fontWeight: 500, color: "var(--text-3)" }}>
                    · {displayDay(focusDay, locale)}
                  </span>
                )}
              </h1>
              <p className="page-sub">
                {isToday
                  ? t.radar.todaySubtitle(unfilteredItems.length)
                  : t.radar.daySubtitle(
                      displayDay(focusDay, locale),
                      unfilteredItems.length,
                    )}
              </p>
            </div>
          </div>
        </div>

        {isToday && !exportMode && (
          <>
            <RunProgress
              // Remount on each new run (lastAnalyzeAt changes) so a freshly
              // started analyze re-seeds initialRunning=true and begins polling;
              // a same-run refresh keeps the live poll state intact.
              key={runState.lastAnalyzeAt ?? "idle"}
              initialRunning={runState.analyzeRunning}
              initialDone={lastFeed.analyze.count}
              initialTotal={runState.analyzeTotal}
            />
            <TodayTracker
              day={focusDay}
              analyzeStart={analyzeStart}
              pullStart={pullStart}
            />
          </>
        )}
        {!exportMode && (
          <SmartRecapSection
            // Remount when the recap range changes (e.g. a saved-recap click)
            // so `initialOpen` re-resolves; a filter-only change keeps the same
            // key, preserving the reader's collapse choice.
            key={`${recapKey.since}:${recapKey.until}`}
            initialOpen={recapOpen}
            title={t.radar.recap.title}
            subtitle={t.radar.recap.subtitle}
          >
            <div className="card" style={{ padding: 16, marginBottom: 18 }}>
              <div className="col gap-12">
                <RecapControls
                  presets={recapPresets}
                  minScore={filters.minScore}
                  novelOnly={filters.novelOnly}
                  status={recap?.status ?? null}
                  staleBy={recap?.staleBy ?? 0}
                  hasRecap={recap?.headline != null}
                />
                {recap ? (
                  <RecapPanel recap={recap} t={t} />
                ) : (
                  <span className="muted">{t.radar.recap.none}</span>
                )}
              </div>
            </div>
          </SmartRecapSection>
        )}

        {!exportMode && (
          <FilterBar
            total={unfilteredItems.length}
            shown={items.length}
            isToday={isToday}
            today={today}
          />
        )}

        <div className="col gap-12" style={{ marginBottom: 30 }}>
          {items.length > 0 ? (
            items.map((item) => <SignalCard key={item.id} item={item} />)
          ) : (
            <div className="filter-empty">
              {t.radar.noItemsPrefix}
              {filters.novelOnly ? t.radar.noItemsNovel : ""}
              {filters.lastFeedOnly ? t.radar.noItemsLastFeed : ""}
              {t.radar.noItemsSuffix}
            </div>
          )}
        </div>

        {exportMode && items.length > 0 && (
          <section className="export-appendix">
            <h2 className="sec-title">{t.radar.appendixTitle}</h2>
            {items.map((item) => (
              <article key={item.id} className="appendix-item">
                <h3 className="appendix-h">
                  {item.title}
                  <span className="appendix-score">{item.score}</span>
                </h3>
                <div className="appendix-meta mono">
                  {item.source}
                  {item.publishedAt ? ` · ${item.publishedAt.slice(0, 16).replace("T", " ")}` : ""}
                  {item.sourceUrl ? ` · ${item.sourceUrl}` : ""}
                </div>
                {item.summary && <p className="appendix-summary">{item.summary}</p>}
                {item.impactMd && <MarkdownText>{item.impactMd}</MarkdownText>}
              </article>
            ))}
          </section>
        )}

        {isToday && !exportMode && pastDays.length > 0 && (
          <>
            <div className="sec-head">
              <h2 className="sec-title">{t.radar.pastDays}</h2>
              <span className="sec-sub">{t.radar.pastDaysSub}</span>
            </div>
            <div className="col gap-8" style={{ marginBottom: 24 }}>
              {pastDays.map((day) => (
                <DayGroup key={day.day} day={day} />
              ))}
            </div>
          </>
        )}

        {isToday && !exportMode && savedRecaps.length > 0 && (
          <SavedRecaps recaps={savedRecaps} locale={locale} t={t} />
        )}
      </div>
    </div>
  );
}

/**
 * Shift a `YYYY-MM-DD` day string by `delta` days. Arithmetic stays in UTC
 * date space because `day` is already a resolved local day — re-interpreting
 * it in a zone would slide the result across a DST boundary.
 */
function shiftDay(day: string, delta: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}

/** Accept a `YYYY-MM-DD` search param; ignore anything else. */
function asDay(value: string | string[] | undefined): string | null {
  const raw = Array.isArray(value) ? value[0] : value;
  return typeof raw === "string" && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null;
}
