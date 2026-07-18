"use client";

import { Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { startKnowledgeIngest } from "@/lib/actions/knowledge";
import type { WikiCategoryOption } from "@/lib/taxonomy";

type Group = { namespace: string | null; items: WikiCategoryOption[] };

/** Group taxonomy paths by their top-level namespace (prefix before `/`);
 *  paths without a `/` (e.g. `life`) are returned ungrouped (namespace null). */
function groupByNamespace(categories: WikiCategoryOption[]): Group[] {
  const grouped = new Map<string, WikiCategoryOption[]>();
  const ungrouped: WikiCategoryOption[] = [];
  for (const cat of categories) {
    const slash = cat.path.indexOf("/");
    if (slash === -1) {
      ungrouped.push(cat);
    } else {
      const ns = cat.path.slice(0, slash);
      const list = grouped.get(ns) ?? [];
      list.push(cat);
      grouped.set(ns, list);
    }
  }
  const groups: Group[] = [...grouped.entries()].map(([namespace, items]) => ({
    namespace,
    items,
  }));
  if (ungrouped.length > 0) groups.push({ namespace: null, items: ungrouped });
  return groups;
}

export function IngestForm({ categories }: { categories: WikiCategoryOption[] }) {
  const { locale, t } = useI18n();
  const [value, setValue] = useState("");
  const [category, setCategory] = useState("");
  const [pending, setPending] = useState(false);
  const groups = useMemo(() => groupByNamespace(categories), [categories]);

  return (
    <form
      className="col gap-8"
      onSubmit={async (e) => {
        e.preventDefault();
        const trimmed = value.trim();
        if (!trimmed) {
          toast.error(t.knowledge.ingest.errorEmpty);
          return;
        }
        setPending(true);
        try {
          const res = await startKnowledgeIngest(trimmed, category || null, locale);
          if (res.ok) {
            toast.success(res.message);
            setValue("");
          } else {
            toast.error(res.message);
          }
        } finally {
          setPending(false);
        }
      }}
    >
      <span className="eyebrow">{t.knowledge.ingest.heading}</span>
      <div className="row gap-8 wrap">
        <Input
          name="ingest-url"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t.knowledge.ingest.placeholder}
          style={{ flex: "2 1 280px", height: 38, fontSize: 14 }}
        />
        <select
          aria-label={t.knowledge.ingest.folderLabel}
          className="input"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          style={{ flex: "1 1 180px", height: 38, fontSize: 14 }}
        >
          <option value="">{t.knowledge.ingest.autoClassify}</option>
          {groups.map((group) =>
            group.namespace ? (
              <optgroup key={group.namespace} label={group.namespace}>
                {group.items.map((c) => (
                  <option key={c.path} value={c.path} title={c.scope}>
                    {c.path}
                  </option>
                ))}
              </optgroup>
            ) : (
              group.items.map((c) => (
                <option key={c.path} value={c.path} title={c.scope}>
                  {c.path}
                </option>
              ))
            ),
          )}
        </select>
        <Button type="submit" variant="primary" disabled={pending}>
          <Plus size={14} />
          {pending ? t.knowledge.ingest.submitting : t.knowledge.ingest.submit}
        </Button>
      </div>
    </form>
  );
}
