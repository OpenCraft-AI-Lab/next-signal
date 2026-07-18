import { ChevronRight, ExternalLink } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ContentBadge, DedupBadge, ScoreChip } from "@/components/radar/badges";
import { DetailPager } from "@/components/radar/detail-pager";
import { IngestButton } from "@/components/radar/ingest-button";
import { MarkdownText } from "@/components/radar/markdown-text";
import { PullAnalyzeButton } from "@/components/radar/pull-analyze-button";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import {
  loadRadarFilters,
  serializeRadarFilters,
} from "@/lib/radar/filter-params";
import { getItemDetail, getLastFeedSummary } from "@/lib/radar/queries";
import { timeAgo } from "@/lib/relative-time";

export default async function RadarDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ id }, filters, locale] = await Promise.all([
    params,
    loadRadarFilters(searchParams),
    getLocale(),
  ]);
  const t = getDictionary(locale);
  const itemId = Number(id);
  if (!Number.isInteger(itemId)) notFound();
  const [item, lastFeed] = await Promise.all([
    getItemDetail(itemId),
    getLastFeedSummary(),
  ]);
  if (!item) notFound();

  const analyzed = item.analysisId !== null;
  const radarHref = `/radar${serializeRadarFilters(filters)}`;

  return (
    <div className="page page-enter">
      <PullAnalyzeButton
        lastPull={
          lastFeed.pull.latestAt
            ? {
                ago: timeAgo(lastFeed.pull.latestAt, new Date(), locale),
                count: lastFeed.pull.count,
              }
            : null
        }
        lastAnalyze={
          lastFeed.analyze.latestAt
            ? {
                ago: timeAgo(lastFeed.analyze.latestAt, new Date(), locale),
                count: lastFeed.analyze.count,
              }
            : null
        }
        unanalyzed={lastFeed.unanalyzed}
      />
      <div className="shell" style={{ maxWidth: 880 }}>
        <div
          className="row"
          style={{
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <Link className="btn ghost sm" href={radarHref}>
            <ChevronRight size={13} style={{ transform: "rotate(180deg)" }} />
            {t.radar.detail.back}
          </Link>
          <DetailPager itemId={item.id} filters={filters} position="top" />
        </div>

        <div className="card" style={{ overflow: "hidden" }}>
          <div style={{ padding: "20px 22px" }}>
            <div
              className="row"
              style={{
                gap: 16,
                alignItems: "flex-start",
                justifyContent: "space-between",
              }}
            >
              <div
                className="row"
                style={{ gap: 16, alignItems: "flex-start", minWidth: 0 }}
              >
                <ScoreChip value={item.score} size="lg" denom />
                <div className="col" style={{ gap: 9, minWidth: 0 }}>
                  {item.sourceUrl ? (
                    <a
                      className="detailtitle"
                      href={item.sourceUrl}
                      target="_blank"
                      rel="noopener"
                    >
                      {item.title}{" "}
                      <ExternalLink size={15} className="muted-2" />
                    </a>
                  ) : (
                    <h1 className="detailtitle">{item.title}</h1>
                  )}
                  <div className="row gap-8 wrap" style={{ rowGap: 6 }}>
                    <span
                      className="mono"
                      style={{ fontSize: 12, color: "var(--text-2)" }}
                    >
                      {item.source}
                    </span>
                    {item.publishedAt && (
                      <span
                        className="mono"
                        style={{ fontSize: 12, color: "var(--text-4)" }}
                      >
                        · {item.publishedAt}
                      </span>
                    )}
                    {item.tags.map((tag) => (
                      <span key={tag} className="chip tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <IngestButton itemId={item.id} primary />
            </div>
          </div>
          <hr className="hr" />

          <div style={{ padding: "20px 22px" }}>
            {!analyzed && (
              <div className="filter-empty" style={{ marginBottom: 22 }}>
                {t.radar.detail.unanalyzed}
              </div>
            )}

            {item.summary && (
              <>
                <span className="eyebrow">{t.radar.detail.summary}</span>
                <p
                  style={{
                    fontSize: 15.5,
                    lineHeight: 1.6,
                    margin: "8px 0 22px",
                    color: "var(--text)",
                  }}
                >
                  {item.summary}
                </p>
              </>
            )}

            {item.impactMd && (
              <>
                <span className="eyebrow">{t.radar.detail.impact}</span>
                <div style={{ margin: "8px 0 22px" }}>
                  <MarkdownText>{item.impactMd}</MarkdownText>
                </div>
              </>
            )}

            <div className="metagrid">
              <div className="metarow">
                <span className="metalabel">{t.radar.detail.tier1Reason}</span>
                <span className="metaval">
                  {item.tier1Reason ?? t.radar.detail.notAnalyzed}
                </span>
              </div>
              <div className="metarow">
                <span className="metalabel">
                  {t.radar.detail.contentStatus}
                </span>
                <span className="metaval">
                  <ContentBadge status={item.contentStatus} />
                </span>
              </div>
              <div className="metarow">
                <span className="metalabel">{t.radar.detail.dedup}</span>
                <span className="metaval row gap-8">
                  <DedupBadge status={item.dedupStatus} />
                  {item.dedupStatus === "duplicate" &&
                    item.duplicateTopicSummary && (
                      <span className="mono muted" style={{ fontSize: 12 }}>
                        {t.radar.detail.duplicateOf(item.duplicateTopicSummary)}
                      </span>
                    )}
                </span>
              </div>
            </div>
          </div>
          <hr className="hr" />

          <div style={{ padding: "18px 22px 22px" }}>
            <div
              className="row"
              style={{ justifyContent: "space-between", marginBottom: 12 }}
            >
              <span className="eyebrow">{t.radar.detail.source}</span>
              {item.sourceUrl && (
                <a
                  className="btn sm ghost"
                  href={item.sourceUrl}
                  target="_blank"
                  rel="noopener"
                >
                  <ExternalLink size={13} />
                  {t.radar.detail.openOriginal}
                </a>
              )}
            </div>
            <div className="excerpt">
              <p>{item.excerpt ?? t.radar.detail.noExcerpt}</p>
            </div>
          </div>
        </div>

        <DetailPager itemId={item.id} filters={filters} position="bottom" />
      </div>
    </div>
  );
}
