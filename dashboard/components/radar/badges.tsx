"use client";

import { useI18n } from "@/components/i18n-provider";
import { scoreColor, scoreTint } from "@/lib/score";

export function ScoreChip({
  value,
  size = "md",
  denom = false,
}: {
  value: number;
  size?: "sm" | "md" | "lg";
  denom?: boolean;
}) {
  const dim = size === "lg" ? 58 : size === "sm" ? 38 : 48;
  const big = value >= 100;
  const fs = (size === "lg" ? 26 : size === "sm" ? 16 : 22) - (big ? 4 : 0);
  const color = scoreColor(value);
  return (
    <div
      className="score"
      style={{
        width: dim,
        height: dim,
        minWidth: dim,
        background: scoreTint(value),
        color,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 26%, transparent)`,
      }}
    >
      <span className="n" style={{ fontSize: fs }}>
        {Math.round(value)}
      </span>
      {denom && <span className="d">/ 100</span>}
    </div>
  );
}

export function DedupBadge({ status }: { status: string | null }) {
  const { t } = useI18n();
  // NULL means dedup gate didn't run (early data / drop verdicts). Show
  // a neutral "—" rather than misleadingly claiming "novel".
  if (status == null) {
    return (
      <span className="badge" title={t.radar.badges.dedupMissingTitle}>
        —
      </span>
    );
  }
  const duplicate = status === "duplicate";
  return (
    <span className={`badge ${duplicate ? "purple" : "green"}`}>
      <span className="dot" />
      {duplicate ? t.radar.badges.duplicate : t.radar.badges.novel}
    </span>
  );
}

export function ContentBadge({ status }: { status: string | null }) {
  const { t } = useI18n();
  // NULL means tier-2 fetch never ran (drop verdicts) — distinct from
  // "full" (successful fetch). The tracker counts T2 ok on
  // `content_status='full'` strictly; the badge must reflect the same
  // semantics, not silently coerce NULL → "full".
  if (status == null) {
    return (
      <span className="badge" title={t.radar.badges.contentMissingTitle}>
        —
      </span>
    );
  }
  const kind =
    status === "fallback" ? "amber" : status === "error" ? "red" : "";
  const label =
    status === "fallback"
      ? t.radar.badges.fallback
      : status === "error"
        ? t.radar.badges.error
        : status === "full"
          ? t.radar.badges.full
          : status;
  return (
    <span className={`badge ${kind}`}>
      {status !== "full" && <span className="dot" />}
      {label}
    </span>
  );
}
