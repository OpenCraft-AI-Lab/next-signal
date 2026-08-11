"use client";

import { Plus, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Input } from "@/components/ui/input";
import { Segmented, SegmentedItem } from "@/components/ui/segmented";
import {
  setSchedule,
  type Schedule,
  type ScheduleStatus,
} from "@/lib/actions/schedule";
import { timeAgo } from "@/lib/relative-time";

/** Shown in the time field the first time a schedule is switched on. */
const DEFAULT_TIME = "08:00";

/** The next time any listed slot comes round, in the zone runs actually fire in. */
function nextRun(
  at: string[],
  tz: string,
  now: Date,
): { at: string; today: boolean } | null {
  const list = at.filter(Boolean).slice().sort();
  if (!list.length) return null;
  let nowMinutes: number;
  try {
    const [hh, mm] = new Intl.DateTimeFormat("en-GB", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .format(now)
      .split(":");
    nowMinutes = Number(hh) * 60 + Number(mm);
  } catch {
    return null;
  }
  const upcoming = list.find((time) => {
    const [hh, mm] = time.split(":");
    return Number(hh) * 60 + Number(mm) > nowMinutes;
  });
  return upcoming ? { at: upcoming, today: true } : { at: list[0], today: false };
}

/**
 * The unattended run schedule (`~/.next-signal/schedule.json`), which the
 * `scheduler` container re-reads on every 30s poll.
 */
export function ScheduleSection({
  initial,
  status,
  runtimeTimezone,
}: {
  initial: Schedule;
  status: ScheduleStatus;
  runtimeTimezone: string;
}) {
  const { t, locale } = useI18n();
  // `saved` mirrors what is actually on disk; `value` is what the controls
  // show. They differ only while a typed field is mid-edit — which is the whole
  // point: a draft is not yet a setting.
  const [saved, setSaved] = useState<Schedule>(initial);
  const [value, setValue] = useState<Schedule>(initial);
  // Both time-derived lines below read the clock, and the server renders this
  // page too — the server's "now" and the browser's would differ and trip a
  // hydration mismatch. Stay blank until mounted, then fill in on the client.
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);

  const canonical = (s: Schedule): Schedule => ({
    ...s,
    at: [...new Set(s.at.filter(Boolean))].sort(),
  });

  const same = (a: Schedule, b: Schedule) =>
    a.enabled === b.enabled &&
    a.catchUp === b.catchUp &&
    a.at.join() === b.at.join();

  /** Persist a committed value. No-ops when nothing actually changed. */
  const commit = async (next: Schedule) => {
    const target = canonical(next);
    setValue(next); // optimistic, drafts and all
    if (same(target, saved)) return;
    try {
      await setSchedule(target);
      setSaved(target);
      toast.success(t.settings.scheduleSaved);
    } catch (err) {
      console.error("failed to update schedule", err);
      setValue(saved); // roll back to the last value known to be on disk
      toast.error(t.settings.saveFailed);
    }
  };

  const setTimeAt = (index: number, at: string) =>
    setValue({ ...value, at: value.at.map((v, i) => (i === index ? at : v)) });

  const addTime = () => {
    // A duplicate is deduped away on write and reads as "nothing happened", so
    // land the new row on the first free hour instead. Searching a fixed list
    // rather than counting upwards: with all 24 taken there is no row to add,
    // and a scan that can end is the only kind worth writing.
    const taken = new Set(value.at);
    const free = Array.from(
      { length: 24 },
      (_, i) => `${String((9 + i) % 24).padStart(2, "0")}:00`,
    ).find((at) => !taken.has(at));
    if (!free) return;
    void commit({ ...value, at: [...value.at, free] });
  };

  // An enabled schedule with no times has nothing to fire; "Off" is how you
  // stop it, so the last remaining time cannot be removed.
  const committedCount = canonical(value).at.length;
  const upcoming = useMemo(
    () => (now ? nextRun(value.at, runtimeTimezone, now) : null),
    [value.at, runtimeTimezone, now],
  );

  const lastRun = () => {
    if (!status.lastRunAt) return t.settings.scheduleNeverRun;
    if (!now) return ""; // relative time is client-only, see `now` above
    // `lastRunAt` is the start instant during a run, so one relative time
    // serves both "how long ago" and "how long so far".
    const ago = timeAgo(status.lastRunAt, now, locale);
    if (status.lastStatus === "running") return t.settings.scheduleRunning(ago);
    // Anything unrecognized lands in the failure branch: it did not finish, so
    // reading it as a completed run would be the one wrong answer.
    return status.lastStatus === "ok"
      ? t.settings.scheduleLastOk(ago)
      : t.settings.scheduleLastFailed(ago);
  };

  /** Colour follows the same branch as the text. A run still going is neither
      green nor red, and grey would say "nothing is happening" — amber does. */
  const tone = !status.lastRunAt
    ? "idle"
    : status.lastStatus === "running"
      ? "warn"
      : status.lastStatus === "ok"
        ? "ok"
        : "down";

  return (
    <section className="card pad set-card" id="schedule">
      <div className="set-row">
        <div className="set-rowtext">
          <span className="set-label">{t.settings.schedule}</span>
          <span className="set-hint">{t.settings.scheduleHint}</span>
        </div>
        <div className="set-rowctl">
          {/* A segmented click IS the commit: one interaction expresses one
              complete, valid intent, so there is nothing to defer to a button. */}
          <Segmented>
            <SegmentedItem
              active={!value.enabled}
              onClick={() => void commit({ ...value, enabled: false })}
            >
              {t.settings.scheduleOff}
            </SegmentedItem>
            <SegmentedItem
              active={value.enabled}
              onClick={() =>
                void commit({
                  ...value,
                  enabled: true,
                  at: canonical(value).at.length ? value.at : [DEFAULT_TIME],
                })
              }
            >
              {t.settings.scheduleOn}
            </SegmentedItem>
          </Segmented>
        </div>
      </div>

      {/* Times, zone and catch-up are all meaningless while the schedule is off. */}
      {value.enabled && (
        <>
          <div className="set-sub set-row">
            <div className="set-rowtext">
              <span className="set-label">{t.settings.scheduleTime}</span>
              {upcoming && (
                <span className="set-hint">
                  {upcoming.today
                    ? t.settings.scheduleNext(upcoming.at, runtimeTimezone)
                    : t.settings.scheduleNextTomorrow(upcoming.at, runtimeTimezone)}
                </span>
              )}
            </div>
            <div className="set-rowctl">
              <div className="set-times">
                {value.at.map((at, i) => (
                  <span key={i} className="set-timechip">
                    <Input
                      type="time"
                      value={at}
                      onChange={(e) => setTimeAt(i, e.target.value)}
                      // Typing is not committing: a native time input emits a
                      // *complete* value per segment edit — turning 13:55 into
                      // 09:30 emits 09:55 on the way — so persisting every
                      // change would publish half-typed times.
                      onBlur={() => void commit(value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          e.currentTarget.blur(); // blur is what commits
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="set-timex"
                      aria-label={t.settings.scheduleRemoveTime}
                      title={t.settings.scheduleRemoveTime}
                      disabled={committedCount < 2 && Boolean(at)}
                      // Without this the input's blur fires first, re-rendering
                      // the row and replacing this button before its click
                      // lands — the row would silently refuse to be removed.
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() =>
                        void commit({
                          ...value,
                          at: value.at.filter((_, index) => index !== i),
                        })
                      }
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
                <button
                  type="button"
                  className="set-timeadd"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={addTime}
                >
                  <Plus size={12} />
                  {t.settings.scheduleAdd}
                </button>
              </div>
            </div>
          </div>

          {/* Stated, not chosen. A schedule with a zone of its own would fire at
              08:00 in one zone while the radar filed the results under a day
              boundary drawn in another, so the zone is one environment-wide
              setting (`INFO_RADAR_TIMEZONE`) rather than a per-schedule one. */}
          <div className="set-sub set-row">
            <div className="set-rowtext">
              <span className="set-label">{t.settings.scheduleTimezone}</span>
              <span className="set-hint">{t.settings.scheduleTimezoneHint}</span>
            </div>
            <div className="set-rowctl">
              <span className="mono set-static">{runtimeTimezone}</span>
            </div>
          </div>

          <div className="set-sub set-row">
            <div className="set-rowtext">
              <span className="set-label">{t.settings.scheduleOnMissed}</span>
              <span className="set-hint">{t.settings.scheduleOnMissedHint}</span>
            </div>
            <div className="set-rowctl">
              <Segmented>
                <SegmentedItem
                  active={!value.catchUp}
                  onClick={() => void commit({ ...value, catchUp: false })}
                >
                  {t.settings.scheduleSkip}
                </SegmentedItem>
                <SegmentedItem
                  active={value.catchUp}
                  onClick={() => void commit({ ...value, catchUp: true })}
                >
                  {t.settings.scheduleCatchUp}
                </SegmentedItem>
              </Segmented>
            </div>
          </div>
        </>
      )}

      <div className="set-foot" title={status.lastError ?? undefined}>
        <span className={`set-status ${tone}`}>
          <span className="dot" />
        </span>
        <span>{lastRun()}</span>
      </div>
    </section>
  );
}
