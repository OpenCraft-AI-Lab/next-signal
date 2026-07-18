"use client";

import { Check, Loader2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/components/i18n-provider";
import { cn } from "@/lib/utils";
import { INGEST_STEPS, type IngestJob, type StepStatus } from "@/lib/ingest/types";

/** Subscribe once to the shared ingest-job SSE feed and render a card per job —
 *  including jobs started from /radar. On a job finishing, refresh the wiki
 *  tree so the new doc shows up, then let the card linger briefly and drop. */
export function ActiveIngests() {
  const { t } = useI18n();
  const router = useRouter();
  const [jobs, setJobs] = useState<Record<string, IngestJob>>({});
  const refreshed = useRef<Set<string>>(new Set());

  useEffect(() => {
    const es = new EventSource("/api/knowledge/ingest/stream");
    const pending: ReturnType<typeof setTimeout>[] = [];

    const drop = (id: string, delay: number) =>
      pending.push(
        setTimeout(
          () =>
            setJobs((prev) => {
              const next = { ...prev };
              delete next[id];
              return next;
            }),
          delay,
        ),
      );

    es.addEventListener("update", (e) => {
      const job = JSON.parse((e as MessageEvent).data) as IngestJob;
      setJobs((prev) => ({ ...prev, [job.id]: job }));
      if (job.status !== "running" && !refreshed.current.has(job.id)) {
        refreshed.current.add(job.id);
        if (job.status === "done") router.refresh();
        drop(job.id, job.status === "done" ? 6000 : 12000);
      }
    });

    es.addEventListener("remove", (e) => {
      const { id } = JSON.parse((e as MessageEvent).data) as { id: string };
      setJobs((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    });

    return () => {
      es.close();
      pending.forEach((tid) => clearTimeout(tid));
    };
  }, [router]);

  const list = Object.values(jobs).sort((a, b) =>
    a.startedAt.localeCompare(b.startedAt),
  );
  if (list.length === 0) return null;

  return (
    <div className="col gap-8">
      <span className="eyebrow">{t.knowledge.ingest.activeTitle}</span>
      {list.map((job) => (
        <IngestCard key={job.id} job={job} />
      ))}
    </div>
  );
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "running")
    return <Loader2 size={13} className="spin" style={{ color: "var(--accent)" }} />;
  if (status === "done") return <Check size={13} style={{ color: "var(--ok, #22a06b)" }} />;
  if (status === "error") return <X size={13} style={{ color: "var(--danger, #d4504e)" }} />;
  return (
    <span
      style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: "var(--text-4)",
        display: "inline-block",
      }}
    />
  );
}

function IngestCard({ job }: { job: IngestJob }) {
  const { t } = useI18n();
  const markdownPath =
    typeof job.result?.markdown_path === "string" ? job.result.markdown_path : null;
  const category =
    typeof job.result?.category === "string" ? job.result.category : job.category;
  const ingestResult = job.result?.ingest;
  const indexed =
    ingestResult && typeof ingestResult === "object"
      ? (ingestResult as { ok?: unknown }).ok === true
      : null;

  return (
    <div className="card" style={{ padding: 12 }}>
      <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
        <span className="elip mono" style={{ fontSize: 12, color: "var(--text-3)" }}>
          {job.value}
        </span>
        <span className="badge">{t.knowledge.ingest.source[job.source]}</span>
      </div>

      <div className="row gap-8 wrap" style={{ marginTop: 8 }}>
        {INGEST_STEPS.map((step) => (
          <span
            key={step}
            className={cn("row", "gap-6")}
            style={{
              alignItems: "center",
              fontSize: 12,
              color: job.steps[step] === "pending" ? "var(--text-4)" : "var(--text-2)",
            }}
          >
            <StepIcon status={job.steps[step]} />
            {t.knowledge.ingest.steps[step]}
          </span>
        ))}
      </div>

      {job.status === "done" && markdownPath && (
        <div className="row gap-8 wrap" style={{ marginTop: 8, fontSize: 12 }}>
          <span className="muted">{t.knowledge.ingest.savedTo(markdownPath)}</span>
          {category && <span className="badge">{t.knowledge.ingest.category(category)}</span>}
          {indexed !== null && (
            <span className={cn("badge", indexed ? "accent" : "danger")}>
              {indexed ? t.knowledge.ingest.indexed : t.knowledge.ingest.indexFailed}
            </span>
          )}
        </div>
      )}

      {job.status === "error" && (
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--danger, #d4504e)" }}>
          {t.knowledge.ingest.failed}
          {job.error ? `: ${job.error}` : ""}
        </div>
      )}
    </div>
  );
}
