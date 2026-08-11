import "server-only";

import {
  execFile,
  spawn,
  type ChildProcessWithoutNullStreams,
} from "node:child_process";
import { randomUUID } from "node:crypto";

import {
  appendBoundedAuthTranscript,
  isAllowedCodingAgentLoginUrl,
  type CodingAgentAuthProvider,
  type CodingAgentAuthSession,
  type CodingAgentAuthView,
} from "@/lib/coding-agent-auth-types";
import { REPO_ROOT } from "@/lib/paths";

const MAX_TRANSCRIPT_CHARS = 12_000;
const MAX_PROTOCOL_LINE_CHARS = 16_384;
const MAX_INPUT_CHARS = 4_096;
const SESSION_TIMEOUT_MS = 10 * 60_000 + 15_000;
const FINISHED_TTL_MS = 5 * 60_000;

type ManagedSession = {
  snapshot: CodingAgentAuthSession;
  child: ChildProcessWithoutNullStreams;
  stdoutBuffer: string;
  resultSeen: boolean;
  inputSent: boolean;
  cancelRequested: boolean;
  forceTimer: ReturnType<typeof setTimeout> | null;
};

type Registry = Map<CodingAgentAuthProvider, ManagedSession>;

function registry(): Registry {
  const root = globalThis as typeof globalThis & {
    nsCodingAgentAuth?: Registry;
  };
  if (!root.nsCodingAgentAuth) root.nsCodingAgentAuth = new Map();
  return root.nsCodingAgentAuth;
}

function snapshot(session: ManagedSession): CodingAgentAuthSession {
  return { ...session.snapshot };
}

function safeError(value: unknown): string {
  const message = value instanceof Error ? value.message : String(value);
  return message.replace(/[\r\n\t]+/g, " ").slice(0, 500);
}

function activeSession(
  provider: CodingAgentAuthProvider,
): ManagedSession | null {
  const session = registry().get(provider) ?? null;
  return session?.snapshot.phase === "running" ? session : null;
}

function scheduleRemoval(
  provider: CodingAgentAuthProvider,
  session: ManagedSession,
): void {
  setTimeout(() => {
    if (registry().get(provider) === session) registry().delete(provider);
  }, FINISHED_TTL_MS).unref?.();
}

function finishWithoutResult(session: ManagedSession, error: string): void {
  if (session.snapshot.phase !== "running") return;
  session.snapshot.phase = session.cancelRequested ? "cancelled" : "failed";
  session.snapshot.error = session.cancelRequested ? null : error;
  session.snapshot.finishedAt = new Date().toISOString();
}

function handleProtocolObject(session: ManagedSession, value: unknown): void {
  if (!value || typeof value !== "object") return;
  const event = value as Record<string, unknown>;
  if (
    event.provider !== session.snapshot.provider ||
    typeof event.type !== "string"
  )
    return;

  if (event.type === "output" && typeof event.text === "string") {
    session.snapshot.transcript = appendBoundedAuthTranscript(
      session.snapshot.transcript,
      event.text,
      MAX_TRANSCRIPT_CHARS,
    );
    return;
  }

  if (
    event.type === "url" &&
    typeof event.url === "string" &&
    isAllowedCodingAgentLoginUrl(session.snapshot.provider, event.url)
  ) {
    session.snapshot.loginUrl = event.url;
    return;
  }

  if (event.type !== "result" || typeof event.ok !== "boolean") return;
  session.resultSeen = true;
  const connected = event.connected === true;
  if (event.ok && connected) {
    session.snapshot.phase = "connected";
    session.snapshot.error = null;
  } else if (event.timed_out === true) {
    session.snapshot.phase = "timed_out";
    session.snapshot.error = "Authentication timed out";
  } else if (event.cancelled === true || session.cancelRequested) {
    session.snapshot.phase = "cancelled";
    session.snapshot.error = null;
  } else {
    session.snapshot.phase = "failed";
    session.snapshot.error =
      typeof event.error === "string"
        ? safeError(event.error)
        : "Authentication failed";
  }
  session.snapshot.finishedAt = new Date().toISOString();
}

function handleProtocolLine(session: ManagedSession, line: string): void {
  if (!line || line.length > MAX_PROTOCOL_LINE_CHARS) return;
  try {
    handleProtocolObject(session, JSON.parse(line));
  } catch {
    // The Python broker promises JSONL. Ignore a stray launcher diagnostic;
    // close handling will produce a generic failure when no result follows.
  }
}

function brokerArgv(
  command: "auth-login" | "auth-status" | "auth-logout",
  provider: string,
) {
  return ["run", "next-signal", "coding-agent", command, provider];
}

function runBrokerJson(
  command: "auth-status" | "auth-logout",
  provider: CodingAgentAuthProvider,
): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    execFile(
      "uv",
      brokerArgv(command, provider),
      {
        cwd: REPO_ROOT,
        env: { ...process.env },
        timeout: 15_000,
        maxBuffer: 32_768,
      },
      (error, stdout) => {
        const line = stdout.trim().split(/\r?\n/).at(-1) ?? "";
        try {
          const parsed = JSON.parse(line);
          if (!parsed || typeof parsed !== "object")
            throw new Error("invalid broker JSON");
          resolve(parsed as Record<string, unknown>);
        } catch {
          reject(
            new Error(
              error
                ? "Coding-agent authentication broker is unavailable"
                : "Coding-agent authentication broker returned invalid JSON",
            ),
          );
        }
      },
    );
  });
}

export async function getCodingAgentAuthView(
  provider: CodingAgentAuthProvider,
): Promise<CodingAgentAuthView> {
  const existing = registry().get(provider);
  if (existing?.snapshot.phase === "running") {
    return {
      provider,
      available: true,
      connected: false,
      message: "Connecting",
      session: snapshot(existing),
    };
  }

  try {
    const value = await runBrokerJson("auth-status", provider);
    return {
      provider,
      available: value.available === true,
      connected: value.connected === true,
      message:
        typeof value.message === "string"
          ? safeError(value.message)
          : "Unknown status",
      session: existing ? snapshot(existing) : null,
    };
  } catch (error) {
    return {
      provider,
      available: false,
      connected: false,
      message: safeError(error),
      session: existing ? snapshot(existing) : null,
    };
  }
}

export async function getCodingAgentAuthViews(): Promise<
  Record<CodingAgentAuthProvider, CodingAgentAuthView>
> {
  const [codex, claude] = await Promise.all([
    getCodingAgentAuthView("codex"),
    getCodingAgentAuthView("claude"),
  ]);
  return { codex, claude };
}

export function startCodingAgentAuthSession(
  provider: CodingAgentAuthProvider,
): CodingAgentAuthSession {
  if (activeSession(provider))
    throw new Error(`${provider} authentication is already running`);

  const authSession: CodingAgentAuthSession = {
    id: randomUUID(),
    provider,
    phase: "running",
    transcript: "",
    loginUrl: null,
    error: null,
    startedAt: new Date().toISOString(),
    finishedAt: null,
  };
  const child = spawn("uv", brokerArgv("auth-login", provider), {
    cwd: REPO_ROOT,
    env: { ...process.env },
    stdio: ["pipe", "pipe", "pipe"],
  });
  const managed: ManagedSession = {
    snapshot: authSession,
    child,
    stdoutBuffer: "",
    resultSeen: false,
    inputSent: false,
    cancelRequested: false,
    forceTimer: null,
  };
  managed.forceTimer = setTimeout(() => {
    if (managed.snapshot.phase !== "running") return;
    managed.snapshot.phase = "timed_out";
    managed.snapshot.error = "Authentication timed out";
    managed.snapshot.finishedAt = new Date().toISOString();
    managed.child.kill("SIGTERM");
  }, SESSION_TIMEOUT_MS);
  managed.forceTimer?.unref?.();
  registry().set(provider, managed);

  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    managed.stdoutBuffer += chunk;
    let newline: number;
    while ((newline = managed.stdoutBuffer.indexOf("\n")) >= 0) {
      const line = managed.stdoutBuffer.slice(0, newline).trim();
      managed.stdoutBuffer = managed.stdoutBuffer.slice(newline + 1);
      handleProtocolLine(managed, line);
    }
    if (managed.stdoutBuffer.length > MAX_PROTOCOL_LINE_CHARS) {
      managed.stdoutBuffer = "";
      finishWithoutResult(
        managed,
        "Authentication broker output exceeded its limit",
      );
      child.kill("SIGTERM");
    }
  });

  // Never forward provider diagnostics or authorization material to app logs.
  child.stderr.resume();
  child.on("error", (error) => finishWithoutResult(managed, safeError(error)));
  child.on("close", (code) => {
    if (managed.forceTimer) clearTimeout(managed.forceTimer);
    if (managed.stdoutBuffer.trim())
      handleProtocolLine(managed, managed.stdoutBuffer.trim());
    if (!managed.resultSeen) {
      finishWithoutResult(
        managed,
        `Authentication broker exited with code ${code}`,
      );
    }
    if (!managed.snapshot.finishedAt)
      managed.snapshot.finishedAt = new Date().toISOString();
    scheduleRemoval(provider, managed);
  });

  return snapshot(managed);
}

export function sendCodingAgentAuthInput(
  provider: CodingAgentAuthProvider,
  sessionId: string,
  value: string,
): CodingAgentAuthSession {
  const session = activeSession(provider);
  if (!session || session.snapshot.id !== sessionId) {
    throw new Error("Authentication session is not running");
  }
  if (session.inputSent)
    throw new Error("Authorization input was already submitted");
  if (!value || value.length > MAX_INPUT_CHARS || /[\r\n]/.test(value)) {
    throw new Error(
      `Authorization input must be one to ${MAX_INPUT_CHARS} characters`,
    );
  }
  session.inputSent = true;
  session.child.stdin.end(`${value}\n`);
  return snapshot(session);
}

export function cancelCodingAgentAuthSession(
  provider: CodingAgentAuthProvider,
): CodingAgentAuthSession {
  const session = activeSession(provider);
  if (!session) throw new Error("Authentication session is not running");
  session.cancelRequested = true;
  session.snapshot.phase = "cancelled";
  session.snapshot.finishedAt = new Date().toISOString();
  session.child.kill("SIGTERM");
  return snapshot(session);
}

export async function logoutCodingAgent(
  provider: CodingAgentAuthProvider,
): Promise<CodingAgentAuthView> {
  if (activeSession(provider))
    throw new Error("Cancel the active authentication session first");
  const value = await runBrokerJson("auth-logout", provider);
  if (value.ok !== true) {
    throw new Error(
      typeof value.error === "string"
        ? safeError(value.error)
        : "Provider logout failed",
    );
  }
  registry().delete(provider);
  return getCodingAgentAuthView(provider);
}
