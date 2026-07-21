"use client";

import { Loader2, RefreshCw, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createParser, useQueryStates } from "nuqs";

import { useI18n } from "@/components/i18n-provider";
import { Input } from "@/components/ui/input";
import { Segmented, SegmentedItem } from "@/components/ui/segmented";
import { generateRecap } from "@/lib/actions/recap";
import { parseDayValue } from "@/lib/radar/filter-shared";
import type { RecapStatus } from "@/lib/radar/recap";

const POLL_MS = 2000;
/**
 * Consecutive "no row yet" polls tolerated before concluding the range was
 * empty. An empty range deliberately writes nothing (no row, no LLM call), so
 * without this bound the panel would poll forever on a run that already exited
 * cleanly. 10 ticks ≈ 20s, well past CLI startup plus one SELECT.
 */
const MAX_MISSING_POLLS = 10;

const parseDay = createParser({ parse: parseDayValue, serialize: String });

const recapParsers = {
  recapSince: parseDay,
  recapUntil: parseDay,
};

export type RecapPreset = { since: string; until: string };

interface RecapControlsProps {
  /** Preset ranges resolved server-side, so "last 7 days" means the radar
   *  timezone's last 7 days rather than the browser's. */
  presets: { last7: RecapPreset; last30: RecapPreset };
  /** Quality gate inherited from the filter bar — part of the recap's identity. */
  minScore: number;
  novelOnly: boolean;
  /** Status of the stored recap for the currently selected range, if any. */
  status: RecapStatus | null;
  staleBy: number;
  hasRecap: boolean;
}

export function RecapControls({
  presets,
  minScore,
  novelOnly,
  status,
  staleBy,
  hasRecap,
}: RecapControlsProps) {
  const { t } = useI18n();
  const router = useRouter();
  const [range, setRange] = useQueryStates(recapParsers, { shallow: false });
  // Bridges the gap between the click and the row appearing as 'running'.
  const [pending, setPending] = useState(false);
  // Set when a triggered run finished without ever writing a row — the signature
  // of an empty range.
  const [ranEmpty, setRanEmpty] = useState(false);
  const missingPolls = useRef(0);

  const since = range.recapSince ?? presets.last7.since;
  const until = range.recapUntil ?? presets.last7.until;
  const running = status === "running" || pending;

  const activePreset =
    since === presets.last7.since && until === presets.last7.until
      ? "last7"
      : since === presets.last30.since && until === presets.last30.until
        ? "last30"
        : "custom";

  useEffect(() => {
    if (!running) return;
    let active = true;

    const poll = async (): Promise<void> => {
      const params = new URLSearchParams({
        since,
        until,
        minScore: String(minScore),
        novelOnly: novelOnly ? "1" : "0",
      });
      let next: RecapStatus | null;
      try {
        const res = await fetch(`/api/radar/recap?${params}`, {
          cache: "no-store",
        });
        next = ((await res.json()) as { status: RecapStatus | null }).status;
      } catch {
        return; // transient — retry next tick
      }
      if (!active) return;
      if (next === null) {
        // No row yet. Tolerate startup latency, but give up eventually: an
        // empty range exits without writing anything, and polling forever
        // would leave the button stuck on "Starting...".
        if (++missingPolls.current >= MAX_MISSING_POLLS) {
          missingPolls.current = 0;
          setPending(false);
          setRanEmpty(true);
        }
        return;
      }
      missingPolls.current = 0;
      if (next !== "running") {
        setPending(false);
        router.refresh();
      }
    };

    const id = window.setInterval(poll, POLL_MS);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [running, since, until, minScore, novelOnly, router]);

  const trigger = async (regenerate: boolean): Promise<void> => {
    setRanEmpty(false);
    missingPolls.current = 0;
    setPending(true);
    const result = await generateRecap(
      { since, until, minScore, novelOnly },
      regenerate,
    );
    if (!result.ok) setPending(false);
  };

  return (
    <div className="row gap-8 wrap" style={{ alignItems: "center" }}>
      <Segmented>
        <SegmentedItem
          active={activePreset === "last7"}
          onClick={() =>
            setRange({
              recapSince: presets.last7.since,
              recapUntil: presets.last7.until,
            })
          }
        >
          {t.radar.recap.last7}
        </SegmentedItem>
        <SegmentedItem
          active={activePreset === "last30"}
          onClick={() =>
            setRange({
              recapSince: presets.last30.since,
              recapUntil: presets.last30.until,
            })
          }
        >
          {t.radar.recap.last30}
        </SegmentedItem>
        <SegmentedItem active={activePreset === "custom"} onClick={() => {}}>
          {t.radar.recap.custom}
        </SegmentedItem>
      </Segmented>

      <label className="rangewrap">
        <span className="rlabel">{t.radar.recap.from}</span>
        <Input
          type="date"
          mono
          value={since}
          max={until}
          onChange={(event) => setRange({ recapSince: event.target.value })}
          style={{ width: 132, height: 26, padding: "0 6px", fontSize: 12 }}
        />
      </label>
      <label className="rangewrap">
        <span className="rlabel">{t.radar.recap.to}</span>
        <Input
          type="date"
          mono
          value={until}
          min={since}
          onChange={(event) => setRange({ recapUntil: event.target.value })}
          style={{ width: 132, height: 26, padding: "0 6px", fontSize: 12 }}
        />
      </label>

      <div className="row gap-6" style={{ marginLeft: "auto" }}>
        {ranEmpty && !running && (
          <span className="mono muted-2" style={{ fontSize: 11 }}>
            {t.radar.recap.empty}
          </span>
        )}
        {staleBy > 0 && !running && (
          <span className="mono muted-2" style={{ fontSize: 11 }}>
            {t.radar.recap.stale(staleBy)}
          </span>
        )}
        <button
          type="button"
          className="btn ghost sm"
          disabled={running}
          onClick={() => void trigger(hasRecap)}
        >
          {running ? (
            <>
              <Loader2 size={13} className="spin" />
              {status === "running"
                ? t.radar.recap.generating
                : t.radar.recap.pending}
            </>
          ) : hasRecap ? (
            <>
              <RefreshCw size={13} />
              {t.radar.recap.regenerate}
            </>
          ) : (
            <>
              <Sparkles size={13} />
              {t.radar.recap.generate}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
