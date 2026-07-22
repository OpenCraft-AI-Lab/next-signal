import { ChevronDown, ChevronRight } from "lucide-react";
import Link from "next/link";

import { ScoreChip } from "@/components/radar/badges";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import { displayDay, type DayGroup as DayGroupData } from "@/lib/radar/queries";

export async function DayGroup({ day }: { day: DayGroupData }) {
  const locale = await getLocale();
  const t = getDictionary(locale);
  const topItems = day.topItems;
  const remaining = Math.max(day.keptCount - topItems.length, 0);

  return (
    <Collapsible className="card group" style={{ overflow: "hidden" }}>
      <CollapsibleTrigger className="pastrow">
        <ChevronRight
          size={14}
          className="muted-2 group-data-[state=open]:hidden"
        />
        <ChevronDown
          size={14}
          className="muted-2 hidden group-data-[state=open]:block"
        />
        <span
          style={{
            fontWeight: 600,
            letterSpacing: "-0.02em",
            minWidth: 120,
            textAlign: "left",
          }}
        >
          {displayDay(day.day, locale)} ·{" "}
          <span
            className="mono"
            style={{ fontSize: 12, fontWeight: 400, color: "var(--text-3)" }}
          >
            {day.day}
          </span>
        </span>
        <span className="badge green" style={{ marginRight: 4 }}>
          {t.radar.dayGroup.kept(day.keptCount)}
        </span>
        <span className="chip">
          <span style={{ color: "var(--text-4)" }}>
            {t.radar.dayGroup.median}
          </span>{" "}
          <span className="num" style={{ color: "var(--text-2)" }}>
            {day.medianScore ?? "-"}
          </span>
        </span>
        <span
          className="elip muted"
          style={{ flex: 1, textAlign: "left", fontSize: 12.5 }}
        >
          {day.topTitle ?? t.radar.dayGroup.noHeadline}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div
          style={{
            padding: "0 14px 14px",
            borderTop: "1px solid var(--line)",
            paddingTop: 12,
          }}
        >
          <span className="mono muted-2" style={{ fontSize: 11 }}>
            {t.radar.dayGroup.showing(topItems.length, day.keptCount)}
          </span>
          <div className="col gap-8" style={{ marginTop: 10 }}>
            {topItems.map((item, i) => (
              <Link
                href={`/radar/${item.id}`}
                key={item.id}
                className="row gap-12"
                style={{
                  padding: "8px 0",
                  borderBottom:
                    i < topItems.length - 1
                      ? "1px solid var(--border-2)"
                      : "none",
                }}
              >
                <ScoreChip value={item.score} size="sm" />
                <span style={{ fontSize: 13.5, flex: 1 }} className="elip">
                  {item.displayTitle ?? item.title}
                </span>
                {item.tags[0] && (
                  <span className="mono muted-2" style={{ fontSize: 11 }}>
                    #{item.tags[0]}
                  </span>
                )}
              </Link>
            ))}
            {remaining > 0 && (
              <Link
                className="btn ghost sm"
                style={{ alignSelf: "flex-start", marginTop: 4 }}
                href={`/radar?day=${day.day}`}
              >
                {t.radar.dayGroup.showAll(day.keptCount)}
              </Link>
            )}
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
