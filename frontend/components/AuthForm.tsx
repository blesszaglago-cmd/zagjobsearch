"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Logo from "@/components/Logo";
import { trackEvent } from "@/lib/analytics";

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
          window.history.replaceState(null, "", window.location.pathname);
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
            ? { ...form, country: "GH" }
            : mode === "login"
              ? { email: form.email, password: form.password }
              : { email: form.email, purpose: form.purpose };
      const response = await fetch(`/api/account/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(errorMessage(data));
      setMessage(data.message || "Saved.");
      if (mode === "signup") trackEvent("sign_up", { method: "email" });
      if (mode === "login") {
        trackEvent("login", { method: "email" });
        router.push("/tracker");
        router.refresh();
      }
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const showPassword = ["login", "signup", "reset"].includes(mode);
  return (
    <main id="main-content" className="auth-page">
      <div className="surface-card auth-form-card">
        <Logo />
        <h1>{titles[mode]}</h1>
        {(mode === "login" || mode === "signup") &&
          capabilities.google_enabled && (
            <button
              className="btn-outline google-login"
              onClick={() => window.location.assign("/api/account/google")}
            >
              Continue with Google
            </button>
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
              <label>
                {mode === "reset" ? "New password" : "Password"}
                <input
                  name="password"
                  type="password"
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  required
                  minLength={mode === "login" ? 1 : 8}
                  maxLength={128}
                  value={form.password}
                  onChange={(e) =>
                    setForm({ ...form, password: e.target.value })
                  }
                />
              </label>
            )}
            {(mode === "signup" || mode === "reset") && (
              <label>
                Confirm password
                <input
                  name="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  maxLength={128}
                  value={form.confirm_password}
                  onChange={(e) =>
                    setForm({ ...form, confirm_password: e.target.value })
                  }
                />
              </label>
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
        <nav className="auth-links" aria-label="Account options">
          {mode !== "login" && <Link href="/login">Log in</Link>}
          {mode !== "signup" && <Link href="/signup">Create account</Link>}
          {mode === "login" && (
            <Link href="/forgot-password">Forgot password or verify email</Link>
          )}
          <Link href="/search">Continue searching</Link>
        </nav>
      </div>
    </main>
  );
}
