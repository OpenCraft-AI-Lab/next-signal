import { RefreshReviewsButton } from "@/components/knowledge/refresh-reviews-button";
import { RetentionHistogram } from "@/components/knowledge/retention-histogram";
import { ReviewCard } from "@/components/knowledge/review-card";
import type { getDictionary } from "@/lib/i18n/dictionaries";
import type { ReviewCard as ReviewCardData, StageBin } from "@/lib/knowledge/review";

type Dict = ReturnType<typeof getDictionary>;

/** Same trailing slot the radar tracker gives its score histogram. */
const CHART_WIDTH = 232;

/** One summary figure. Mirrors `StatPill` on the radar tracker. */
function ReviewStat({
  label,
  value,
  accent,
  muted,
  title,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
  muted?: boolean;
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
          color: accent ? "var(--accent-text)" : muted ? "var(--text-3)" : "var(--text)",
        }}
      >
        {value}
      </span>
    </div>
  );
}

/**
 * The stage the middle doc is waiting on — the one figure that answers "where is
 * my collection on the curve" without reading the bars. Docs past the final
 * stage sort after every stage, so a mostly-retired collection reads as done.
 */
function medianStage(bins: StageBin[], enrolled: number, doneLabel: string): string {
  if (enrolled === 0) return "—";
  const middle = (enrolled + 1) / 2;
  let seen = 0;
  for (const bin of bins) {
    seen += bin.total;
    if (seen >= middle) return bin.days === null ? doneLabel : `${bin.days}d`;
  }
  return doneLabel;
}

/**
 * Summary figures on the left, chart flush right — the layout `TodayTracker`
 * uses, down to the `vdiv` separators and the trailing fixed-width slot.
 */
function ReviewStrip({ bins, t }: { bins: StageBin[]; t: Dict }) {
  const enrolled = bins.reduce((sum, bin) => sum + bin.total, 0);
  const due = bins.reduce((sum, bin) => sum + bin.due, 0);
  const done = bins[bins.length - 1]?.total ?? 0;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1px auto 1px auto 1fr",
        gap: 22,
        alignItems: "center",
      }}
    >
      <ReviewStat label={t.knowledge.review.curveEnrolled} value={enrolled} />
      <div className="vdiv" />
      <div className="row" style={{ gap: 18 }}>
        <ReviewStat label={t.knowledge.review.curveDueKey} value={due} accent />
        <ReviewStat
          label={t.knowledge.review.curveScheduledKey}
          value={enrolled - due - done}
        />
      </div>
      <div className="vdiv" />
      <div className="row" style={{ gap: 18 }}>
        <ReviewStat
          label={t.knowledge.review.curveMedian}
          value={medianStage(bins, enrolled, t.knowledge.review.curveDone)}
          title={t.knowledge.review.curveMedianTitle}
        />
        <ReviewStat
          label={t.knowledge.review.curveDone}
          value={done}
          muted
          title={t.knowledge.review.curveDoneStatTitle}
        />
      </div>
      <div style={{ justifySelf: "end", minWidth: CHART_WIDTH }}>
        <RetentionHistogram bins={bins} t={t} />
      </div>
    </div>
  );
}

/**
 * The review section above the ingest form. When docs are due it shows up to
 * REVIEW_DISPLAY_CAP cards and states the remainder; when nothing is due it
 * drops the cards and says so, keeping the same panel, header shape, and strip.
 *
 * Both states are one card with one header — the section carries a summary and a
 * chart either way, so an unframed variant would read as a different component
 * rather than the same one with less to say. What collapses is the card list,
 * not the frame.
 *
 * The histogram is seated the way `TodayTracker` seats `ScoreHistogram`: flush
 * with the trailing edge of a strip below the header, never in the header row.
 */
export function ReviewSection({
  reviews,
  bins,
  t,
}: {
  reviews: { cards: ReviewCardData[]; total: number };
  bins: StageBin[];
  t: Dict;
}) {
  const { cards, total } = reviews;
  const remainder = total - cards.length;

  if (total === 0) {
    return (
      <div className="card" style={{ padding: 16, marginBottom: 18 }}>
        <div className="col gap-12">
          <div
            className="row"
            style={{ justifyContent: "space-between", alignItems: "flex-end" }}
          >
            <div className="col" style={{ gap: 4 }}>
              <span className="eyebrow">{t.knowledge.review.title}</span>
              <span className="muted" style={{ fontSize: 12 }}>
                {t.knowledge.review.nothingDue}
              </span>
            </div>
            <RefreshReviewsButton />
          </div>
          <ReviewStrip bins={bins} t={t} />
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: 16, marginBottom: 18 }}>
      <div className="col gap-12">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end" }}>
          <div className="col" style={{ gap: 4 }}>
            <div className="row gap-8" style={{ alignItems: "baseline" }}>
              <span className="eyebrow">{t.knowledge.review.title}</span>
              <span className="chip" style={{ fontSize: 11 }}>
                {t.knowledge.review.due(total)}
              </span>
            </div>
            <span className="muted" style={{ fontSize: 12 }}>
              {t.knowledge.review.subtitle}
            </span>
          </div>
          <RefreshReviewsButton />
        </div>

        <ReviewStrip bins={bins} t={t} />

        <div className="col gap-12">
          {cards.map((card) => (
            <ReviewCard key={card.docPath} card={card} t={t} />
          ))}
        </div>

        {remainder > 0 && (
          <span className="mono muted-2" style={{ fontSize: 11 }}>
            {t.knowledge.review.more(remainder)}
          </span>
        )}
      </div>
    </div>
  );
}
