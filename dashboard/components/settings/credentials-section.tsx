"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useI18n } from "@/components/i18n-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { deleteCredential, saveCredential } from "@/lib/actions/secrets";
import { CREDENTIAL_NAMES, type CredentialPresence } from "@/lib/secrets";

/**
 * Every provider credential, in one place.
 *
 * One section rather than a field beside each provider: five of the seven have
 * no settings card to sit next to, and there is now exactly one file holding
 * credentials, so one place to edit them is the honest reflection of that. The
 * engine and embedding sections keep a presence indicator and point here.
 *
 * ## What crosses the wire
 *
 * Only `presence` — a boolean per credential — arrives from the server. An
 * input is write-only: it holds what the operator is typing and is cleared on
 * save, and nothing ever renders a stored value or a fragment of one. There is
 * deliberately no masked preview: with no migration, the only way a credential
 * is in the store is that someone typed it here, so a preview would disambiguate
 * between candidates that do not exist while leaking part of a short token.
 *
 * Saving takes effect on the next use — credentials resolve at call time from
 * the shared state volume, so nothing here tells the operator to restart a
 * process or recreate a container.
 */
export function CredentialsSection({
  presence: initialPresence,
}: {
  presence: CredentialPresence;
}) {
  const { t } = useI18n();
  const [presence, setPresence] = useState(initialPresence);
  const markPresent = (name: string) =>
    setPresence((p) => ({ ...p, [name]: true }));

  return (
    <section className="card pad set-card" id="credentials">
      <div className="set-row">
        <div className="set-rowtext">
          <span className="set-label">{t.settings.credentials}</span>
          <span className="set-hint">{t.settings.credentialsHint}</span>
        </div>
      </div>
      {CREDENTIAL_NAMES.map((name) => (
        <CredentialRow
          key={name}
          name={name}
          present={presence[name] ?? false}
          onChange={(next) => setPresence((p) => ({ ...p, [name]: next }))}
          assist={
            name === "FOLO_TOKEN" ? (
              <FoloSignIn onConnected={() => markPresent("FOLO_TOKEN")} />
            ) : null
          }
          assistHint={name === "FOLO_TOKEN" ? t.settings.foloHint : null}
        />
      ))}
    </section>
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
 *
 * The manual input stays right beside this and produces the same stored result.
 * That is deliberate — a browser that cannot reach the dashboard, or a Folo-side
 * contract change, must leave the operator a way through rather than a dead end.
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

function CredentialRow({
  name,
  present,
  onChange,
  assist,
  assistHint,
}: {
  name: string;
  present: boolean;
  onChange: (present: boolean) => void;
  /** Optional helper control for credentials that can be obtained in-app. */
  assist?: React.ReactNode;
  /** Explains that helper, shown under the credential description. */
  assistHint?: string | null;
}) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    const trimmed = value.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      await saveCredential(name, trimmed);
      setValue(""); // never keep a credential in client state after the write
      onChange(true);
      toast.success(t.settings.credentialSaved);
    } catch (err) {
      // The credential is never inside the logged object: the action rejects
      // with a message naming it, not carrying it.
      console.error(`failed to save ${name}`, err);
      toast.error(t.settings.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await deleteCredential(name);
      onChange(false);
      toast.success(t.settings.credentialCleared);
    } catch (err) {
      console.error(`failed to clear ${name}`, err);
      toast.error(t.settings.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="set-row">
      <div className="set-rowtext">
        <span className="set-label">{name}</span>
        <span className="set-hint">
          {present
            ? t.settings.credentialPowers[name]
            : `${t.settings.credentialPowers[name]} ${t.settings.credentialUnsetSuffix}`}
        </span>
        {assistHint && <span className="set-hint">{assistHint}</span>}
      </div>
      <div className="set-rowctl set-credrow">
        {assist}
        <span className={`set-status ${present ? "ok" : "warn"}`}>
          {present ? t.settings.credentialSet : t.settings.credentialUnset}
        </span>
        <Input
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={value}
          disabled={busy}
          aria-label={name}
          placeholder={
            present ? t.settings.credentialReplace : t.settings.credentialEnter
          }
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void save();
          }}
        />
        <Button
          size="sm"
          variant="primary"
          disabled={busy || !value.trim()}
          onClick={() => void save()}
        >
          {t.settings.credentialSave}
        </Button>
        {present && (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => void clear()}
          >
            {t.settings.credentialClear}
          </Button>
        )}
      </div>
    </div>
  );
}
