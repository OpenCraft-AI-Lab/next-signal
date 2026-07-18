"use client";

import { useI18n } from "@/components/i18n-provider";
import { scoreColor } from "@/lib/score";

export function ScoreHistogram({ hist }: { hist: number[] }) {
  const { t } = useI18n();
  const max = Math.max(...hist, 1);
  const height = 56;

  return (
    <div className="col" style={{ gap: 8 }}>
      <span className="eyebrow">{t.radar.tracker.histogram}</span>
      <div className="row" style={{ alignItems: "flex-end", gap: 3, height }}>
        {hist.map((value, i) => {
          const midpoint = i === 10 ? 100 : i * 10 + 5;
          const barHeight = value
            ? Math.max((value / max) * (height - 14), 3)
            : 0;
          return (
            <div
              key={i}
              className="col"
              style={{ alignItems: "center", gap: 4, flex: 1 }}
              title={t.radar.tracker.histogramTitle(
                String(i === 10 ? 100 : `${i * 10}-${i * 10 + 9}`),
                value,
              )}
            >
              <div
                style={{
                  width: "100%",
                  height: barHeight,
                  background: scoreColor(midpoint),
                  opacity: value ? 0.85 : 0,
                  borderRadius: 2,
                  transition: "height .3s ease",
                }}
              />
              <span
                className="mono"
                style={{ fontSize: 9, color: "var(--text-4)" }}
              >
                {i === 0 ? 0 : i === 10 ? 100 : i * 10}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
