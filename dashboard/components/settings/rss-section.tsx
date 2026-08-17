"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { InlineCredential } from "@/components/settings/inline-credential";
import { SettingsSectionShell } from "@/components/settings/section-shell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

/**
 * The RSS section owns `FOLO_TOKEN` — the credential info-radar's Folo
 * source and the Subscriptions page depend on. Moved out of the former flat
 * Credentials section into its own section, with the same assisted sign-in
 * as before.
 *
 * Two peer entry points rather than a sign-in button with a credential row
 * stacked underneath it: sign-in is the common path, and manual paste is the
 * fallback for a browser that cannot reach the dashboard or a Folo-side
 * contract change. A popup keeps the fallback from permanently occupying
 * space on the page for the common case that never uses it.
 */
export function RssSection({
  credentialPresence,
  onCredentialChange,
}: {
  credentialPresence: Record<string, boolean>;
  onCredentialChange: (name: string, present: boolean) => void;
}) {
  const { t } = useI18n();
  const present = Boolean(credentialPresence.FOLO_TOKEN);
  const [manualOpen, setManualOpen] = useState(false);
  const setPresent = (value: boolean) => onCredentialChange("FOLO_TOKEN", value);

  const summary = (
    <span className={`set-status ${present ? "ok" : "warn"}`}>
      <span className="dot" />
      {present ? t.settings.credentialSet : t.settings.credentialUnset}
    </span>
  );

  return (
    <SettingsSectionShell
      id="rss"
      label={t.settings.rss}
      hint={t.settings.rssHint}
      summary={summary}
    >
      <div className="set-row">
        <div className="set-rowtext">
          <span className="set-label">FOLO_TOKEN</span>
          <span className="set-hint">{t.settings.foloHint}</span>
        </div>
        <div className="set-rowctl set-credrow">
          <FoloSignIn onConnected={() => setPresent(true)} />
          <Dialog open={manualOpen} onOpenChange={setManualOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost">
                {t.settings.foloPasteManually}
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-sm">
              <DialogHeader>
                <DialogTitle>{t.settings.foloPasteManually}</DialogTitle>
                <DialogDescription>{t.settings.foloManualHint}</DialogDescription>
              </DialogHeader>
              <InlineCredential
                name="FOLO_TOKEN"
                label="FOLO_TOKEN"
                present={present}
                onChange={(next) => {
                  setPresent(next);
                  if (next) setManualOpen(false);
                }}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>
    </SettingsSectionShell>
  );
}

type SignInSession = {
  phase: "running" | "connected" | "failed" | "cancelled" | "timed_out";
  signInUrl: string | null;
  error: string | null;
};

/**
 * Folo has no API-token page, so its credential gets an assisted sign-in: the
 * dashboard hosts the callback, exchanges the returned one-time token, and
 * writes the session token itself.
 */
function FoloSignIn({ onConnected }: { onConnected: () => void }) {
  const { t } = useI18n();
  const [session, setSession] = useState<SignInSession | null>(null);
  const [busy, setBusy] = useState(false);

  // While a sign-in is running the outcome arrives on the callback route, in a
  // different request — polling this process's session is how this tab learns.
  useEffect(() => {
    if (session?.phase !== "running") return;
    const poll = setInterval(async () => {
      try {
        const res = await fetch("/api/folo/signin", { cache: "no-store" });
        const body = (await res.json()) as { session: SignInSession | null };
        if (!body.session) return;
        setSession(body.session);
        if (body.session.phase === "connected") {
          onConnected();
          toast.success(t.settings.foloConnected);
        } else if (body.session.phase === "failed") {
          toast.error(body.session.error ?? t.settings.foloFailed);
        } else if (body.session.phase === "timed_out") {
          toast.error(t.settings.foloTimedOut);
        }
      } catch {
        // A dropped poll is not an outcome; the next tick retries.
      }
    }, 1500);
    return () => clearInterval(poll);
  }, [session?.phase, onConnected, t]);

  const start = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/folo/signin", { method: "POST" });
      const body = (await res.json()) as {
        session?: SignInSession;
        error?: string;
      };
      if (!res.ok || !body.session) {
        throw new Error(body.error ?? t.settings.foloFailed);
      }
      setSession(body.session);
      if (body.session.signInUrl) window.open(body.session.signInUrl, "_blank");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t.settings.foloFailed);
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await fetch("/api/folo/signin", { method: "DELETE" });
      setSession(null);
    } finally {
      setBusy(false);
    }
  };

  if (session?.phase === "running") {
    return (
      <>
        <span className="set-status idle">{t.settings.foloWaiting}</span>
        {/* The URL is server-checked against the Folo host allowlist before it
            is ever handed to the client, so this is safe to offer directly. */}
        {session.signInUrl && (
          <a
            className="set-note"
            href={session.signInUrl}
            target="_blank"
            rel="noreferrer noopener"
          >
            {t.settings.foloReopen}
          </a>
        )}
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => void cancel()}>
          {t.settings.foloCancel}
        </Button>
      </>
    );
  }

  return (
    <Button size="sm" disabled={busy} onClick={() => void start()}>
      {t.settings.foloConnect}
    </Button>
  );
}
