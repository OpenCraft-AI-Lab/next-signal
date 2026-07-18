"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

/**
 * Confirm-before-delete dialog wrapping any trigger element. The Cancel button
 * comes first so radix auto-focuses it (not Delete) — anti-misclick. `action`
 * is a bound server action; on success we toast + refresh the route so the tree
 * and ingest dropdown re-render.
 */
export function DeleteConfirm({
  title,
  body,
  action,
  children,
}: {
  title: string;
  body: string;
  action: () => Promise<{ ok: boolean; message: string }>;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const m = t.knowledge.manage;
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{body}</DialogDescription>
        </DialogHeader>
        <div className="row gap-8" style={{ justifyContent: "flex-end" }}>
          <DialogClose asChild>
            <Button variant="ghost" disabled={pending}>
              {m.cancel}
            </Button>
          </DialogClose>
          <Button
            variant="danger"
            disabled={pending}
            onClick={async () => {
              setPending(true);
              const res = await action();
              setPending(false);
              if (res.ok) {
                toast.success(res.message);
                setOpen(false);
                router.refresh();
              } else {
                toast.error(res.message);
              }
            }}
          >
            {pending ? m.deleting : m.confirmDelete}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
