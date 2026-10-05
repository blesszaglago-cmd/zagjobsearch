"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { API_URL } from "../../lib/api";
import Logo from "@/components/Logo";

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "" });
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("loading");
    setMessage("");

    try {
      const res = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      const data = await res.json();

      if (!res.ok) {
        setStatus("error");
        setMessage(data.detail || "Login failed.");
        return;
      }

      setStatus("success");
      setMessage(`Welcome back, ${data.full_name}. Redirecting...`);

      localStorage.setItem(
        "user",
        JSON.stringify({
          user_id: data.user_id,
          email: data.email,
          full_name: data.full_name,
          country: data.country,
        })
      );

      setTimeout(() => {
        const pending = sessionStorage.getItem("zagjobsearch-pending-application");
        sessionStorage.removeItem("zagjobsearch-pending-application");
        if (pending && /^https?:\/\//i.test(pending)) window.location.assign(pending);
        else router.push("/search");
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
          <h1 className="text-2xl font-bold mb-6">Log in to your account</h1>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" style={labelStyle}>Email</label>
              <input id="email" name="email" type="email" value={form.email} onChange={handleChange} required style={inputStyle} />
            </div>

            <div>
              <label htmlFor="password" style={labelStyle}>Password</label>
              <input id="password" name="password" type="password" value={form.password} onChange={handleChange} required style={inputStyle} />
            </div>

            <button type="submit" disabled={status === "loading"} className="btn-primary w-full">
              {status === "loading" ? "Logging in..." : "Log in"}
            </button>
          </form>

          {message && (
            <p className="mt-4 text-sm" style={{ color: status === "success" ? "var(--secondary)" : "#ff6b6b" }}>
              {message}
            </p>
          )}

          <p className="text-sm mt-6 text-center" style={{ color: "var(--text-muted)" }}>
            Don&apos;t have an account?{" "}
            <Link href="/signup" style={{ color: "var(--primary)" }}>Sign up</Link>
          </p>
        </div>
      </div>
    </main>
  );
}