"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { NavTriggerPortal } from "@/components/nav-trigger-slot";
import { Button } from "@/components/ui/button";
import { runPullAndAnalyze } from "@/lib/actions/radar";

type Phase = null | "pulling";
type LastEntry = { ago: string; count: number };

interface PullAnalyzeButtonProps {
  /**
   * Pre-rendered "last pull" chip data. Server component computes from
   * the latest `fetched_at` cluster (5-min gap heuristic). null when the
   * `radar_items` table is empty.
   */
  lastPull?: LastEntry | null;
  /**
   * Pre-rendered "last analyze" chip data. Server component computes
   * from the latest `analyzed_at` cluster (5-min gap heuristic). null
   * when the `radar_analyses` table is empty.
   */
  lastAnalyze?: LastEntry | null;
  /**
   * Count of radar_items still awaiting analysis (seen_at IS NULL). When
   * > 0, an amber "pending N" tag is shown next to the analyzed chip to
   * flag that the last pull produced items the analyzer hasn't touched yet.
   */
  unanalyzed?: number;
}

function Chip({
  label,
  entry,
  color,
  title,
  countPrefix = "",
}: {
  label: string;
  entry: LastEntry;
  color: string;
  title?: string;
  /** Prefix in front of the count, e.g. "+" so 0 reads "+0" not just "0". */
  countPrefix?: string;
}) {
  return (
    <span
      className="mono"
      style={{ fontSize: 11, color, whiteSpace: "nowrap" }}
      title={title}
    >
      {label}{" "}
      <strong style={{ fontWeight: 600 }}>
        {countPrefix}
        {entry.count}
      </strong>{" "}
      · {entry.ago}
    </span>
  );
}

export function PullAnalyzeButton({
  lastPull,
  lastAnalyze,
  unanalyzed = 0,
}: PullAnalyzeButtonProps) {
  const { locale, t } = useI18n();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>(null);

  async function onClick() {
    setPhase("pulling");
    const result = await runPullAndAnalyze(locale);
    setPhase(null);
    if (result.ok) {
      toast.success(result.message);
      // Re-render the server page so it re-reads radar-state.json (now with the
      // fresh analyze start) and hands <RunProgress /> a running run to poll —
      // the analyze phase is owned by that bar, not a client timer here.
      router.refresh();
    } else {
      toast.error(result.message);
    }
  }

  const loading = phase !== null;
  const label =
    phase === "pulling" ? t.radar.pullAnalyze.pulling : t.radar.pullAnalyze.idle;

  return (
    <NavTriggerPortal>
      <div className="row" style={{ alignItems: "center", gap: 10 }}>
        {lastPull && (
          <Chip
            label={t.radar.pullAnalyze.pulled}
            entry={lastPull}
            color="var(--text-4)"
            title={t.radar.pullAnalyze.lastPullTitle}
            countPrefix="+"
          />
        )}
        {lastAnalyze && (
          <Chip
            label={t.radar.pullAnalyze.analyzed}
            entry={lastAnalyze}
            color="var(--text-4)"
            title={t.radar.pullAnalyze.analyzedTitle}
          />
        )}
        {unanalyzed > 0 && (
          <span
            className="mono"
            style={{ fontSize: 11, color: "var(--amber)", whiteSpace: "nowrap" }}
            title={t.radar.pullAnalyze.drainedTitle}
          >
            {t.radar.pullAnalyze.pending}{" "}
            <strong style={{ fontWeight: 600 }}>{unanalyzed}</strong>
          </span>
        )}
        <Button variant="primary" onClick={onClick} disabled={loading}>
          {loading ? (
            <Loader2 className="spin" size={14} />
          ) : (
            <Sparkles size={14} />
          )}
          {label}
        </Button>
      </div>
    </NavTriggerPortal>
  );
}
