import { LoaderCircle } from "lucide-react";

import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";

export default async function SubscriptionsLoading() {
  const t = getDictionary(await getLocale());
  return (
    <div className="page page-enter">
      <div className="shell">
        <div style={{ marginBottom: 18 }}>
          <h1 className="page-title">{t.subscriptions.title}</h1>
          <p className="page-sub">{t.subscriptions.loadingSubtitle}</p>
        </div>
        <div className="card" style={{ overflow: "hidden" }}>
          <div
            className="row"
            style={{
              padding: "10px 14px",
              gap: 10,
              borderBottom: "1px solid var(--line)",
            }}
          >
            <LoaderCircle
              size={14}
              className="spin"
              style={{ color: "var(--accent)" }}
            />
            <span
              className="mono"
              style={{ fontSize: 12, color: "var(--text-3)" }}
            >
              {t.subscriptions.loading}
            </span>
          </div>
          {Array.from({ length: 8 }).map((_, index) => (
            <div
              key={index}
              className="row"
              style={{
                height: "var(--row-h)",
                padding: "0 14px",
                gap: 14,
                borderBottom: "1px solid var(--border-2)",
                alignItems: "center",
              }}
            >
              <div
                className="skel"
                style={{ height: 12, width: `${30 + (index % 4) * 12}%` }}
              />
              <div
                className="skel"
                style={{ height: 12, width: 160, marginLeft: "auto" }}
              />
              <div className="skel" style={{ height: 16, width: 50 }} />
              <div className="skel" style={{ height: 12, width: 60 }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
