import Link from "next/link";

import { MarkdownText } from "@/components/radar/markdown-text";
import type { getDictionary } from "@/lib/i18n/dictionaries";
import type { Recap } from "@/lib/radar/recap";

type Dict = ReturnType<typeof getDictionary>;

/**
 * Renders a stored recap: headline, then one block per theme with its
 * citations. Server-rendered — the polling lives in RecapControls, which
 * calls `router.refresh()` to bring a finished recap through this path.
 *
 * A recap in `error` still renders whatever content it had: a failed
 * regeneration must not blank a previously good answer.
 */
export function RecapPanel({ recap, t }: { recap: Recap; t: Dict }) {
  const hasContent = recap.headline !== null || recap.themes.length > 0;

  return (
    <div className="col gap-12">
      {recap.status === "error" && recap.error && (
        <div className="filter-empty" style={{ color: "var(--danger, #d9534f)" }}>
          {t.radar.recap.failed(recap.error)}
        </div>
      )}

      {!hasContent && recap.status !== "error" && (
        <span className="muted">{t.radar.recap.none}</span>
      )}

      {recap.headline && (
        <h3
          style={{
            margin: 0,
            fontSize: 17,
            fontWeight: 600,
            letterSpacing: "-0.02em",
            lineHeight: 1.4,
          }}
        >
          {recap.headline}
        </h3>
      )}

      {recap.themes.map((theme, index) => (
        <article key={`${theme.title}-${index}`} className="col gap-6">
          <div className="row gap-8" style={{ alignItems: "baseline" }}>
            <span className="eyebrow">{String(index + 1).padStart(2, "0")}</span>
            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
              {theme.title}
            </h4>
            <span className="mono muted-2" style={{ fontSize: 11 }}>
              {t.radar.recap.cited(theme.item_ids.length)}
            </span>
          </div>
          <MarkdownText>{theme.narrative}</MarkdownText>
          <div className="row gap-6 wrap">
            {theme.item_ids.map((id) => (
              <Citation key={id} id={id} live={recap.liveIds.includes(id)} t={t} />
            ))}
          </div>
        </article>
      ))}

      {recap.itemCount !== null &&
        recap.consideredCount !== null &&
        recap.consideredCount > recap.itemCount && (
          <span className="mono muted-2" style={{ fontSize: 11 }}>
            {t.radar.recap.coverage(recap.itemCount, recap.consideredCount)}
          </span>
        )}
    </div>
  );
}

/**
 * A cited item. `radar_recaps` holds no FK to `radar_items`, so a recap
 * outlives the 30-day sweep of its sources — an id whose row is gone renders
 * as plain text rather than a link into a 404.
 */
function Citation({ id, live, t }: { id: number; live: boolean; t: Dict }) {
  if (!live) {
    return (
      <span
        className="chip mono muted-2"
        title={t.radar.recap.sweptCitation}
        style={{ fontSize: 11 }}
      >
        #{id}
      </span>
    );
  }
  return (
    <Link href={`/radar/${id}`} className="chip mono" style={{ fontSize: 11 }}>
      #{id}
    </Link>
  );
}
