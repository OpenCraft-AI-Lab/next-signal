"use client";

import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { useI18n } from "@/components/i18n-provider";
import { ContentBadge, DedupBadge, ScoreChip } from "@/components/radar/badges";
import { IngestButton } from "@/components/radar/ingest-button";
import type { RadarItem } from "@/lib/radar/queries";

const MarkdownText = dynamic(
  () =>
    import("@/components/radar/markdown-text").then((mod) => mod.MarkdownText),
  { ssr: false },
);

function shortTime(value: string | null): string {
  return value ? value.slice(11, 16) : "";
}

export function SignalCard({ item }: { item: RadarItem }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";

  return (
    <div
      className="card hoverable"
      style={{ padding: 14, cursor: "pointer" }}
      onClick={() => router.push(`/radar/${item.id}${suffix}`)}
    >
      <div className="row" style={{ gap: 14, alignItems: "flex-start" }}>
        <ScoreChip value={item.score} />
        <div className="col" style={{ flex: 1, minWidth: 0, gap: 8 }}>
          <div
            className="row"
            style={{
              justifyContent: "space-between",
              gap: 12,
              alignItems: "flex-start",
            }}
          >
            <div className="col" style={{ gap: 5, minWidth: 0 }}>
              {item.sourceUrl ? (
                <a
                  className="cardtitle"
                  href={item.sourceUrl}
                  target="_blank"
                  rel="noopener"
                  onClick={(event) => event.stopPropagation()}
                >
                  {item.title}
                </a>
              ) : (
                <span className="cardtitle">{item.title}</span>
              )}
              <div className="row gap-8 wrap" style={{ rowGap: 5 }}>
                <span
                  className="mono"
                  style={{ fontSize: 11, color: "var(--text-3)" }}
                >
                  {item.source}
                </span>
                {item.publishedAt && (
                  <span
                    className="mono"
                    style={{ fontSize: 11, color: "var(--text-4)" }}
                  >
                    · {shortTime(item.publishedAt)}
                  </span>
                )}
                <DedupBadge status={item.dedupStatus} />
                {item.contentStatus !== "full" && (
                  <ContentBadge status={item.contentStatus} />
                )}
              </div>
            </div>
            <div
              className="row gap-6 actions"
              onClick={(event) => event.stopPropagation()}
            >
              {item.sourceUrl && (
                <a
                  className="btn sm ghost"
                  href={item.sourceUrl}
                  target="_blank"
                  rel="noopener"
                >
                  <ExternalLink size={13} />
                  {t.radar.card.readSource}
                </a>
              )}
              <IngestButton itemId={item.id} />
            </div>
          </div>

          <div className="row gap-6 wrap">
            {item.tags.map((tag) => (
              <span key={tag} className="chip tag">
                {tag}
              </span>
            ))}
          </div>

          <div
            className="impact"
            onClick={(event) => {
              event.stopPropagation();
              setOpen((value) => !value);
            }}
          >
            {open && item.impactMd ? (
              <div className="impact-text">
                <MarkdownText>{item.impactMd}</MarkdownText>
              </div>
            ) : (
              <p className="impact-text clamp">{item.summary ?? ""}</p>
            )}
            {item.impactMd && (
              <button className="impact-toggle" type="button">
                {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                {open ? t.radar.card.showLess : t.radar.card.expandImpact}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
