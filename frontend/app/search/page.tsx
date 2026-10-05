"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { API_URL } from "@/lib/api";

type Job = { id: string; title: string; company: string | null; location: string | null; description: string; url: string; salary_min?: number | null; salary_max?: number | null; salary_currency?: string | null; salary_period?: string | null; source: string; remote?: boolean };
const countries = [["gh", "Ghana"], ["ng", "Nigeria"], ["ke", "Kenya"], ["za", "South Africa"], ["us", "United States"], ["gb", "United Kingdom"], ["ca", "Canada"], ["de", "Germany"], ["fr", "France"], ["in", "India"], ["au", "Australia"]];
function SearchContent() {
  const params = useSearchParams();
  const router = useRouter();
  const q = params.get("q") || "";
  const selectedCountry = params.get("country") || "gh";
  const remoteOnly = params.get("remote") === "true";
  const page = Math.max(1, Math.min(10, Number(params.get("page")) || 1));
  const [query, setQuery] = useState(q);
  const [country, setCountry] = useState(selectedCountry);
  const [remote, setRemote] = useState(remoteOnly);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(Boolean(q));
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  useEffect(() => {
    if (!q.trim()) return;
    const controller = new AbortController();
    async function search() {
      setLoading(true); setError(""); setWarning("");
      const search = new URLSearchParams({ q, country: selectedCountry, remote: String(remoteOnly), page: String(page) });
      const sources = await Promise.allSettled([
        fetch(`${API_URL}/search?${search}`, { signal: controller.signal }).then(async r => { if (!r.ok) throw new Error("Search unavailable"); return r.json(); }),
        fetch(`/api/jobicy?${search}`, { signal: controller.signal }).then(async r => { if (!r.ok) throw new Error("Jobicy unavailable"); return r.json(); }),
      ]);
      if (controller.signal.aborted) return;
      const found: Job[] = []; let failures = 0;
      for (const result of sources) {
        if (result.status === "fulfilled") { found.push(...(result.value.jobs || [])); if (result.value.errors?.length) failures++; }
        else failures++;
      }
      const seen = new Set<string>();
      setJobs(found.filter(job => {
        if (!/^https?:\/\//i.test(job.url || "")) return false;
        const key = `${job.company?.toLowerCase()}|${job.title?.toLowerCase()}|${job.location?.toLowerCase()}`;
        if (seen.has(key)) return false; seen.add(key); return true;
      }));
      if (failures === sources.length && found.length === 0) setError("Job sources are unavailable right now. Please try again shortly.");
      else if (failures) setWarning("Some job sources could not respond. These are the available results.");
      setLoading(false);
    }
    void search();
    return () => controller.abort();
  }, [q, selectedCountry, remoteOnly, page]);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    router.push(`/search?${new URLSearchParams({ q: query.trim(), country, remote: String(remote) })}`);
  }
  function apply(job: Job) {
    // The existing login stores profile data locally. This is a UX gate, not server authentication.
    if (!localStorage.getItem("user")) {
      sessionStorage.setItem("zagjobsearch-pending-application", job.url);
      router.push("/login?apply=1");
      return;
    }
    window.open(job.url, "_blank", "noopener,noreferrer");
  }
  return <><Header /><main id="main-content" className="shell">
    <section className="search-banner"><span className="eyebrow">A LITTLE CLOSER TO YOUR NEXT CHAPTER</span><h1>Find a role that fits you.</h1><p>Search available jobs. Check the details. Apply on the original website.</p></section>
    <form onSubmit={submit} className="search-layout">
      <aside className="filter-sidebar"><h2>Refine your search</h2><label className="field-label" htmlFor="country">Your country</label><select id="country" value={country} onChange={e => setCountry(e.target.value)}>{countries.map(([code, name]) => <option value={code} key={code}>{name}</option>)}</select><label className="checkbox-label remote-filter"><input type="checkbox" checked={remote} onChange={e => setRemote(e.target.checked)} />Remote jobs only</label><button className="btn-primary" type="submit" disabled={loading}>Update results</button><p className="filter-note">Remote roles may have location restrictions. Always check your eligibility on the posting.</p></aside>
      <section className="results-panel" aria-busy={loading}><div className="results-search"><label className="sr-only" htmlFor="keywords">Job title or keywords</label><input id="keywords" value={query} onChange={e => setQuery(e.target.value)} placeholder="Job title or keywords" required maxLength={200} /><button type="submit" className="btn-primary" disabled={loading}>Search ↗</button></div>
        <div role="status" aria-live="polite" className="results-count">{loading ? "Searching job sources…" : q ? `${jobs.length} results on page ${page}` : "Your next opportunity starts with a search."}</div>
        {warning && <p className="source-warning">{warning}</p>}{error && <p role="alert" className="search-error">{error}</p>}
        {!loading && jobs.map(job => <article key={`${job.source}:${job.id}`} className="job-row"><div className="job-mark" aria-hidden="true">{(job.company || "J").slice(0, 1)}</div><div className="job-main"><h2>{job.title}</h2><p className="job-company">{job.company || "Company not supplied"} · {job.location || "Location not supplied"}</p><p className="job-description">{job.description}</p><div className="job-tags"><span className="tag">{job.source === "jobicy" ? <a href="https://jobicy.com" target="_blank" rel="noopener noreferrer">Jobicy</a> : job.source}</span>{job.remote && <span className="tag mint">Remote</span>}{job.salary_min != null && <span className="tag">{job.salary_currency || ""} {Number(job.salary_min).toLocaleString()}{job.salary_max != null ? ` – ${Number(job.salary_max).toLocaleString()}` : "+"}{job.salary_period ? ` / ${job.salary_period}` : ""}</span>}</div></div><div className="job-actions"><button type="button" onClick={() => apply(job)} className="btn-primary">Apply ↗</button><small>Opens the source</small></div></article>)}
        {!loading && !error && jobs.length === 0 && <div className="empty-state"><span aria-hidden="true">⌕</span><h2>{q ? "Let’s try a different search." : "What would you like to do next?"}</h2><p>{q ? "Try a broader job title or another country. Coverage depends on the available sources." : "Enter a role or skill to discover real jobs."}</p></div>}
        {!loading && q && <div className="pagination"><button type="button" className="btn-outline" disabled={page === 1} onClick={() => router.push(`/search?${new URLSearchParams({ q, country: selectedCountry, remote: String(remoteOnly), page: String(page - 1) })}`)}>Previous</button><span>Page {page}</span><button type="button" className="btn-outline" disabled={page >= 10 || jobs.length === 0} onClick={() => router.push(`/search?${new URLSearchParams({ q, country: selectedCountry, remote: String(remoteOnly), page: String(page + 1) })}`)}>Next</button></div>}
      </section>
    </form>
  </main><Footer /></>;
}
export default function SearchPage() { return <Suspense fallback={<p className="empty-state">Loading search…</p>}><SearchContent /></Suspense>; }
