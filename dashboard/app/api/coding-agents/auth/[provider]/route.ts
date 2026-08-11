import {
  cancelCodingAgentAuthSession,
  getCodingAgentAuthView,
  sendCodingAgentAuthInput,
  startCodingAgentAuthSession,
} from "@/lib/coding-agent-auth";
import { parseCodingAgentAuthProvider } from "@/lib/coding-agent-auth-types";
import { isSameOriginRequest } from "@/lib/same-origin";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ provider: string }> };

async function providerFrom(context: RouteContext) {
  const provider = parseCodingAgentAuthProvider(
    (await context.params).provider,
  );
  if (!provider) throw new Error("Unsupported coding-agent provider");
  return provider;
}

function errorResponse(error: unknown, status: number): Response {
  const message =
    typeof error === "string"
      ? error
      : error instanceof Error
        ? error.message
        : "Authentication request failed";
  return Response.json({ error: message.slice(0, 500) }, { status });
}

async function requireEmptyBody(request: Request): Promise<boolean> {
  return (await request.text()).trim() === "";
}

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  try {
    return Response.json(
      await getCodingAgentAuthView(await providerFrom(context)),
      {
        headers: { "Cache-Control": "no-store" },
      },
    );
  } catch (error) {
    return errorResponse(error, 404);
  }
}

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  if (!isSameOriginRequest(request))
    return errorResponse("Cross-origin request rejected", 403);
  if (!(await requireEmptyBody(request)))
    return errorResponse("Request body must be empty", 400);
  try {
    const provider = await providerFrom(context);
    startCodingAgentAuthSession(provider);
    return Response.json(await getCodingAgentAuthView(provider), {
      status: 202,
    });
  } catch (error) {
    return errorResponse(error, 409);
  }
}

export async function PUT(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  if (!isSameOriginRequest(request))
    return errorResponse("Cross-origin request rejected", 403);
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return errorResponse("Invalid JSON body", 400);
  }
  if (!body || typeof body !== "object")
    return errorResponse("Invalid input body", 400);
  const record = body as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  if (
    keys.length !== 2 ||
    keys[0] !== "sessionId" ||
    keys[1] !== "value" ||
    typeof record.sessionId !== "string" ||
    typeof record.value !== "string"
  ) {
    return errorResponse(
      "Only sessionId and one bounded input value are accepted",
      400,
    );
  }
  try {
    const session = sendCodingAgentAuthInput(
      await providerFrom(context),
      record.sessionId,
      record.value,
    );
    return Response.json({ session });
  } catch (error) {
    return errorResponse(error, 409);
  }
}

export async function DELETE(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  if (!isSameOriginRequest(request))
    return errorResponse("Cross-origin request rejected", 403);
  if (!(await requireEmptyBody(request)))
    return errorResponse("Request body must be empty", 400);
  try {
    const session = cancelCodingAgentAuthSession(await providerFrom(context));
    return Response.json({ session });
  } catch (error) {
    return errorResponse(error, 409);
  }
}
