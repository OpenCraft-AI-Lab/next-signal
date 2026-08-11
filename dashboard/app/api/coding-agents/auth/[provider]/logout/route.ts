import { logoutCodingAgent } from "@/lib/coding-agent-auth";
import { parseCodingAgentAuthProvider } from "@/lib/coding-agent-auth-types";
import { isSameOriginRequest } from "@/lib/same-origin";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ provider: string }> };

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  if (!isSameOriginRequest(request)) {
    return Response.json(
      { error: "Cross-origin request rejected" },
      { status: 403 },
    );
  }
  if ((await request.text()).trim()) {
    return Response.json(
      { error: "Request body must be empty" },
      { status: 400 },
    );
  }
  const provider = parseCodingAgentAuthProvider(
    (await context.params).provider,
  );
  if (!provider) {
    return Response.json(
      { error: "Unsupported coding-agent provider" },
      { status: 404 },
    );
  }
  try {
    return Response.json(await logoutCodingAgent(provider));
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Provider logout failed";
    return Response.json({ error: message.slice(0, 500) }, { status: 409 });
  }
}
