"use client";
import Icon from "@/components/Icon";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
export default function AccountNav() {
  const router = useRouter();
  const [signedIn, setSignedIn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    const c = new AbortController();
    fetch("/api/account/session", { cache: "no-store", signal: c.signal })
      .then(async (response) => {
        if (!response.ok) return;
        const data = await response.json();
        if (!c.signal.aborted) setSignedIn(data.signed_in === true);
      })
      .catch(() => {});
    return () => c.abort();
  }, []);
  return (
    <div className="nav-actions">
      {signedIn ? (
        <>
          <Link href="/tracker">My workspace</Link>
          <Link href="/settings">Settings</Link>
          <button
            className="btn-outline"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setMessage("");
              try {
                const response = await fetch("/api/account/logout", {
                  method: "POST",
                });
                if (!response.ok)
                  throw Error(
                    "Sign out could not be confirmed. Please try again.",
                  );
                setSignedIn(false);
                router.push("/");
                router.refresh();
              } catch {
                setMessage(
                  "Sign out could not be confirmed. Please try again.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Signing out…" : "Sign out"}
          </button>
        </>
      ) : (
        <>
          <Link href="/login">Log in</Link>
          <Link href="/signup" className="btn-primary">
            Create account <Icon name="arrow-up-right" />
          </Link>
        </>
      )}
      {message && <span role="alert">{message}</span>}
    </div>
  );
}
