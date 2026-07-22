import { RefreshReviewsButton } from "@/components/knowledge/refresh-reviews-button";
import { ReviewCard } from "@/components/knowledge/review-card";
import type { getDictionary } from "@/lib/i18n/dictionaries";
import type { ReviewCard as ReviewCardData } from "@/lib/knowledge/review";

type Dict = ReturnType<typeof getDictionary>;

/**
 * The review section above the ingest form. When nothing is due it collapses to
 * a single line rather than parking an empty panel at the top of the page; when
 * docs are due it shows up to REVIEW_DISPLAY_CAP cards and states the remainder.
 */
export function ReviewSection({
  reviews,
  t,
}: {
  reviews: { cards: ReviewCardData[]; total: number };
  t: Dict;
}) {
  const { cards, total } = reviews;
  const remainder = total - cards.length;

  if (total === 0) {
    return (
      <div
        className="row"
        style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}
      >
        <span className="muted" style={{ fontSize: 12 }}>
          {t.knowledge.review.nothingDue}
        </span>
        <RefreshReviewsButton />
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
