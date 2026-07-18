// Pure types + constants shared between the server-only job runner
// (`jobs.ts`) and client components. Keep this module free of `server-only`
// and of any Node imports so client code can use it.

export const INGEST_STEPS = ["fetch", "clean", "enrich", "classify", "persist"] as const;
export type IngestStep = (typeof INGEST_STEPS)[number];
export type StepStatus = "pending" | "running" | "done" | "error";
export type IngestSource = "knowledge" | "radar";

export type IngestJob = {
  id: string;
  value: string;
  category: string | null;
  source: IngestSource;
  status: "running" | "done" | "error";
  steps: Record<IngestStep, StepStatus>;
  startedAt: string;
  finishedAt: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
};
