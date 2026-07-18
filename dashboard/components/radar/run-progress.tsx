"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/components/i18n-provider";

type RunState = { running: boolean; done: number; total: number };

const POLL_MS = 1500;

interface RunProgressProps {
  /** Seeded from radar-state.json by the server so a mid-run reload re-shows
   *  the bar without depending on the click that started the run. */
  initialRunning: boolean;
  initialDone: number;
  initialTotal: number;
}

/**
 * Live analyze-progress bar. While a dashboard-triggered analyze is running it
 * polls `GET /api/radar/run` every ~1.5s and shows `done/total`. The bar's fill
 * is display-only; whether a run is in flight is governed solely by the polled
 * `running` flag (tier1-error items never produce an analysis row, so `done`
 * can finish below `total`). On a running → false transition it does one final
 * `router.refresh()` so the TodayTracker counters + item feed settle; while
 * running it refreshes on a throttled cadence so the tracker moves live.
 */
export function RunProgress({
  initialRunning,
  initialDone,
  initialTotal,
}: RunProgressProps) {
  const { t } = useI18n();
  const router = useRouter();
  const [state, setState] = useState<RunState>({
    running: initialRunning,
    done: initialDone,
    total: initialTotal,
  });
  const tick = useRef(0);

  useEffect(() => {
    if (!state.running) return;
    let active = true;

    const poll = async (): Promise<void> => {
      let next: RunState;
      try {
        const res = await fetch("/api/radar/run", { cache: "no-store" });
        next = (await res.json()) as RunState;
      } catch {
        return; // transient fetch error — try again next tick
      }
      if (!active) return;
      setState(next);

      if (!next.running) {
        // Run finished: settle the server-rendered tracker + feed once.
        router.refresh();
      } else if (++tick.current % 2 === 0) {
        // Throttle live refreshes to ~every other tick (~3s) so the tracker
        // counters advance without re-querying the whole page every 1.5s.
        router.refresh();
      }
    };

    const id = window.setInterval(poll, POLL_MS);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [state.running, router]);

  // No bar when idle, or for a zero-denominator run (would read a stuck 0/0).
  if (!state.running || state.total <= 0) return null;

  const pct = Math.min(100, Math.round((state.done / state.total) * 100));

  return (
    <div className="card" style={{ padding: "10px 14px", marginBottom: 14 }}>
      <div
        className="row"
        style={{
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <span
          className="row gap-6"
          style={{ alignItems: "center", fontSize: 12, color: "var(--text-2)" }}
          title={t.radar.progress.title}
        >
          <Loader2 size={13} className="spin" style={{ color: "var(--accent)" }} />
          {t.radar.progress.analyzing(state.done, state.total)}
        </span>
        <span className="mono" style={{ fontSize: 11, color: "var(--text-4)" }}>
          {pct}%
        </span>
      </div>
      <div
        style={{
          height: 6,
          borderRadius: 999,
          background: "var(--inset-track)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: "var(--accent)",
            transition: "width 0.4s ease",
          }}
        />
      </div>
    </div>
  );
}
