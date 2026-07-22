"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { refreshReviews } from "@/lib/actions/review";

/**
 * Refresh control: spawns `paca knowledge review` detached to reconcile the wiki
 * against the review table, so the toast says "started", not "finished".
 */
export function RefreshReviewsButton() {
  const { locale, t } = useI18n();
  const [pending, setPending] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={pending}
      onClick={async () => {
        setPending(true);
        toast.info(t.knowledge.review.refreshToastTitle, {
          description: t.knowledge.review.refreshToastDescription,
        });
        const result = await refreshReviews(locale);
        setPending(false);
        if (result.ok) toast.success(result.message);
        else toast.error(result.message);
      }}
    >
      <RefreshCw size={14} className={pending ? "spin" : undefined} />
      {pending ? t.knowledge.review.refreshPending : t.knowledge.review.refresh}
    </Button>
  );
}
