"use client";
import Icon from "@/components/Icon";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { accountRequest } from "@/lib/workspace";
type Profile = {
  full_name: string;
  email: string;
  country: string;
  email_verified_at?: string;
  onboarding_complete: boolean;
  auth_provider: string;
};
export default function Settings() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [emailEnabled, setEmailEnabled] = useState(false),
    [terms, setTerms] = useState(false),
    [age, setAge] = useState(false),
    [password, setPassword] = useState(""),
    [newPassword, setNewPassword] = useState(""),
    [newEmail, setNewEmail] = useState(""),
    [confirmation, setConfirmation] = useState("");
  useEffect(() => {
    const c = new AbortController();
    accountRequest("me", { signal: c.signal })
      .then(setProfile)
      .catch((e) => {
        if (!c.signal.aborted) setMessage(e.message);
      });
    fetch("/api/account/config", { signal: c.signal })
      .then((r) => r.json())
      .then((d) => setEmailEnabled(Boolean(d.email_enabled)))
      .catch(() => {});
    return () => c.abort();
  }, []);
  function leaveAccount(destination: string) {
    setProfile(null);
    router.replace(destination);
    router.refresh();
  }
  async function action(path: string, method: string, body?: unknown) {
    setBusy(true);
    setMessage("");
    try {
      const d = await accountRequest(path, {
        method,
        ...(body
          ? {
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            }
          : {}),
      });
      setMessage(d.message || "Saved.");
      return true;
    } catch (e) {
      setMessage((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Header />
      <main id="main-content" className="shell settings-page">
        <p className="eyebrow">YOUR ACCOUNT</p>
        <h1>Settings & data</h1>
        {message && (
          <p role="status" className="source-warning">
            {message}
          </p>
        )}
        {profile ? (
          <>
            <section className="surface-card">
              <h2>
                {profile.onboarding_complete
                  ? "Account details"
                  : "Complete your account"}
              </h2>
              <p>
                {profile.email} ·{" "}
                {profile.email_verified_at
                  ? "Email verified"
                  : "Email not yet verified"}
              </p>
              <form
                className="account-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (
                    await action("settings", "PUT", {
                      full_name: profile.full_name,
                      country: profile.country,
                      accepted_terms: terms,
                      age_confirmed: age,
                    })
                  ) {
                    setProfile({ ...profile, onboarding_complete: true });
                  }
                }}
              >
                <label>
                  Full name
                  <input
                    required
                    minLength={2}
                    maxLength={100}
                    value={profile.full_name}
                    onChange={(e) =>
                      setProfile({ ...profile, full_name: e.target.value })
                    }
                  />
                </label>
                <label>
                  Country code
                  <input
                    required
                    minLength={2}
                    maxLength={2}
                    value={profile.country}
                    onChange={(e) =>
                      setProfile({
                        ...profile,
                        country: e.target.value.toUpperCase(),
                      })
                    }
                  />
                </label>
                {!profile.onboarding_complete && (
                  <>
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        required
                        checked={age}
                        onChange={(e) => setAge(e.target.checked)}
                      />
                      I am at least 13 years old.
                    </label>
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        required
                        checked={terms}
                        onChange={(e) => setTerms(e.target.checked)}
                      />
                      I accept the <Link href="/terms">Terms</Link> and{" "}
                      <Link href="/privacy">Privacy Policy</Link>.
                    </label>
                  </>
                )}
                <button className="btn-primary" disabled={busy}>
                  Save account details
                </button>
              </form>
              {!profile.email_verified_at &&
                (emailEnabled ? (
                  <button
                    className="btn-outline"
                    disabled={busy}
                    onClick={() => void action("verify-email", "POST")}
                  >
                    Send verification email
                  </button>
                ) : (
                  <p className="field-help">
                    Email delivery is awaiting setup. In-app tracking remains
                    available.
                  </p>
                ))}
              <Link className="portal-text-link" href="/tracker">
                Open your tracker <Icon name="arrow-right" />
              </Link>
            </section>
            <section className="surface-card">
              <h2>Password & email</h2>
              <p>
                Changing your password signs out all sessions. For a Google-only
                account, use{" "}
                <Link href="/forgot-password">account recovery</Link> to set a
                password once email delivery is available.
              </p>
              <form
                className="account-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (
                    await action("password", "POST", {
                      current_password: password,
                      password: newPassword,
                    })
                  )
                    leaveAccount("/login");
                }}
              >
                <label>
                  Current password
                  <input
                    type="password"
                    autoComplete="current-password"
                    required
                    maxLength={128}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                <label>
                  New password
                  <input
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    maxLength={128}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                </label>
                <button className="btn-primary" disabled={busy}>
                  Change password
                </button>
              </form>
              {emailEnabled && (
                <form
                  className="account-form"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    await action("email", "POST", {
                      email: newEmail,
                      current_password: password,
                    });
                  }}
                >
                  <label>
                    New email address
                    <input
                      type="email"
                      autoComplete="email"
                      required
                      value={newEmail}
                      onChange={(e) => setNewEmail(e.target.value)}
                    />
                  </label>
                  <label>
                    Current password
                    <input
                      type="password"
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </label>
                  <button className="btn-outline" disabled={busy}>
                    Verify a new email address
                  </button>
                </form>
              )}
              <button
                className="btn-outline"
                disabled={busy}
                onClick={async () => {
                  if (await action("logout", "POST")) leaveAccount("/login");
                }}
              >
                Sign out all devices
              </button>
            </section>
            <section className="surface-card">
              <h2>Your data</h2>
              <p>
                Download your application records as a CSV file. Your private
                notes stay in your account until you choose to export or delete
                them.
              </p>
              <Link
                className="btn-primary"
                href="/api/account/export"
                prefetch={false}
                download
              >
                Download applications CSV
              </Link>
              <button
                className="btn-outline"
                disabled={busy}
                onClick={() => void action("profile", "DELETE")}
              >
                Delete previously saved career-profile text
              </button>
            </section>
            <section className="surface-card danger-zone">
              <h2>Delete your account</h2>
              <p>
                This permanently deletes your profile, applications, saved
                searches and their history. Download your records first.
              </p>
              <form
                className="account-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (
                    await action("settings", "DELETE", {
                      current_password: password,
                      confirmation,
                    })
                  )
                    leaveAccount("/");
                }}
              >
                <label>
                  {profile.auth_provider === "google"
                    ? "Password, or sign in with Google again immediately before deleting"
                    : "Current password"}
                  <input
                    type="password"
                    autoComplete="current-password"
                    required={profile.auth_provider !== "google"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                <label>
                  Type DELETE MY ACCOUNT
                  <input
                    required
                    value={confirmation}
                    onChange={(e) => setConfirmation(e.target.value)}
                  />
                </label>
                <button
                  className="btn-outline danger"
                  disabled={busy || confirmation !== "DELETE MY ACCOUNT"}
                >
                  Permanently delete my account
                </button>
              </form>
            </section>
          </>
        ) : (
          <p>
            <Link href="/login">Log in</Link> to manage your account.
          </p>
        )}
      </main>
      <Footer />
    </>
  );
}
