import Link from "next/link";

import { SeenButton } from "@/components/knowledge/seen-button";
import type { getDictionary } from "@/lib/i18n/dictionaries";
import type { ReviewCard as ReviewCardData } from "@/lib/knowledge/review";

type Dict = ReturnType<typeof getDictionary>;

/**
 * One due review. The card body (title, position, capture date, the doc's own
 * summary) is a single link that opens the doc's full text in the preview pane
 * below and scrolls to it (`#doc-preview`); the "seen" control stays a separate
 * button so reading and dismissing don't collide.
 */
export function ReviewCard({ card, t }: { card: ReviewCardData; t: Dict }) {
  const href = `/knowledge?doc=${encodeURIComponent(card.docPath)}#doc-preview`;
  return (
    <div className="card" style={{ padding: 14 }}>
      <div
        className="row"
        style={{ justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}
      >
        <Link
          href={href}
          className="col gap-8"
          style={{ flex: 1, minWidth: 0, color: "inherit", textDecoration: "none" }}
        >
          <span
            style={{
              fontSize: 15,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              lineHeight: 1.35,
            }}
          >
            {card.title}
          </span>

          <span className="row gap-8" style={{ alignItems: "center" }}>
            <span className="chip mono" style={{ fontSize: 11 }}>
              {t.knowledge.review.position(card.stage + 1, card.totalStages)}
            </span>
            <span className="mono muted-2" style={{ fontSize: 11 }}>
              {t.knowledge.review.captured(card.capturedAt)}
            </span>
          </span>

          {card.summary && (
            <span style={{ fontSize: 13, lineHeight: 1.55 }}>{card.summary}</span>
          )}
        </Link>

        <SeenButton docPath={card.docPath} />
      </div>
    </div>
  );
}
