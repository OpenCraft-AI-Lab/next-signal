"use client";

import Link from "next/link";

import { useI18n } from "@/components/i18n-provider";
import { HighlightedSnippet } from "@/components/knowledge/highlighted-snippet";
import type { GbrainHit } from "@/lib/actions/knowledge";
import { cn } from "@/lib/utils";

interface SearchResultsProps {
  hits: GbrainHit[];
  q: string;
  selectedSlug?: string;
}

/**
 * Render gbrain hits as the design's `.rescard` list. Snippets carry HTML
 * `<em>` highlight markup from gbrain plus arbitrary text lifted from
 * wiki markdown — wiki content is NOT a trusted HTML source. We route
 * snippets through `<HighlightedSnippet>` which keeps only `<em>` pairs
 * as real DOM and escapes everything else.
 */
export function SearchResults({ hits, q, selectedSlug }: SearchResultsProps) {
  const { t } = useI18n();
  if (!q) return null;
  if (hits.length === 0) {
    return (
      <span className="muted" style={{ fontSize: 13 }}>
        {t.knowledge.noMatches(q)}
      </span>
    );
  }
  return (
    <div className="col gap-8">
      <span className="eyebrow">{t.knowledge.resultsFor(hits.length, q)}</span>
      {hits.map((hit) => (
        <Link
          key={hit.slug}
          href={`/knowledge?${new URLSearchParams({ q, doc: hit.slug }).toString()}`}
          className={cn("rescard", selectedSlug === hit.slug && "on")}
        >
          <div
            className="row"
            style={{ justifyContent: "space-between", gap: 8 }}
          >
            <span
              style={{ fontWeight: 600, letterSpacing: "-0.01em" }}
              className="elip"
            >
              {hit.slug}
            </span>
            <span className="badge accent">{hit.score.toFixed(2)}</span>
          </div>
          <HighlightedSnippet className="ressnip" html={hit.snippet} />
        </Link>
      ))}
    </div>
  );
}
