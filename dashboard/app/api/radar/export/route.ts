import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { readFile, unlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { loadRadarFilters } from "@/lib/radar/filter-params";
import {
  getItemsForDay,
  getLastFeedBounds,
  todayInRadarTz,
  type RadarItem,
} from "@/lib/radar/queries";

// Needs child_process + fs (drives system Chrome for PDF); never cache.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// System Chrome ships a headless `--print-to-pdf` mode — no extra dependency,
// no Chromium download. Override the path with CHROME_BIN if needed.
const CHROME =
  process.env.CHROME_BIN ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

/**
 * Download the current radar feed (exactly the active filter) as markdown or
 * PDF. Filters arrive as the same query params the page uses, so
 * `loadRadarFilters` resolves an identical view (defaults included).
 */
export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const format = url.searchParams.get("format") === "pdf" ? "pdf" : "md";
  const filters = await loadRadarFilters(url.searchParams);
  const today = todayInRadarTz();
  const focusDay = filters.day ?? today;
  const isToday = filters.day === null || filters.day === today;

  try {
    if (format === "pdf") {
      return await exportPdf(url, focusDay);
    }
    return await exportMarkdown(filters, focusDay, isToday);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return new Response(`radar export failed: ${message}`, { status: 500 });
  }
}

async function exportMarkdown(
  filters: Awaited<ReturnType<typeof loadRadarFilters>>,
  focusDay: string,
  isToday: boolean,
): Promise<Response> {
  // Mirror the page: "last feed only" bounds the query to the latest analyze
  // cluster, and only applies on today's view.
  const analyzeStart =
    isToday && filters.lastFeedOnly
      ? (await getLastFeedBounds(focusDay)).analyzeStart
      : null;
  const items = await getItemsForDay(focusDay, filters, analyzeStart);
  const body = renderRadarMarkdown(items, focusDay);
  return new Response(body, {
    headers: {
      "content-type": "text/markdown; charset=utf-8",
      "content-disposition": `attachment; filename="radar-${focusDay}.md"`,
    },
  });
}

function renderRadarMarkdown(items: RadarItem[], day: string): string {
  const lines: string[] = [`# Radar · ${day}`, "", `> ${items.length} signals`, ""];
  for (const item of items) {
    lines.push(`## ${item.title} \`${item.score}\``);
    const meta = [item.source];
    if (item.publishedAt) meta.push(item.publishedAt.slice(0, 16).replace("T", " "));
    if (item.sourceUrl) meta.push(`[link](${item.sourceUrl})`);
    lines.push(meta.join(" · "));
    if (item.tags.length > 0) lines.push(`tags: ${item.tags.join(", ")}`);
    lines.push("");
    if (item.summary) lines.push(item.summary.trim(), "");
    if (item.impactMd) lines.push(item.impactMd.trim(), "");
    lines.push("---", "");
  }
  return lines.join("\n");
}

async function exportPdf(reqUrl: URL, focusDay: string): Promise<Response> {
  if (!existsSync(CHROME)) {
    return new Response(
      `Chrome not found at ${CHROME}. Set CHROME_BIN to override.`,
      { status: 500 },
    );
  }
  // Print the live radar page in export mode — same origin, same filters.
  const target = new URL("/radar", reqUrl.origin);
  for (const [key, value] of reqUrl.searchParams) {
    if (key !== "format") target.searchParams.set(key, value);
  }
  target.searchParams.set("export", "1");

  const out = path.join(os.tmpdir(), `radar-${focusDay}-${randomUUID()}.pdf`);
  try {
    await runChromePdf(target.toString(), out);
    const bytes = await readFile(out);
    return new Response(new Uint8Array(bytes), {
      headers: {
        "content-type": "application/pdf",
        "content-disposition": `attachment; filename="radar-${focusDay}.pdf"`,
      },
    });
  } finally {
    await unlink(out).catch(() => {});
  }
}

// Hard ceiling on a single Chrome print, in ms.
const CHROME_TIMEOUT_MS = 30000;
// Grace after the PDF file appears before we kill Chrome, so a multi-page
// write finishes flushing.
const CHROME_SETTLE_MS = 1000;

function runChromePdf(targetUrl: string, outPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      CHROME,
      [
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        // Advance virtual time so React hydration / fonts settle before print.
        "--virtual-time-budget=10000",
        // Isolated profile so a running Chrome doesn't lock the default one.
        `--user-data-dir=${path.join(os.tmpdir(), "paca-radar-chrome")}`,
        `--print-to-pdf=${outPath}`,
        targetUrl,
      ],
      { stdio: "ignore" },
    );

    // The Next dev server holds an HMR websocket open, so Chrome's network is
    // never idle and it won't self-exit after `--print-to-pdf`. Treat the
    // output file appearing as "done": let it settle, then kill Chrome.
    let done = false;
    const finish = (err?: Error) => {
      if (done) return;
      done = true;
      clearInterval(poll);
      clearTimeout(hardKill);
      child.kill("SIGKILL");
      if (err) reject(err);
      else resolve();
    };
    const poll = setInterval(() => {
      if (!existsSync(outPath)) return;
      clearInterval(poll);
      setTimeout(() => finish(), CHROME_SETTLE_MS);
    }, 300);
    const hardKill = setTimeout(
      () =>
        finish(existsSync(outPath) ? undefined : new Error("chrome print timed out")),
      CHROME_TIMEOUT_MS,
    );
    child.on("error", (err) => finish(err));
    child.on("close", () =>
      finish(existsSync(outPath) ? undefined : new Error("chrome produced no pdf")),
    );
  });
}
