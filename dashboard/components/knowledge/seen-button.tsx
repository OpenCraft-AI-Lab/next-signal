"use client";

import { Check } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { markReviewSeen } from "@/lib/actions/review";

/**
 * "Seen" control for a review card. Calls the POST server action, which
 * advances the stage and revalidates the page — so on success the card simply
 * leaves the due list and this button unmounts with it.
 */
export function SeenButton({ docPath }: { docPath: string }) {
  const { t } = useI18n();
  const [pending, setPending] = useState(false);
  return (
    <Button
      size="sm"
      disabled={pending}
      onClick={async () => {
        setPending(true);
        const res = await markReviewSeen(docPath);
        if (!res.ok) {
          setPending(false);
          toast.error(t.knowledge.review.seenFailed);
        }
      }}
    >
      <Check size={14} />
      {pending ? t.knowledge.review.seenPending : t.knowledge.review.seen}
    </Button>
  );
}
