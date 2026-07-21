import { getRecap } from "@/lib/radar/recap";

// Live status read — never cache.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Poll endpoint for the recap panel. Returns only the row's `status` — the
 * panel itself is server-rendered, so on a `running` → `done` transition the
 * client calls `router.refresh()` rather than rendering from this payload.
 * `status: null` means no recap row exists for the key yet.
 */
export async function GET(request: Request): Promise<Response> {
  const params = new URL(request.url).searchParams;
  const since = params.get("since") ?? "";
  const until = params.get("until") ?? "";
  if (!DAY_RE.test(since) || !DAY_RE.test(until)) {
    return Response.json({ status: null }, { status: 400 });
  }

  const recap = await getRecap({
    since,
    until,
    minScore: Number(params.get("minScore") ?? 0) || 0,
    novelOnly: params.get("novelOnly") === "1",
  });
  return Response.json({ status: recap?.status ?? null });
}
