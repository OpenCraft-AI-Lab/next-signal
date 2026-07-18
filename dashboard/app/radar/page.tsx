import { RadarAlpaca } from "@/components/brand/radar-alpaca";
import { DayGroup } from "@/components/radar/day-group";
import { FilterBar } from "@/components/radar/filter-bar";
import { MarkdownText } from "@/components/radar/markdown-text";
import { PullAnalyzeButton } from "@/components/radar/pull-analyze-button";
import { RunProgress } from "@/components/radar/run-progress";
import { SignalCard } from "@/components/radar/signal-card";
import { TodayTracker } from "@/components/radar/today-tracker";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import { loadRadarFilters } from "@/lib/radar/filter-params";
import {
  displayDay,
  getDayGroups,
  getItemsForDay,
  getLastFeedBounds,
  getLastFeedSummary,
  todayInRadarTz,
} from "@/lib/radar/queries";
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
  const exportMode = (await searchParams).export === "1";
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

  const [items, unfilteredItems, pastDays, lastFeed, runState] =
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
            <div className="col gap-8">
              {pastDays.map((day) => (
                <DayGroup key={day.day} day={day} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
