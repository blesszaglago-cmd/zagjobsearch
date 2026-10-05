"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import {countries} from "@/lib/countries";
import {Job,listingTypes} from "@/lib/jobs";
import Link from "next/link";

function SearchContent() {
  const params = useSearchParams();
  const router = useRouter();
  const q = params.get("q") || "";
  const selectedCountry = params.get("country") || "gh";
  const remoteOnly = params.get("remote") === "true";
  const page = Math.max(1, Math.min(10, Number(params.get("page")) || 1));
  const [query, setQuery] = useState(q);
  const [country, setCountry] = useState(selectedCountry);
  const [jobType,setJobType]=useState(params.get("job_type")||"all"),[experience,setExperience]=useState(params.get("experience")||""),[industry,setIndustry]=useState(params.get("industry")||""),[salary,setSalary]=useState(params.get("salary_min")||""),[currency,setCurrency]=useState(params.get("currency")||"USD"),[period,setPeriod]=useState(params.get("salary_period")||"annual");
  const activeType=params.get("job_type")||"all";
  const filterString=params.toString();
  const [remote, setRemote] = useState(remoteOnly);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    async function search() {
      setLoading(true); setError(""); setWarning("");
      try {
        const response=await fetch(`/api/jobs?${filterString}`,{signal:controller.signal});
        const data=await response.json();
        if(controller.signal.aborted)return;
        setJobs(data.jobs||[]);
        if(data.errors?.length)setWarning(`Some sources are unavailable: ${data.errors.join(', ')}. Showing available listings.`);
      }catch{if(!controller.signal.aborted)setError('Search is temporarily unavailable. Please try again.');}
      setLoading(false);
    }
    void search();
    return () => controller.abort();
  }, [filterString]);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    router.push(`/search?${new URLSearchParams({ q: query.trim(), country, remote: String(remote),job_type:jobType,experience,industry,salary_min:salary,currency,salary_period:period })}`);
  }
  function detailLink(job:Job){return `/jobs/${encodeURIComponent(job.id)}?${params.toString()}`;}
  function pageLink(next:number){const nextParams=new URLSearchParams(params.toString());nextParams.set('page',String(next));return `/search?${nextParams}`;}
  return <><Header /><main id="main-content" className="shell">
    <section className="search-banner"><span className="eyebrow">A LITTLE CLOSER TO YOUR NEXT CHAPTER</span><h1>Find a role that fits you.</h1><p>Search available jobs. Check the details. Apply on the original website.</p></section>
    <nav className="listing-tabs" aria-label="Listing types">{listingTypes.map(([value,label])=><button key={value} aria-pressed={activeType===value} onClick={()=>{setJobType(value);const next=new URLSearchParams(params.toString());next.set('job_type',value);next.delete('page');router.push(`/search?${next}`)}}>{label}</button>)}</nav>
    <form onSubmit={submit} className="search-layout">
      <aside className="filter-sidebar"><h2>Refine your search</h2><label className="field-label" htmlFor="country">Your country</label><select id="country" value={country} onChange={e => setCountry(e.target.value)}>{countries.map(([code, name]) => <option value={code} key={code}>{name}</option>)}</select><label className="checkbox-label remote-filter"><input type="checkbox" checked={remote} onChange={e => setRemote(e.target.checked)} />Remote jobs only</label><label className="field-label" htmlFor="experience">Experience</label><select id="experience" value={experience} onChange={e=>setExperience(e.target.value)}><option value="">All levels</option><option value="entry">Entry level</option><option value="mid">Mid level</option><option value="senior">Senior</option><option value="manager">Management</option></select><label className="field-label" htmlFor="industry">Industry or field</label><input id="industry" value={industry} onChange={e=>setIndustry(e.target.value)} placeholder="Any industry"/><label className="field-label" htmlFor="salary">Minimum salary</label><input id="salary" type="number" min="0" value={salary} onChange={e=>setSalary(e.target.value)}/><label className="field-label" htmlFor="currency">Currency</label><input id="currency" value={currency} onChange={e=>setCurrency(e.target.value.toUpperCase())} maxLength={3}/><label className="field-label" htmlFor="period">Salary period</label><select id="period" value={period} onChange={e=>setPeriod(e.target.value)}>{['annual','yearly','monthly','weekly','hourly'].map(p=><option key={p}>{p}</option>)}</select><button className="btn-primary" type="submit" disabled={loading}>Update results</button><p className="filter-note">Remote roles may have location restrictions. Always check your eligibility on the posting.</p></aside>
      <section className="results-panel" aria-busy={loading}><div className="results-search"><label className="sr-only" htmlFor="keywords">Job title or keywords</label><input id="keywords" value={query} onChange={e => setQuery(e.target.value)} placeholder="Job title or keywords" maxLength={200} /><button type="submit" className="btn-primary" disabled={loading}>Search ↗</button></div>
        <div role="status" aria-live="polite" className="results-count">{loading ? "Searching job sources…" : `${jobs.length} results on page ${page}`}</div>
        {warning && <p className="source-warning">{warning}</p>}{error && <p role="alert" className="search-error">{error}</p>}
        {!loading && jobs.map(job => <article key={`${job.source}:${job.id}`} className="job-row"><div className="job-mark" aria-hidden="true">{(job.company || "J").slice(0, 1)}</div><div className="job-main"><h2><Link href={detailLink(job)}>{job.title}</Link></h2><p className="job-company">{job.company || "Company not supplied"} · {job.location || "Location not supplied"}</p><p className="job-description">{job.description.slice(0,300)}</p><div className="job-tags"><span className="tag">{job.source === "jobicy" ? <a href="https://jobicy.com" target="_blank" rel="noopener noreferrer">Jobicy</a> : job.source}</span>{job.remote && <span className="tag mint">Remote</span>}{job.salary_min != null && <span className="tag">{job.salary_currency || ""} {Number(job.salary_min).toLocaleString()}{job.salary_max != null ? ` – ${Number(job.salary_max).toLocaleString()}` : "+"}{job.salary_period ? ` / ${job.salary_period}` : ""}</span>}</div></div><div className="job-actions"><Link href={detailLink(job)} className="btn-primary">View role ↗</Link><small>Details and application link</small></div></article>)}
        {!loading && !error && jobs.length === 0 && <div className="empty-state"><span aria-hidden="true">⌕</span><h2>{q ? "Let’s try a different search." : "What would you like to do next?"}</h2><p>{q ? "Try a broader job title or another country. Coverage depends on the available sources." : "Enter a role or skill to discover real jobs."}</p></div>}
        {!loading && <div className="pagination"><button type="button" className="btn-outline" disabled={page === 1} onClick={() => router.push(pageLink(page-1))}>Previous</button><span>Page {page}</span><button type="button" className="btn-outline" disabled={page >= 10 || jobs.length === 0} onClick={() => router.push(pageLink(page+1))}>Next</button></div>}
      </section>
    </form>
  </main><Footer /></>;
}
export default function SearchPage() { return <Suspense fallback={<p className="empty-state">Loading search…</p>}><SearchContent /></Suspense>; }
