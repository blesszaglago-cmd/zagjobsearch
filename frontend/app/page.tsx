"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Logo from "@/components/Logo";

export default function Home() {
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "dark";
    const saved = localStorage.getItem("theme") as "light" | "dark" | null;
    return saved || "dark";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  };

  return (
    <main className="min-h-screen">
      {/* Nav */}
      <nav
        className="sticky top-0 z-50 border-b"
        style={{
          background: "var(--glass-bg)",
          borderColor: "var(--glass-border)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
        }}
      >
        <div className="max-w-6xl mx-auto px-6 py-3 flex justify-between items-center">
          <Logo />
          <div className="flex gap-3 items-center">
            <button
              onClick={toggleTheme}
              className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
              style={{
                border: "1px solid var(--glass-border)",
                color: "var(--text)",
              }}
              aria-label="Toggle theme"
            >
              {theme === "dark" ? "☀" : "☾"}
            </button>
            <Link
              href="/login"
              className="text-sm px-4 py-2"
              style={{ color: "var(--text-soft)" }}
            >
              Log in
            </Link>
            <Link href="/signup" className="btn-primary text-sm">
              Sign up
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero-gradient text-white">
        <div className="max-w-4xl mx-auto px-6 py-24 text-center">
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-5">
            Find your next role.
          </h1>
          <p className="text-lg md:text-xl opacity-95 mb-10 max-w-2xl mx-auto">
            Search jobs from multiple sources in one place. Apply directly at the source.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 max-w-2xl mx-auto">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Job title or keywords"
              className="flex-1 px-5 py-3 rounded-full text-zinc-900 focus:outline-none"
            />
            <Link
              href={`/search?q=${encodeURIComponent(query)}`}
              className="bg-white text-zinc-900 font-semibold px-8 py-3 rounded-full hover:opacity-90 transition"
            >
              Search
            </Link>
          </div>

          <p className="text-sm opacity-80 mt-4">
            Free forever. No credit card. No spam.
          </p>
        </div>
      </section>

      {/* Popular searches */}
      <section className="max-w-6xl mx-auto px-6 py-10">
        <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>
          Popular searches
        </p>
        <div className="flex flex-wrap gap-2">
          {["software engineer", "data analyst", "product manager", "designer", "marketing", "customer support"].map(
            (term) => (
              <Link
                key={term}
                href={`/search?q=${encodeURIComponent(term)}`}
                className="tag hover:opacity-80 transition"
              >
                {term}
              </Link>
            )
          )}
        </div>
      </section>

      {/* Stats */}
      <section className="max-w-6xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-card p-6 text-center">
            <div className="text-3xl font-bold mb-1" style={{ color: "var(--primary)" }}>
              500K+
            </div>
            <div className="text-sm" style={{ color: "var(--text-muted)" }}>
              Jobs indexed
            </div>
          </div>
          <div className="glass-card p-6 text-center">
            <div className="text-3xl font-bold mb-1" style={{ color: "var(--primary)" }}>
              18
            </div>
            <div className="text-sm" style={{ color: "var(--text-muted)" }}>
              Countries covered
            </div>
          </div>
          <div className="glass-card p-6 text-center">
            <div className="text-3xl font-bold mb-1" style={{ color: "var(--primary)" }}>
              $0
            </div>
            <div className="text-sm" style={{ color: "var(--text-muted)" }}>
              Free forever
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <h2 className="text-3xl font-bold mb-2 text-center">Why ZagJobSearch</h2>
        <p className="text-center mb-12" style={{ color: "var(--text-muted)" }}>
          Built for job seekers everywhere
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-card p-6">
            <h3 className="text-lg font-semibold mb-2">Global coverage</h3>
            <p className="text-sm" style={{ color: "var(--text-soft)" }}>
              Jobs from Adzuna (18 countries) and Himalayas (remote worldwide).
            </p>
          </div>
          <div className="glass-card p-6">
            <h3 className="text-lg font-semibold mb-2">Country-aware</h3>
            <p className="text-sm" style={{ color: "var(--text-soft)" }}>
              Results filtered by your country. Remote jobs available everywhere.
            </p>
          </div>
          <div className="glass-card p-6">
            <h3 className="text-lg font-semibold mb-2">Apply at the source</h3>
            <p className="text-sm" style={{ color: "var(--text-soft)" }}>
              We send you straight to the original job posting. No middleman.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-16 py-8 border-t" style={{ borderColor: "var(--glass-border)" }}>
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            © {new Date().getFullYear()} ZagJobSearch. Built by Bless Zaglago.
          </p>
          <div className="flex gap-6 text-sm" style={{ color: "var(--text-muted)" }}>
            <Link href="/privacy" className="hover:opacity-80">
              Privacy
            </Link>
            <Link href="/terms" className="hover:opacity-80">
              Terms
            </Link>
            <Link href="/cookies" className="hover:opacity-80">
              Cookies
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}