"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import type { Job } from "@/lib/jobs";
import {
  categories,
  regions,
  types,
  experienceLevels,
  studyLevels,
  displayDate,
} from "@/lib/ghana";
function SearchContent() {
  const params = useSearchParams(),
    router = useRouter(),
    filterString = params.toString();
  const raw = params.get("category") || "jobs",
    category = categories.some(([key]) => key === raw) ? raw : "jobs";
  const [jobs, setJobs] = useState<Job[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [total, setTotal] = useState(0),
    [more, setMore] = useState(false),
    [updated, setUpdated] = useState<string | null>(null),
    [warning, setWarning] = useState(false);
  const page = Math.max(1, Number(params.get("page")) || 1);
  useEffect(() => {
    const c = new AbortController();
    fetch(
      `/api/jobs?${new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(filterString)), category })}`,
      { signal: c.signal },
    )
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw Error(d.detail || "Search unavailable.");
        if (!c.signal.aborted) {
          setJobs(d.jobs || []);
          setTotal(d.total || 0);
          setMore(Boolean(d.has_more));
          setUpdated(d.updated_at);
          setWarning(
            (d.source_status || []).some(
              (s: { state: string }) => s.state !== "ok",
            ),
          );
          setError("");
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!c.signal.aborted) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => c.abort();
  }, [filterString, category]);
  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget),
      next = new URLSearchParams();
    data.forEach((v, k) => {
      if (String(v)) next.set(k, String(v));
    });
    setLoading(true);
    router.push(`/search?${next}`);
  }
  function switchCategory(value: string) {
    setLoading(true);
    setJobs([]);
    router.push(`/search?category=${value}`);
  }
  function paginate(n: number) {
    const next = new URLSearchParams(filterString);
    next.set("page", String(n));
    setLoading(true);
    router.push(`/search?${next}`);
  }
  const scholarship = category === "scholarships";
  return (
    <>
      <Header />
      <main id="main-content" className="shell gh-search">
        <section className="search-banner gh-banner">
          <p className="eyebrow">OPPORTUNITIES FOR GHANA</p>
          <h1>
            {scholarship
              ? "Invest in your next qualification."
              : category === "early"
                ? "Your first experience starts here."
                : category === "remote"
                  ? "Remote roles. Ghana eligible."
                  : "Find your next role in Ghana."}
          </h1>
          <p>
            {scholarship
              ? "Browse Scholsec’s published scholarships and notices. Open awards, unconfirmed deadlines and the closed archive stay separate."
              : "Search source-linked vacancies. Check the details. Apply directly at the original source."}
          </p>
        </section>
        <nav className="gh-tabs" aria-label="Opportunity categories">
          {categories.map(([v, label]) => (
            <button
              type="button"
              key={v}
              aria-pressed={category === v}
              onClick={() => switchCategory(v)}
            >
              {label}
            </button>
          ))}
        </nav>
        <form
          key={category + "|" + filterString}
          onSubmit={submit}
          className="search-layout"
        >
          <input type="hidden" name="category" value={category} />
          <aside className="filter-sidebar">
            <h2>
              {scholarship
                ? "Scholarship filters"
                : category === "early"
                  ? "Early career filters"
                  : "Job filters"}
            </h2>
            {scholarship ? (
              <>
                <label className="field-label" htmlFor="availability">
                  Scholarship status
                </label>
                <select
                  id="availability"
                  name="availability"
                  defaultValue={params.get("availability") || "open"}
                >
                  <option value="open">Open for applications</option>
                  <option value="unconfirmed">Deadline unconfirmed</option>
                  <option value="closed">Closed archive</option>
                  <option value="all">All Scholsec notices</option>
                </select>
                <label className="field-label" htmlFor="study">
                  Study level
                </label>
                <select
                  id="study"
                  name="study_level"
                  defaultValue={params.get("study_level") || ""}
                >
                  <option value="">All study levels</option>
                  {studyLevels.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
                <label className="field-label" htmlFor="destination">
                  Study destination
                </label>
                <select
                  id="destination"
                  name="destination"
                  defaultValue={params.get("destination") || ""}
                >
                  <option value="">Ghana and abroad</option>
                  <option value="ghana">Study in Ghana</option>
                  <option value="abroad">
                    Study abroad, Ghanaian eligible
                  </option>
                </select>
                <label className="field-label" htmlFor="funding">
                  Funding
                </label>
                <select
                  id="funding"
                  name="funding"
                  defaultValue={params.get("funding") || ""}
                >
                  <option value="">All funding</option>
                  <option value="full">Fully funded</option>
                  <option value="partial">Partially funded</option>
                </select>
              </>
            ) : (
              <>
                <label className="field-label" htmlFor="type">
                  {category === "early" ? "Programme type" : "Employment type"}
                </label>
                <select
                  id="type"
                  name="job_type"
                  defaultValue={params.get("job_type") || "all"}
                >
                  {(types[category] || types.jobs).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
                {category !== "remote" ? (
                  <>
                    <label className="field-label" htmlFor="region">
                      Region
                    </label>
                    <select
                      id="region"
                      name="region"
                      defaultValue={params.get("region") || ""}
                    >
                      <option value="">Across Ghana</option>
                      {regions.map((r) => (
                        <option key={r}>{r}</option>
                      ))}
                    </select>
                    <label className="field-label" htmlFor="town">
                      Town or city
                    </label>
                    <input
                      id="town"
                      name="town"
                      defaultValue={params.get("town") || ""}
                      placeholder="Accra, Tamale, Ho…"
                    />
                  </>
                ) : null}
                <label className="field-label" htmlFor="experience">
                  Experience level
                </label>
                <select
                  id="experience"
                  name="experience"
                  defaultValue={params.get("experience") || ""}
                >
                  <option value="">All levels</option>
                  {experienceLevels.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </>
            )}
            <label className="field-label" htmlFor="industry">
              {scholarship ? "Subject or field" : "Industry or field"}
            </label>
            <input
              id="industry"
              name="industry"
              defaultValue={params.get("industry") || ""}
              placeholder={
                scholarship ? "Engineering, education…" : "Finance, healthcare…"
              }
            />
            <button className="btn-primary" type="submit">
              Apply filters
            </button>
            <Link className="text-action" href={`/search?category=${category}`}>
              Clear filters
            </Link>
            <p className="filter-note">
              Filters use information supplied by the source. Unspecified
              details are never guessed.
            </p>
          </aside>
          <section className="results-panel" aria-busy={loading}>
            <div className="results-search">
              <label className="sr-only" htmlFor="keywords">
                Keywords
              </label>
              <input
                id="keywords"
                name="q"
                defaultValue={params.get("q") || ""}
                placeholder={
                  scholarship
                    ? "Scholarship, provider or subject"
                    : "Job title, employer or skill"
                }
                maxLength={200}
              />
              <button className="btn-primary" type="submit">
                Search ↗
              </button>
            </div>
            <div
              className="gh-subsections"
              aria-label={scholarship ? "Study levels" : "Listing subsections"}
            >
              {(scholarship ? studyLevels : types[category] || types.jobs).map(
                ([v, l]) => {
                  const next = new URLSearchParams({
                    category,
                    [scholarship ? "study_level" : "job_type"]: v,
                  });
                  return (
                    <Link key={v} href={`/search?${next}`}>
                      {l}
                    </Link>
                  );
                },
              )}
            </div>
            <p role="status" className="results-count">
              {loading
                ? "Loading the Ghana catalogue…"
                : `${total} ${scholarship ? "scholarship notices" : "current opportunities"} · Page ${page}`}
            </p>
            {updated ? (
              <p className="filter-note">
                Last refresh {displayDate(updated)}. Rechecked automatically
                each day.
              </p>
            ) : null}
            {warning ? (
              <p className="source-warning">
                Some sources could not be checked. Only recently checked
                listings are shown.
              </p>
            ) : null}
            {error ? (
              <p role="alert" className="search-error">
                {error}
              </p>
            ) : null}
            {!loading && !error
              ? jobs.map((job) => (
                  <article className="job-row" key={job.id}>
                    <div className="job-mark" aria-hidden="true">
                      {job.company.slice(0, 1)}
                    </div>
                    <div className="job-main">
                      <p className="gh-source">{job.company}</p>
                      <h2>
                        <Link href={`/jobs/${job.id}`}>{job.title}</Link>
                      </h2>
                      <p className="job-company">{job.location}</p>
                      <p className="job-description">
                        {job.description.slice(0, 200)}…
                      </p>
                      <div className="job-tags">
                        {scholarship && (
                          <span
                            className={`tag scholarship-status ${job.listing_status}`}
                          >
                            {job.listing_status === "open"
                              ? "Open for applications"
                              : job.listing_status === "closed"
                                ? "Closed · archive"
                                : "Deadline unconfirmed"}
                          </span>
                        )}
                        <span className="tag mint">
                          {scholarship
                            ? job.study_levels
                                ?.map(
                                  (l) =>
                                    studyLevels.find(([v]) => v === l)?.[1] ||
                                    l,
                                )
                                .join(", ") || "Study level not specified"
                            : job.job_type === "unspecified"
                              ? "Type not specified"
                              : job.job_type}
                        </span>
                        {!scholarship ? (
                          <span className="tag">
                            {experienceLevels.find(
                              ([v]) => v === job.experience,
                            )?.[1] || "Level not specified"}
                          </span>
                        ) : null}
                      </div>
                      <p className="listing-dates">
                        {job.created
                          ? `${job.date_kind === "source_updated" ? "Source updated" : "Posted"} ${displayDate(job.created)} · `
                          : ""}
                        Deadline: {displayDate(job.deadline)}
                        <br />
                        Source checked: {displayDate(job.checked_at)}
                      </p>
                    </div>
                    <div className="job-actions">
                      <Link href={`/jobs/${job.id}`} className="btn-primary">
                        View details ↗
                      </Link>
                      <small>
                        {scholarship && job.listing_status !== "open"
                          ? "Read the official notice"
                          : "Apply at the original source"}
                      </small>
                    </div>
                  </article>
                ))
              : null}
            {!loading && !error && jobs.length === 0 ? (
              <div className="empty-state">
                <h2>No current matches.</h2>
                <p>
                  {scholarship
                    ? "Try fewer filters or choose All Scholsec notices to include the closed archive and notices without a confirmed deadline."
                    : "Try fewer filters. We do not substitute unrelated countries or expired listings. Coverage is growing as more sources pass our checks."}
                </p>
                <Link
                  href={`/search?category=${category}`}
                  className="btn-outline"
                >
                  Reset this category
                </Link>
              </div>
            ) : null}
            {!loading && !error ? (
              <div className="pagination">
                <button
                  type="button"
                  className="btn-outline"
                  disabled={page === 1}
                  onClick={() => paginate(page - 1)}
                >
                  Previous
                </button>
                <span>Page {page}</span>
                <button
                  type="button"
                  className="btn-outline"
                  disabled={!more}
                  onClick={() => paginate(page + 1)}
                >
                  Next
                </button>
              </div>
            ) : null}
          </section>
        </form>
      </main>
      <Footer />
    </>
  );
}
export default function Page() {
  return (
    <Suspense
      fallback={<p className="empty-state">Loading Ghana opportunities…</p>}
    >
      <SearchContent />
    </Suspense>
  );
}
