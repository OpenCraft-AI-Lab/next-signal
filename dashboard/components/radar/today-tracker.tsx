import { ScoreHistogram } from "@/components/radar/score-histogram";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import { displayDay, getTrackerForDay } from "@/lib/radar/queries";

function StatPill({
  label,
  value,
  kind,
  sub,
  title,
}: {
  label: string;
  value: number;
  kind?: "green" | "amber" | "red" | "purple";
  sub?: string;
  /** Hover tooltip — used to disambiguate stage semantics for T1/T2. */
  title?: string;
}) {
  return (
    <div className="col" style={{ gap: 3 }} title={title}>
      <span className="eyebrow">{label}</span>
      <span
        className="num"
        style={{
          fontSize: 19,
          fontWeight: 600,
          color: kind ? `var(--${kind})` : "var(--text)",
        }}
      >
        {value}
      </span>
      {sub && (
        <span
          className="mono"
          style={{ fontSize: 10.5, color: "var(--text-4)" }}
        >
          {sub}
        </span>
      )}
    </div>
  );
}

export async function TodayTracker({
  day,
  analyzeStart,
  pullStart,
}: {
  day: string;
  analyzeStart: Date | null;
  pullStart: Date | null;
}) {
  const locale = await getLocale();
  const t = getDictionary(locale);
  const tracker = await getTrackerForDay(day, { analyzeStart, pullStart });
  const lastFeedActive = analyzeStart !== null || pullStart !== null;

  return (
    <div className="card" style={{ padding: "16px 18px", marginBottom: 22 }}>
      <div
        className="row"
        style={{
          justifyContent: "space-between",
          marginBottom: 14,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div className="row gap-8" style={{ alignItems: "center" }}>
          <span className="badge accent" style={{ fontWeight: 600 }}>
            <span className="dot" />
            {t.radar.tracker.today}
          </span>
          <span
            className="mono"
            style={{ fontSize: 12, color: "var(--text-2)" }}
          >
            {displayDay(tracker.date, locale)}
          </span>
          {lastFeedActive && (
            <span
              className="badge purple"
              style={{ fontWeight: 600 }}
              title={t.radar.tracker.lastFeedTitle}
            >
              {t.radar.tracker.lastFeed}
            </span>
          )}
        </div>
        <div className="row gap-6">
          {tracker.pulledBySource.map((source) => (
            <span key={source.source} className="chip">
              <span className="mono" style={{ color: "var(--text-2)" }}>
                {source.source}
              </span>
              <span className="num" style={{ color: "var(--text-4)" }}>
                {source.n}
              </span>
            </span>
          ))}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "auto 1px auto 1px auto 1px auto 1fr",
          gap: 22,
          alignItems: "center",
        }}
      >
        <StatPill
          label={t.radar.tracker.pulled}
          value={tracker.pulledTotal}
          sub={t.radar.tracker.sources(tracker.pulledBySource.length)}
        />
        <div className="vdiv" />
        <div className="row" style={{ gap: 18 }}>
          <StatPill
            label={t.radar.tracker.t1Dropped}
            value={tracker.tier1.dropped}
            kind="red"
            title={t.radar.tracker.t1DroppedTitle}
          />
          <StatPill
            label={t.radar.tracker.t1Kept}
            value={tracker.tier1.kept}
            kind="green"
            title={t.radar.tracker.t1KeptTitle}
          />
        </div>
        <div className="vdiv" />
        <div className="row" style={{ gap: 18 }}>
          <StatPill
            label={t.radar.tracker.t2Full}
            value={tracker.tier2.ok}
            kind="green"
            title={t.radar.tracker.t2FullTitle}
          />
          <StatPill
            label={t.radar.tracker.fallback}
            value={tracker.tier2.fallback}
            kind="amber"
            title={t.radar.tracker.fallbackTitle}
          />
          <StatPill
            label={t.radar.tracker.error}
            value={tracker.tier2.error}
            kind="red"
            title={t.radar.tracker.errorTitle}
          />
        </div>
        <div className="vdiv" />
        <div className="row" style={{ gap: 18 }}>
          <StatPill
            label={t.radar.tracker.novel}
            value={tracker.dedup.novel}
            kind="green"
          />
          <StatPill
            label={t.radar.tracker.duplicateShort}
            value={tracker.dedup.duplicate}
            kind="purple"
          />
        </div>
        <div style={{ justifySelf: "end", minWidth: 232 }}>
          <ScoreHistogram hist={tracker.hist} />
        </div>
      </div>
    </div>
  );
}
