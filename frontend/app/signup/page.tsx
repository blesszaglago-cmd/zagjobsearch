"use client";

import { countries } from "@/lib/countries";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import Logo from "@/components/Logo";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    confirm_password: "",
    date_of_birth: "",
    country: "GH",
    accepted_terms: false,
  });

  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? (e.target as HTMLInputElement).checked : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("loading");
    setMessage("");

    try {
      const res = await fetch("/api/account/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      const data = await res.json();

      if (!res.ok) {
        setStatus("error");
        setMessage(data.detail?.[0]?.msg || data.detail || "Signup failed.");
        return;
      }

      setStatus("success");
      setMessage("Account created. Redirecting to login...");
      setTimeout(() => {
        router.push("/login");
      }, 1500);
    } catch {
      setStatus("error");
      setMessage("Something went wrong. Try again.");
    }
  };

  const inputStyle = {
    width: "100%",
    background: "var(--input-bg)",
    border: "1px solid var(--input-border)",
    borderRadius: "12px",
    padding: "10px 14px",
    color: "var(--input-text)",
    outline: "none",
  };

  const labelStyle = {
    display: "block",
    fontSize: "0.85rem",
    marginBottom: "6px",
    color: "var(--text-soft)",
  };

  return (
    <main id="main-content" className="auth-page min-h-screen flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <Logo />
        </div>

        <div className="surface-card p-8">
          <h1 className="text-2xl font-bold mb-6">Create your account</h1>

          <Link prefetch={false} href="/api/account/google" className="btn-outline google-login">Continue with Google</Link>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="full_name" style={labelStyle}>Full name</label>
              <input id="full_name" name="full_name" type="text" value={form.full_name} onChange={handleChange} required style={inputStyle} />
            </div>

            <div>
              <label htmlFor="email" style={labelStyle}>Email</label>
              <input id="email" name="email" type="email" value={form.email} onChange={handleChange} required style={inputStyle} />
            </div>

            <div>
              <label htmlFor="password" style={labelStyle}>Password</label>
              <input id="password" name="password" type="password" value={form.password} onChange={handleChange} required minLength={8} style={inputStyle} />
            </div>

            <div>
              <label htmlFor="confirm_password" style={labelStyle}>Confirm password</label>
              <input id="confirm_password" name="confirm_password" type="password" value={form.confirm_password} onChange={handleChange} required style={inputStyle} />
            </div>

            <div>
              <label htmlFor="date_of_birth" style={labelStyle}>Date of birth</label>
              <input id="date_of_birth" name="date_of_birth" type="date" value={form.date_of_birth} onChange={handleChange} required style={inputStyle} />
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>You must be 13 or older.</p>
            </div>

            <div>
              <label htmlFor="country" style={labelStyle}>Country</label>
              <select id="country" name="country" value={form.country} onChange={handleChange} style={inputStyle}>
                {countries.map(([code,name])=><option key={code} value={code.toUpperCase()}>{name}</option>)}
              </select>
            </div>

            <label className="flex items-start gap-2 text-sm" style={{ color: "var(--text-soft)" }}>
              <input name="accepted_terms" type="checkbox" checked={form.accepted_terms} onChange={handleChange} className="mt-1" />
              <span>
                I agree to the{" "}
                <Link href="/terms" style={{ color: "var(--primary)" }}>Terms</Link>{" "}
                and{" "}
                <Link href="/privacy" style={{ color: "var(--primary)" }}>Privacy Policy</Link>.
              </span>
            </label>

            <button type="submit" disabled={status === "loading"} className="btn-primary w-full">
              {status === "loading" ? "Creating account..." : "Create account"}
            </button>
          </form>

          {message && (
            <p className="mt-4 text-sm" style={{ color: status === "success" ? "var(--secondary)" : "#ff6b6b" }}>
              {message}
            </p>
          )}

          <p className="text-sm mt-6 text-center" style={{ color: "var(--text-muted)" }}>
            Already have an account?{" "}
            <Link href="/login" style={{ color: "var(--primary)" }}>Log in</Link>
          </p>
        </div>
      </div>
    </main>
  );
}