import { ingestEmitter, listJobs, type IngestJob } from "@/lib/ingest/jobs";

// Long-lived SSE connection — never cache or statically optimize.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Server-Sent Events feed of the shared ingest-job registry. On connect it
 * replays a snapshot of all current jobs (so a job already running — e.g.
 * started from /radar before this page loaded — shows immediately), then
 * streams `update` / `remove` events until the client disconnects.
 */
export function GET(request: Request): Response {
  const emitter = ingestEmitter();
  const encoder = new TextEncoder();
  let cleanup = (): void => {};

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const send = (event: string, data: unknown): void => {
        try {
          controller.enqueue(
            encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`),
          );
        } catch {
          cleanup();
        }
      };

      // Flush immediately so the connection (and headers) open right away,
      // even when there are no jobs to snapshot yet.
      try {
        controller.enqueue(encoder.encode(": connected\n\n"));
      } catch {
        cleanup();
      }

      for (const job of listJobs()) send("update", job);

      const onUpdate = (job: IngestJob): void => send("update", job);
      const onRemove = (id: string): void => send("remove", { id });
      emitter.on("update", onUpdate);
      emitter.on("remove", onRemove);

      // Comment heartbeat keeps intermediaries from closing an idle stream.
      const ping = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(": ping\n\n"));
        } catch {
          cleanup();
        }
      }, 25_000);

      cleanup = (): void => {
        clearInterval(ping);
        emitter.off("update", onUpdate);
        emitter.off("remove", onRemove);
        try {
          controller.close();
        } catch {
          // already closed
        }
      };

      request.signal.addEventListener("abort", cleanup);
    },
    cancel() {
      cleanup();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
