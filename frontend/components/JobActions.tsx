"use client";
import Icon from "@/components/Icon";
import { useEffect, useState } from "react";
import Link from "next/link";
import { accountRequest, blankApplication } from "@/lib/workspace";
import { trackEvent } from "@/lib/analytics";
import type { Job } from "@/lib/jobs";
import { siteUrl } from "@/lib/site";
export type ActionJob = Pick<
  Job,
  | "id"
  | "title"
  | "company"
  | "location"
  | "url"
  | "source"
  | "deadline"
  | "salary_min"
  | "salary_max"
  | "salary_currency"
  | "salary_period"
  | "can_apply"
  | "category"
>;
export default function JobActions({ job }: { job: ActionJob }) {
  const [signedIn, setSignedIn] = useState(false),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [record, setRecord] = useState("");
  const [reportOpen, setReportOpen] = useState(false),
    [reason, setReason] = useState("closed"),
    [details, setDetails] = useState("");
  const url = `${siteUrl}/jobs/${job.id}`;
  useEffect(() => {
    const c = new AbortController();
    accountRequest("me", { signal: c.signal })
      .then(() => setSignedIn(true))
      .catch(() => {});
    return () => c.abort();
  }, []);
  async function save(automatic = false) {
    setBusy(true);
    try {
      const deadline = job.deadline ? String(job.deadline).slice(0, 10) : null;
      const d = await accountRequest("applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...blankApplication,
          job_title: job.title,
          company_name: job.company,
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
      setRecord(d.id);
      setMessage(
        "Saved to your tracker. Confirm Applied after submitting on the original website.",
      );
      trackEvent("save_application", { job_id: job.id });
    } catch (e) {
      if (!automatic || (e as Error & { status?: number }).status !== 401)
        setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function share() {
    try {
      if (navigator.share)
        await navigator.share({
          title: job.title,
          text: `${job.title} at ${job.company}`,
          url,
        });
      else {
        await navigator.clipboard.writeText(url);
        setMessage("Job link copied.");
      }
      trackEvent("share_job", { job_id: job.id, method: "share" });
    } catch {
      setMessage(`Share this link: ${url}`);
    }
  }
  return (
    <div className="detail-actions">
      <a
        className="btn-primary"
        href={job.can_apply === false ? job.url : `/api/jobs/${job.id}/apply`}
        target="_blank"
        rel="noopener noreferrer"
        onClick={() => {
          trackEvent("apply_click", { job_id: job.id });
          if (job.can_apply !== false && !record) void save(true);
        }}
      >
        {job.can_apply === false
          ? "Read official notice"
          : "Apply at source"}
        <Icon name="external-link" />
      </a>
      <p>
        {job.can_apply === false
          ? "Read the notice for its application status."
          : "Apply on the original website. A saved record does not confirm submission."}
      </p>
      {signedIn ? (
        <button
          className="btn-outline"
          disabled={busy || Boolean(record)}
          onClick={() => void save()}
        >
          {record ? "Saved to tracker" : busy ? "Saving…" : "Save to tracker"}
        </button>
      ) : (
        <Link className="portal-text-link" href="/signup">
          Create an account for tracking <Icon name="arrow-right" />
        </Link>
      )}
      {record && <Link href="/tracker">Confirm Applied in your tracker <Icon name="arrow-right" /></Link>}
      <div className="job-share-actions">
        <button className="btn-outline" onClick={() => void share()}>
          Share job
        </button>
        <a
          className="btn-outline"
          href={`https://wa.me/?text=${encodeURIComponent(`${job.title} at ${job.company}\n${url}`)}`}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() =>
            trackEvent("share_job", { job_id: job.id, method: "whatsapp" })
          }
        >
          Share on WhatsApp
        </a>
      </div>
      {message && (
        <p role="status" className="source-warning">
          {message}
        </p>
      )}
      <button
        className="portal-text-link"
        onClick={() => setReportOpen(!reportOpen)}
        aria-expanded={reportOpen}
      >
        Report a problem with this listing
      </button>
      {reportOpen && (
        <form
          className="account-form job-report"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              const r = await fetch(`/api/jobs/${job.id}/report`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reason, details }),
              });
              const d = await r.json();
              if (!r.ok) throw Error(d.detail || "Report could not be saved.");
              setMessage("Report received for review. Thank you.");
              setReportOpen(false);
              setDetails("");
            } catch (e) {
              setMessage((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            What is wrong?
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="closed">Expired or no longer available</option>
              <option value="fraud">Suspicious or misleading</option>
              <option value="broken_link">
                Application link does not work
              </option>
              <option value="wrong_location">
                Location or eligibility is incorrect
              </option>
              <option value="other">Other issue</option>
            </select>
          </label>
          <label>
            Details, without personal information
            <textarea
              maxLength={2000}
              rows={3}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
            />
          </label>
          <button className="btn-outline" disabled={busy}>
            Submit report
          </button>
        </form>
      )}
    </div>
  );
}
