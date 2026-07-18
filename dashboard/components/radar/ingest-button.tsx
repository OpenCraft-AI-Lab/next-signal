"use client";

import { Plus } from "lucide-react";
import { useState, type MouseEvent } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { ingestToWiki } from "@/lib/actions/radar";

export function IngestButton({
  itemId,
  primary = false,
}: {
  itemId: number;
  primary?: boolean;
}) {
  const { locale, t } = useI18n();
  const [pending, setPending] = useState(false);

  async function onClick(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    setPending(true);
    const result = await ingestToWiki(itemId, locale);
    setPending(false);
    if (result.ok) toast.success(result.message);
    else toast.error(result.message);
  }

  return (
    <Button
      variant={primary ? "primary" : "default"}
      size={primary ? "default" : "sm"}
      onClick={onClick}
      disabled={pending}
    >
      <Plus size={14} />
      {pending ? t.radar.ingest.pending : t.radar.ingest.idle}
    </Button>
  );
}
