import {
  cancelFoloSignIn,
  getFoloSignIn,
  startFoloSignIn,
} from "@/lib/folo-auth";
import { isSameOriginRequest } from "@/lib/same-origin";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Start, poll, and cancel the Folo browser sign-in.
 *
 * The callback address is derived from *this* request rather than configured:
 * whatever origin reached the dashboard is the origin the operator's browser
 * can reach, which is the whole reason the dashboard hosts the callback instead
 * of `folocli`. Same-origin is enforced on the mutating verbs, matching the
 * coding-agent auth endpoints.
 */
function errorResponse(error: unknown, status: number): Response {
  const message =
    typeof error === "string"
      ? error
      : error instanceof Error
        ? error.message
        : "Folo sign-in request failed";
  return Response.json({ error: message.slice(0, 500) }, { status });
}

async function requireEmptyBody(request: Request): Promise<boolean> {
  return (await request.text()).trim() === "";
}

function callbackUrlFor(request: Request): string {
  const url = new URL(request.url);
  const forwardedHost = request.headers
    .get("x-forwarded-host")
    ?.split(",")[0]
    ?.trim();
  const forwardedProto = request.headers
    .get("x-forwarded-proto")
    ?.split(",")[0]
    ?.trim();
  const host = forwardedHost || request.headers.get("host") || url.host;
  const protocol = forwardedProto ? `${forwardedProto}:` : url.protocol;
  return `${protocol}//${host}/api/folo/callback`;
}

export async function GET(): Promise<Response> {
  return Response.json(
    { session: getFoloSignIn() },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export async function POST(request: Request): Promise<Response> {
  if (!isSameOriginRequest(request))
    return errorResponse("Cross-origin request rejected", 403);
  if (!(await requireEmptyBody(request)))
    return errorResponse("Request body must be empty", 400);
  try {
    return Response.json(
      { session: startFoloSignIn(callbackUrlFor(request)) },
      { status: 202 },
    );
  } catch (error) {
    return errorResponse(error, 409);
  }
}

export async function DELETE(request: Request): Promise<Response> {
  if (!isSameOriginRequest(request))
    return errorResponse("Cross-origin request rejected", 403);
  if (!(await requireEmptyBody(request)))
    return errorResponse("Request body must be empty", 400);
  try {
    return Response.json({ session: cancelFoloSignIn() });
  } catch (error) {
    return errorResponse(error, 409);
  }
}
