"use client";

import { FolderPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
import { Input } from "@/components/ui/input";
import { createWikiFolder } from "@/lib/actions/knowledge";

// Inlined to avoid pulling lib/taxonomy (which imports node:fs) into the client
// bundle. Mirrors the `freshness.tiers` keys in knowledge_taxonomy.yaml.
const FRESHNESS_TIERS = ["permanent", "stable", "evolving", "ephemeral"];

/** "New folder" button + create-folder dialog. Creates a wiki dir and registers
 *  it as a taxonomy category (ingest destination) in one step. */
export function NewFolderDialog() {
  const { locale, t } = useI18n();
  const m = t.knowledge.manage;
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [folderPath, setFolderPath] = useState("");
  const [scope, setScope] = useState("");
  const [freshness, setFreshness] = useState("");
  const [pending, setPending] = useState(false);

  const submit = async () => {
    setPending(true);
    try {
      const res = await createWikiFolder(folderPath, scope, freshness, locale);
      if (res.ok) {
        toast.success(res.message);
        setOpen(false);
        setFolderPath("");
        setScope("");
        setFreshness("");
        router.refresh();
      } else {
        toast.error(res.message);
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" aria-label={m.newFolder}>
          <FolderPlus size={13} />
          {m.newFolder}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{m.newFolderTitle}</DialogTitle>
          <DialogDescription>{m.newFolderDesc}</DialogDescription>
        </DialogHeader>
        <form
          className="col gap-12"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <label className="col gap-4">
            <span className="eyebrow">{m.pathLabel}</span>
            <Input
              autoFocus
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              placeholder={m.pathPlaceholder}
              style={{ height: 38, fontSize: 14 }}
            />
            <span className="muted-2" style={{ fontSize: 11 }}>
              {m.pathHint}
            </span>
          </label>
          <label className="col gap-4">
            <span className="eyebrow">{m.scopeLabel}</span>
            <Input
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder={m.scopePlaceholder}
              style={{ height: 38, fontSize: 14 }}
            />
          </label>
          <label className="col gap-4">
            <span className="eyebrow">{m.freshnessLabel}</span>
            <select
              className="input"
              value={freshness}
              onChange={(e) => setFreshness(e.target.value)}
              style={{ height: 38, fontSize: 14 }}
            >
              <option value="">{m.freshnessNone}</option>
              {FRESHNESS_TIERS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
          <div className="row gap-8" style={{ justifyContent: "flex-end" }}>
            <DialogClose asChild>
              <Button type="button" variant="ghost" disabled={pending}>
                {m.cancel}
              </Button>
            </DialogClose>
            <Button type="submit" variant="primary" disabled={pending}>
              {pending ? m.creating : m.create}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
