"use client";

import Logo from "@/components/Logo";
import { useEffect, useState, Suspense, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { API_URL } from "../../lib/api";

type Job = {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  description: string;
  url: string;
  created: string | number | null;
  salary_min: number | null;
  salary_max: number | null;
  source: string;
  remote?: boolean;
};

function SearchContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";

  const [query, setQuery] = useState(initialQuery);
  const [country, setCountry] = useState("gh");
  const [remote, setRemote] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  const hasAutoSearched = useRef(false);

  const runSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setSearched(true);

    try {
      const params = new URLSearchParams({
        q: query,
        country: country,
        page: "1",
        remote: String(remote),
      });

      const res = await fetch(`${API_URL}/search?${params.toString()}`);
      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Search failed.");
        setJobs([]);
        return;
      }

      setJobs(data.jobs || []);
    } catch {
      setError("Something went wrong. Try again.");
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [query, country, remote]);

  // Auto-search only once when the page loads with a query
  useEffect(() => {
    if (initialQuery && !hasAutoSearched.current) {
      hasAutoSearched.current = true;
      runSearch();
    }
  }, [initialQuery, runSearch]);

  const inputStyle = {
    width: "100%",
    background: "var(--input-bg)",
    border: "1px solid var(--input-border)",
    borderRadius: "12px",
    padding: "10px 14px",
    color: "var(--input-text)",
    outline: "none",
  };

  return (
    <main className="min-h-screen">
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
          <div className="flex justify-center mb-8">
            <Logo />
          </div>
          <div className="flex gap-3 items-center">
            <Link href="/login" className="text-sm px-4 py-2" style={{ color: "var(--text-soft)" }}>
              Log in
            </Link>
            <Link href="/signup" className="btn-primary text-sm">
              Sign up
            </Link>
          </div>
        </div>
      </nav>

      <section className="max-w-6xl mx-auto px-6 py-8">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            runSearch();
          }}
          className="flex flex-col gap-4"
        >
          <div className="flex flex-col md:flex-row gap-3">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Job title or keywords"
              style={{ ...inputStyle, flex: 1 }}
            />

            <select value={country} onChange={(e) => setCountry(e.target.value)} style={inputStyle}>
              <option value="gh">Ghana</option>
              <option value="ng">Nigeria</option>
              <option value="ke">Kenya</option>
              <option value="za">South Africa</option>
              <option value="us">United States</option>
              <option value="gb">United Kingdom</option>
              <option value="ca">Canada</option>
              <option value="de">Germany</option>
              <option value="fr">France</option>
              <option value="in">India</option>
              <option value="au">Australia</option>
            </select>

            <button type="submit" disabled={loading} className="btn-primary">
              {loading ? "Searching..." : "Search"}
            </button>
          </div>

          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--text-soft)" }}>
            <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} />
            Only remote jobs
          </label>
        </form>
      </section>

      <section className="max-w-6xl mx-auto px-6 pb-16">
        {error && (
          <div className="glass-card p-4 mb-4" style={{ borderColor: "#ff6b6b", color: "#ff6b6b" }}>
            {error}
          </div>
        )}

        {loading && (
          <p className="text-center py-12" style={{ color: "var(--text-muted)" }}>
            Loading jobs...
          </p>
        )}

        {!loading && searched && jobs.length === 0 && !error && (
          <p className="text-center py-12" style={{ color: "var(--text-muted)" }}>
            No jobs found. Try a different keyword or country.
          </p>
        )}

        {!loading && jobs.length > 0 && (
          <>
            <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>
              {jobs.length} jobs found
            </p>
            <div className="space-y-4">
              {jobs.map((job) => (
                <div key={job.id} className="glass-card p-6">
                  <div className="flex justify-between items-start gap-4 flex-wrap">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold">{job.title}</h3>
                      <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                        {job.company || "Unknown company"}
                        {job.location && ` · ${job.location}`}
                      </p>
                      {job.description && (
                        <p className="text-sm mt-3 line-clamp-2" style={{ color: "var(--text-soft)" }}>
                          {job.description}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-2 mt-3">
                        <span className="tag">{job.source}</span>
                        {job.remote && <span className="tag">Remote</span>}
                        {job.salary_min && job.salary_max && (
                          <span className="tag">
                            {Math.round(job.salary_min).toLocaleString()} – {Math.round(job.salary_max).toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>

                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-primary text-sm whitespace-nowrap"
                    >
                      Apply
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {!searched && (
          <p className="text-center py-16" style={{ color: "var(--text-muted)" }}>
            Search for jobs to get started.
          </p>
        )}
      </section>
    </main>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="text-center py-12" style={{ color: "var(--text-muted)" }}>Loading...</p>}>
      <SearchContent />
    </Suspense>
  );
}