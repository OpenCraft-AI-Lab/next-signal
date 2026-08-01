import type { getDictionary } from "@/lib/i18n/dictionaries";
import type { StageBin } from "@/lib/knowledge/review";
import { RETENTION_HELD, retentionColor } from "@/lib/retention";

type Dict = ReturnType<typeof getDictionary>;

/** Matches ScoreHistogram's block so the two pages' charts line up. */
const HEIGHT = 56;

/**
 * Where the enrolled collection sits on the Ebbinghaus curve: one bar per review
 * stage plus a terminal bar, split into the portion already due (solid, at the
 * baseline) and the portion still scheduled (translucent, above it).
 *
 * Geometry is `ScoreHistogram`'s, deliberately — same 56px block, 3px gaps, 2px
 * radius, 9px mono ticks — because this sits in the same kind of trailing slot
 * on the knowledge page that the score histogram sits in on the radar page.
 * Colour comes from the retention ramp rather than the score ramp; see
 * `lib/retention.ts` for why those stay separate.
 *
 * The frame — eyebrow, axis, key — always renders, including with nothing
 * enrolled and nothing due. ScoreHistogram does the same (the radar tracker
 * still reads "Score distribution · 0-100" over a full axis on a day with no
 * items): a chart that vanishes or sheds its labels when it has little to say
 * leaves an unexplained shape behind and moves the layout underneath it.
 *
 * Exact numbers live in each bar's native `title`, which keeps this a server
 * component with no hydration cost.
 */
export function RetentionHistogram({ bins, t }: { bins: StageBin[]; t: Dict }) {
  const enrolled = bins.reduce((sum, bin) => sum + bin.total, 0);
  const max = Math.max(...bins.map((bin) => bin.total), 1);
  // ScoreHistogram reserves 14px of the block for the tick label
  const barSpace = HEIGHT - 14;
  // every bin except the terminal one; the ramp spans those and stops there
  const stageCount = bins.length - 1;
  const key = retentionColor(0.6);

  return (
    <div className="col" style={{ gap: 8 }}>
      <span className="eyebrow">{t.knowledge.review.curve(enrolled)}</span>

      <div className="row" style={{ alignItems: "flex-end", gap: 3, height: HEIGHT }}>
        {bins.map((bin, i) => {
          const held = bin.days === null;
          const label = held ? t.knowledge.review.curveDone : `${bin.days}d`;
          const color = held ? RETENTION_HELD : retentionColor(i / (stageCount - 1));

          const total = bin.total ? Math.max((bin.total / max) * barSpace, 3) : 0;
          const due = bin.due ? Math.max((bin.due / max) * barSpace, 3) : 0;
          // 2px separates the two segments, so it comes out of the upper one.
          const scheduled = Math.max(total - due - (due ? 2 : 0), 0);

          return (
            <div
              key={label}
              className="col"
              style={{ alignItems: "center", gap: 4, flex: 1 }}
              title={
                held
                  ? t.knowledge.review.curveDoneTitle(bin.total)
                  : t.knowledge.review.curveTitle(label, bin.total, bin.due)
              }
            >
              <div
                style={{
                  width: "100%",
                  height: total,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "flex-end",
                  gap: 2,
                }}
              >
                {scheduled > 0 && (
                  <div
                    style={{
                      height: scheduled,
                      background: color,
                      opacity: held ? 0.6 : 0.32,
                      borderRadius: 2,
                    }}
                  />
                )}
                {due > 0 && (
                  <div style={{ height: due, background: color, borderRadius: 2 }} />
                )}
              </div>
              <span className="mono" style={{ fontSize: 9, color: "var(--text-4)" }}>
                {label}
              </span>
            </div>
          );
        })}
      </div>

      {/* The split is opacity-only, which nothing else on the page explains —
          ScoreHistogram needs no key because its bars are a single solid fill. */}
      <div className="row" style={{ gap: 12, marginTop: -2 }}>
        {[
          { label: t.knowledge.review.curveDueKey, opacity: 1 },
          { label: t.knowledge.review.curveScheduledKey, opacity: 0.32 },
        ].map((item) => (
          <span
            key={item.label}
            className="row"
            style={{ gap: 5, fontSize: 10, color: "var(--text-4)" }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 2,
                background: key,
                opacity: item.opacity,
              }}
            />
            <span className="mono">{item.label}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
