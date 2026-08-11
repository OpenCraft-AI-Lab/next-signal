/** Strict same-origin check for local state-changing API routes. */
export function isSameOriginRequest(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin || origin === "null") return false;
  try {
    const supplied = new URL(origin);
    const requestUrl = new URL(request.url);
    const forwardedHost = request.headers
      .get("x-forwarded-host")
      ?.split(",")[0]
      ?.trim();
    const forwardedProto = request.headers
      .get("x-forwarded-proto")
      ?.split(",")[0]
      ?.trim();
    const expectedHost =
      forwardedHost || request.headers.get("host") || requestUrl.host;
    const expectedProtocol = forwardedProto
      ? `${forwardedProto}:`
      : requestUrl.protocol;
    return (
      supplied.host === expectedHost && supplied.protocol === expectedProtocol
    );
  } catch {
    return false;
  }
}
