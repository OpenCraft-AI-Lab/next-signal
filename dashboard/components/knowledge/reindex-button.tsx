"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { reindexKnowledge } from "@/lib/actions/knowledge";

export function ReindexButton() {
  const { locale, t } = useI18n();
  const [pending, setPending] = useState(false);
  return (
    <Button
      disabled={pending}
      onClick={async () => {
        setPending(true);
        toast.info(t.knowledge.reindex.toastTitle, {
          description: t.knowledge.reindex.toastDescription,
        });
        const result = await reindexKnowledge(locale);
        setPending(false);
        if (result.ok) toast.success(result.message);
        else toast.error(result.message);
      }}
    >
      <RefreshCw size={14} className={pending ? "spin" : undefined} />
      {pending ? t.knowledge.reindex.pending : t.knowledge.reindex.idle}
    </Button>
  );
}
