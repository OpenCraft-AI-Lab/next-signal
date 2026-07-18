import { AlertTriangle } from "lucide-react";

import { SubscriptionsTable } from "@/components/subscriptions/subscriptions-table";
import { getDictionary } from "@/lib/i18n/dictionaries";
import { getLocale } from "@/lib/i18n/server";
import { getSubscriptions } from "@/lib/subscriptions";

export const dynamic = "force-dynamic";

export default async function SubscriptionsPage() {
  const locale = await getLocale();
  const t = getDictionary(locale);
  const state = await getSubscriptions();
  const rows = state.ok ? state.rows : [];
  const totalUnread = rows.reduce((sum, row) => sum + (row.unread ?? 0), 0);

  return (
    <div className="page page-enter">
      <div className="shell">
        <div
          className="row"
          style={{
            justifyContent: "space-between",
            alignItems: "flex-end",
            marginBottom: 18,
          }}
        >
          <div>
            <h1 className="page-title">{t.subscriptions.title}</h1>
            <p className="page-sub">
              {state.ok
                ? t.subscriptions.subtitle(rows.length, totalUnread)
                : t.subscriptions.loadingSubtitle}
            </p>
          </div>
        </div>

        {!state.ok ? (
          <div className="filter-empty" style={{ textAlign: "left" }}>
            <div
              className="row gap-8"
              style={{ alignItems: "center", marginBottom: 8 }}
            >
              <AlertTriangle size={16} style={{ color: "var(--amber)" }} />
              <strong style={{ color: "var(--text)" }}>
                {t.subscriptions.unable}
              </strong>
            </div>
            <p style={{ margin: 0, lineHeight: 1.6 }}>
              {t.subscriptions.checkAuth(state.message)}
            </p>
          </div>
        ) : rows.length === 0 ? (
          <div className="filter-empty">{t.subscriptions.empty}</div>
        ) : (
          <SubscriptionsTable rows={rows} />
        )}
      </div>
    </div>
  );
}
