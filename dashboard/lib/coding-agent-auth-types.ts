export const CODING_AGENT_AUTH_PROVIDERS = ["codex", "claude"] as const;
export type CodingAgentAuthProvider =
  (typeof CODING_AGENT_AUTH_PROVIDERS)[number];

export type CodingAgentAuthPhase =
  | "running"
  | "connected"
  | "failed"
  | "cancelled"
  | "timed_out";

export type CodingAgentAuthSession = {
  id: string;
  provider: CodingAgentAuthProvider;
  phase: CodingAgentAuthPhase;
  transcript: string;
  loginUrl: string | null;
  error: string | null;
  startedAt: string;
  finishedAt: string | null;
};

export type CodingAgentAuthView = {
  provider: CodingAgentAuthProvider;
  available: boolean;
  connected: boolean;
  message: string;
  session: CodingAgentAuthSession | null;
};

const ALLOWED_DOMAINS: Record<CodingAgentAuthProvider, readonly string[]> = {
  codex: ["openai.com", "chatgpt.com"],
  claude: ["claude.com", "claude.ai", "anthropic.com"],
};

export function parseCodingAgentAuthProvider(
  value: string,
): CodingAgentAuthProvider | null {
  return (CODING_AGENT_AUTH_PROVIDERS as readonly string[]).includes(value)
    ? (value as CodingAgentAuthProvider)
    : null;
}

export function isAllowedCodingAgentLoginUrl(
  provider: CodingAgentAuthProvider,
  value: string,
): boolean {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:") return false;
    const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
    return ALLOWED_DOMAINS[provider].some(
      (domain) => host === domain || host.endsWith(`.${domain}`),
    );
  } catch {
    return false;
  }
}

export function appendBoundedAuthTranscript(
  current: string,
  chunk: string,
  maxChars: number,
): string {
  const combined = current + chunk;
  return combined.length <= maxChars ? combined : combined.slice(-maxChars);
}
