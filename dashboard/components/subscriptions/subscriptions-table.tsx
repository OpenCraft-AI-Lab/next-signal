"use client";

import { Rss, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { timeAgo } from "@/lib/relative-time";
import type { SubscriptionRow } from "@/lib/subscriptions";

export function SubscriptionsTable({ rows }: { rows: SubscriptionRow[] }) {
  const { locale, t } = useI18n();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const categories = useMemo(
    () => Array.from(new Set(rows.map((row) => row.category))).sort(),
    [rows],
  );
  const filtered = rows.filter((row) => {
    const q = query.trim().toLowerCase();
    const matchesQuery =
      q.length === 0 ||
      row.title.toLowerCase().includes(q) ||
      row.feedUrl.toLowerCase().includes(q);
    const matchesCategory = category === null || row.category === category;
    return matchesQuery && matchesCategory;
  });

  return (
    <>
      <div
        className="row gap-8"
        style={{ justifyContent: "space-between", marginBottom: 12 }}
      >
        <div className="row gap-6 wrap">
          {[null, ...categories].map((item) => (
            <Button
              key={item ?? "__all"}
              type="button"
              size="sm"
              variant={category === item ? "default" : "ghost"}
              onClick={() => setCategory(item)}
            >
              {item ?? t.subscriptions.all}
            </Button>
          ))}
        </div>
        <div className="search-wrap" style={{ width: 260 }}>
          <Search />
          <input
            className="input"
            placeholder={t.subscriptions.searchPlaceholder}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>
      <div className="card" style={{ overflow: "hidden" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: "34%" }}>{t.subscriptions.titleColumn}</th>
              <th>{t.subscriptions.feedUrl}</th>
              <th style={{ width: 120 }}>{t.subscriptions.category}</th>
              <th style={{ width: 80, textAlign: "right" }}>
                {t.subscriptions.unread}
              </th>
              <th style={{ width: 120 }}>{t.subscriptions.lastUpdated}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td>
                  <div className="row gap-8">
                    <Rss size={13} className="muted-2" />
                    <span style={{ fontWeight: 500 }} className="elip">
                      {row.title}
                    </span>
                  </div>
                </td>
                <td>
                  {row.feedUrl ? (
                    <a
                      className="mono link-ext elip"
                      style={{
                        fontSize: 11.5,
                        display: "block",
                        maxWidth: 360,
                      }}
                      href={row.feedUrl}
                      target="_blank"
                      rel="noopener"
                    >
                      {row.feedUrl}
                    </a>
                  ) : (
                    <span className="mono muted-2" style={{ fontSize: 11.5 }}>
                      {t.subscriptions.noFeedUrl}
                    </span>
                  )}
                </td>
                <td>
                  <span className="chip">{row.category}</span>
                </td>
                <td style={{ textAlign: "right" }}>
                  {row.unread && row.unread > 0 ? (
                    <span
                      className={`badge ${row.unread > 30 ? "amber" : "accent"}`}
                    >
                      {row.unread}
                    </span>
                  ) : (
                    <span className="num muted-2">0</span>
                  )}
                </td>
                <td>
                  <span className="mono muted" style={{ fontSize: 11.5 }}>
                    {row.updatedAt
                      ? timeAgo(row.updatedAt, new Date(), locale)
                      : "—"}
                  </span>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  style={{
                    textAlign: "center",
                    color: "var(--text-4)",
                    height: 80,
                  }}
                >
                  {t.subscriptions.noMatches(query)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
