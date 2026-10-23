"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Logo from "@/components/Logo";
import PasswordInput from "@/components/PasswordInput";
import { trackEvent } from "@/lib/analytics";
import { applicationReturnPath } from "@/lib/application-return";

type Mode = "login" | "signup" | "recovery" | "reset" | "verify";
const titles: Record<Mode, string> = {
  login: "Log in to your account",
  signup: "Create your account",
  recovery: "Recover your account",
  reset: "Choose a new password",
  verify: "Verify your email",
};
function errorMessage(data: { detail?: unknown }) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail))
    return data.detail
      .map((d: { msg?: string }) => d.msg)
      .filter(Boolean)
      .join(". ");
  return "Please try again shortly.";
}
export default function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [capabilities, setCapabilities] = useState<{
    google_enabled?: boolean;
    email_enabled?: boolean;
  }>({});
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    confirm_password: "",
    age_confirmed: false,
    accepted_terms: false,
    purpose: "reset",
  });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState("");
  const [nextPath, setNextPath] = useState<string>();
  const [linkRequested, setLinkRequested] = useState(false);
  const [purpose, setPurpose] = useState(mode === "reset" ? "reset" : "verify");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/account/config", { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : {}))
      .then(setCapabilities)
      .catch(() => {});
    queueMicrotask(() => {
      if (controller.signal.aborted) return;
      const params = new URLSearchParams(window.location.search);
      setNextPath(applicationReturnPath(params.get("next")));
      if (params.get("error"))
        setMessage(
          params.get("error") === "google_setup"
            ? "Google sign-in is not configured yet. Use email and password."
            : "Google sign-in could not finish. Please try again or use your password.",
        );
      if (mode === "reset" || mode === "verify") {
        const fragment = new URLSearchParams(window.location.hash.slice(1));
        setToken(fragment.get("token") || "");
        setPurpose(
          fragment.get("purpose") || (mode === "reset" ? "reset" : "verify"),
        );
        // Remove the one-time secret from browser history. It never reaches a server URL.
        if (window.location.hash)
          window.history.replaceState(
            null,
            "",
            window.location.pathname + window.location.search,
          );
      }
    });
    return () => controller.abort();
  }, [mode]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      if (
        (mode === "signup" || mode === "reset") &&
        form.password !== form.confirm_password
      )
        throw new Error("Passwords do not match.");
      const endpoint =
        mode === "reset" || mode === "verify" ? "complete" : mode;
      const body =
        mode === "reset" || mode === "verify"
          ? {
              token,
              purpose,
              ...(mode === "reset" ? { password: form.password } : {}),
            }
          : mode === "signup"
            ? { ...form, country: "GH", next_path: nextPath || "" }
            : mode === "login"
              ? { email: form.email, password: form.password }
              : {
                  email: form.email,
                  purpose: form.purpose,
                  next_path: nextPath || "",
                };
      const response = await fetch(`/api/account/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data));
      setMessage(data.message || "Saved.");
      if (mode === "signup" || mode === "recovery") setLinkRequested(true);
      if (mode === "signup") trackEvent("sign_up", { method: "email" });
      if (mode === "login") {
        trackEvent("login", { method: "email" });
        router.push(nextPath || "/tracker");
        router.refresh();
      }
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const showPassword = ["login", "signup", "reset"].includes(mode);
  const accountLink = (path: string) =>
    nextPath ? `${path}?${new URLSearchParams({ next: nextPath })}` : path;
  return (
    <main id="main-content" className="auth-page">
      <div className="surface-card auth-form-card">
        <Logo />
        <h1>{titles[mode]}</h1>
        {nextPath && (mode === "login" || mode === "signup") && (
          <p className="field-help">
            A free account is required to apply. After logging in, you’ll return
            to your selected listing.
          </p>
        )}
        {(mode === "login" || mode === "signup") &&
          capabilities.google_enabled && (
            <form action="/api/account/google" method="get">
              {nextPath && <input type="hidden" name="next" value={nextPath} />}
              <button type="submit" className="btn-outline google-login">
                Continue with Google
              </button>
            </form>
          )}
        {mode === "recovery" && capabilities.email_enabled === false ? (
          <p>
            Email recovery is awaiting setup. For help accessing your existing
            account, contact{" "}
            <a href="mailto:blesszaglago@gmail.com">blesszaglago@gmail.com</a>.
          </p>
        ) : (
          <form onSubmit={submit} className="account-form">
            {mode === "signup" && (
              <label>
                Full name
                <input
                  name="name"
                  autoComplete="name"
                  required
                  minLength={2}
                  maxLength={100}
                  value={form.full_name}
                  onChange={(e) =>
                    setForm({ ...form, full_name: e.target.value })
                  }
                />
              </label>
            )}
            {["login", "signup", "recovery"].includes(mode) && (
              <label>
                Email address
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  maxLength={254}
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </label>
            )}
            {showPassword && (
              <div className="password-group">
                <label htmlFor="auth-password">
                  {mode === "reset" ? "New password" : "Password"}
                </label>
                <PasswordInput
                  id="auth-password"
                  name="password"
                  visibilityLabel={
                    mode === "reset" ? "new password" : "password"
                  }
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  required
                  minLength={mode === "login" ? 1 : 8}
                  maxLength={128}
                  aria-describedby={
                    mode === "login" ? undefined : "password-hint"
                  }
                  value={form.password}
                  onChange={(e) =>
                    setForm({ ...form, password: e.target.value })
                  }
                />
                {mode !== "login" && (
                  <small id="password-hint">Use at least 8 characters.</small>
                )}
              </div>
            )}
            {(mode === "signup" || mode === "reset") && (
              <div className="password-group">
                <label htmlFor="auth-confirm-password">Confirm password</label>
                <PasswordInput
                  id="auth-confirm-password"
                  name="confirm-password"
                  visibilityLabel="confirm password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  maxLength={128}
                  value={form.confirm_password}
                  onChange={(e) =>
                    setForm({ ...form, confirm_password: e.target.value })
                  }
                />
              </div>
            )}
            {mode === "recovery" && (
              <label>
                I need to
                <select
                  value={form.purpose}
                  onChange={(e) =>
                    setForm({ ...form, purpose: e.target.value })
                  }
                >
                  <option value="reset">Reset my password</option>
                  <option value="verify">Verify my email</option>
                </select>
              </label>
            )}
            {mode === "signup" && (
              <>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    required
                    checked={form.age_confirmed}
                    onChange={(e) =>
                      setForm({ ...form, age_confirmed: e.target.checked })
                    }
                  />
                  I am at least 13 years old.
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    required
                    checked={form.accepted_terms}
                    onChange={(e) =>
                      setForm({ ...form, accepted_terms: e.target.checked })
                    }
                  />
                  I accept the <Link href="/terms">Terms</Link> and{" "}
                  <Link href="/privacy">Privacy Policy</Link>.
                </label>
              </>
            )}
            {(mode === "reset" || mode === "verify") && !token ? (
              <p>
                This link is missing its verification code.{" "}
                <Link href="/forgot-password">Request a fresh link.</Link>
              </p>
            ) : (
              <button className="btn-primary" disabled={busy}>
                {busy
                  ? "Please wait…"
                  : mode === "login"
                    ? "Log in"
                    : mode === "signup"
                      ? "Create account"
                      : mode === "recovery"
                        ? "Send my link"
                        : mode === "reset"
                          ? "Update password"
                          : "Verify email"}
              </button>
            )}
          </form>
        )}
        {message && (
          <p className="form-message" role="status">
            {message}
          </p>
        )}
        {linkRequested && capabilities.email_enabled && (
          <p className="field-help">
            Account emails come from <strong>blesszaglago@gmail.com</strong>.
            Check Spam or Junk too. If you find our email there, mark it as not
            spam and add the sender to your contacts.
          </p>
        )}
        <nav className="auth-links" aria-label="Account options">
          {mode !== "login" && <Link href={accountLink("/login")}>Log in</Link>}
          {mode !== "signup" && (
            <Link href={accountLink("/signup")}>Create account</Link>
          )}
          {(mode === "login" || mode === "signup") && (
            <Link href={accountLink("/forgot-password")}>
              Forgot password or verify email
            </Link>
          )}
          <Link href="/search">Continue searching</Link>
        </nav>
      </div>
    </main>
  );
}
