"use client";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Job } from "@/lib/jobs";
import { displayDate } from "@/lib/ghana";
import { accountRequest, blankApplication } from "@/lib/workspace";
export default function Details() {
  const { id } = useParams<{ id: string }>(),
    params = useSearchParams();
  const [job, setJob] = useState<Job | null>(null),
    [message, setMessage] = useState(""),
    [signedIn, setSignedIn] = useState(false),
    [busy, setBusy] = useState(false),
    [recordId, setRecordId] = useState("");
  const query = params.toString();
  useEffect(() => {
    const c = new AbortController();
    fetch(`/api/jobs/${encodeURIComponent(id)}?${query}`, { signal: c.signal })
      .then(async (r) => {
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail);
        if (!c.signal.aborted) setJob(d);
      })
      .catch((e) => {
        if (!c.signal.aborted) setMessage(e.message);
      });
    accountRequest("me")
      .then(() => {
        if (!c.signal.aborted) setSignedIn(true);
      })
      .catch(() => {});
    return () => c.abort();
  }, [id, query]);
  async function save() {
    if (!job) return;
    setBusy(true);
    try {
      const deadline = job.deadline
        ? typeof job.deadline === "number"
          ? new Date(job.deadline * 1000).toISOString().slice(0, 10)
          : String(job.deadline).slice(0, 10)
        : null;
      const d = await accountRequest("applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...blankApplication,
          job_title: job.title,
          company_name: job.company || "Company not supplied",
          location: job.location,
          source_url: job.url,
          source: job.source,
          deadline,
          salary_min: job.salary_min ?? null,
          salary_max: job.salary_max ?? null,
          salary_currency: job.salary_currency || "",
          salary_period: job.salary_period || "",
        }),
      });
      setRecordId(d.id);
      setMessage(
        d.status === "started"
          ? "Saved as Started. Confirm Applied only after submitting on the source website."
          : "This role is already in your tracker. Open your tracker to review its status.",
      );
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Header />
      <main id="main-content" className="shell job-detail">
        <Link
          href={
            job?.category === "scholarships"
              ? `/search?category=scholarships&availability=${job.listing_status || "open"}`
              : `/search?${query}`
          }
          className="back-link"
        >
          ← Back to results
        </Link>
        {message && (
          <p role="status" className="source-warning">
            {message}
          </p>
        )}
        {job ? (
          <>
            <div className="detail-heading">
              <div>
                <p className="eyebrow">{job.source}</p>
                <h1>{job.title}</h1>
                <p>
                  {job.company} · {job.location}
                </p>
                <div className="job-tags">
                  {job.category === "scholarships" && (
                    <span
                      className={`tag scholarship-status ${job.listing_status}`}
                    >
                      {job.listing_status === "open"
                        ? "Open for applications"
                        : job.listing_status === "closed"
                          ? "Closed archive"
                          : "Deadline unconfirmed"}
                    </span>
                  )}
                  {job.remote && <span className="tag mint">Remote</span>}
                  {job.job_type && <span className="tag">{job.job_type}</span>}
                  {job.industry && <span className="tag">{job.industry}</span>}
                </div>
              </div>
              <div className="detail-actions">
                <a
                  className="btn-primary"
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => {
                    if (signedIn && !recordId && job.can_apply !== false)
                      void save();
                  }}
                >
                  {job.can_apply === false
                    ? "Read official notice ↗"
                    : "Apply at source ↗"}
                </a>
                <p>
                  {job.listing_status === "closed"
                    ? "This scholarship has closed. The notice remains available for reference."
                    : job.listing_status === "unconfirmed"
                      ? "A current application deadline is not confirmed. Check the official notice for eligibility and availability."
                      : "Read the posting and submit on its original website. No account required."}
                </p>
                {signedIn ? (
                  <>
                    <button
                      disabled={busy || Boolean(recordId)}
                      onClick={save}
                      className="btn-outline"
                    >
                      {recordId ? "Saved to tracker" : "Save to tracker"}
                    </button>
                    {recordId && (
                      <Link href="/tracker" className="text-action">
                        Confirm Applied in your tracker →
                      </Link>
                    )}
                  </>
                ) : (
                  <Link href="/signup" className="text-action">
                    Create an account for application tracking →
                  </Link>
                )}
              </div>
            </div>
            <section className="detail-description">
              <h2>{job.description_kind === "source_summary" ? "Opportunity summary" : "About the opportunity"}</h2>
              <p>
                Deadline: {displayDate(job.deadline)} · Last source check:{" "}
                {displayDate(job.checked_at)}
              </p>
              {job.category === "scholarships" && (
                <p>
                  {job.eligibility_note}. Published by Scholsec. jobs.ac.ghana is
                  an independent listing service.
                </p>
              )}
              <p>
                {job.description ||
                  "The source did not provide a full description. Open the original posting for details."}
              </p>
              {job.description_kind === "source_summary" && <a className="portal-text-link" href={job.source_url || job.url} target="_blank" rel="noopener noreferrer">Read full requirements and application instructions at {job.source} ↗</a>}
            </section>
            {job.salary_min != null && (
              <p>
                Listed salary: {job.salary_currency || "Currency not supplied"}{" "}
                {Number(job.salary_min).toLocaleString()}
                {job.salary_max != null
                  ? ` to ${Number(job.salary_max).toLocaleString()}`
                  : ""}{" "}
                {job.salary_period || ""}
              </p>
            )}
            <p className="field-help">
              Check eligibility, salary units and the deadline on the original
              posting.{" "}
              <a
                href={job.source_url || job.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Source: {job.source} ↗
              </a>
            </p>
          </>
        ) : !message ? (
          <p>Loading the full posting…</p>
        ) : (
          <Link href="/search" className="btn-outline">
            Find current opportunities
          </Link>
        )}
      </main>
      <Footer />
    </>
  );
}
