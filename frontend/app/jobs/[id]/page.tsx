import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import JobActions from "@/components/JobActions";
import { getJob } from "@/lib/jobs-server";
import { displayDate, experienceLevels, studyLevels } from "@/lib/ghana";
import { jobSchema } from "@/lib/job-metadata";
type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const job = await getJob(id);
  if (!job)
    return {
      title: "Opportunity no longer available",
      robots: { index: false, follow: true },
    };
  const title = `${job.title} at ${job.company}`;
  const description = `${job.title} in ${job.location}. ${job.description.slice(0, 125)}`;
  return {
    title,
    description,
    alternates: { canonical: `/jobs/${id}` },
    robots: { index: true, follow: true },
    openGraph: { title, description, url: `/jobs/${id}` },
    twitter: { card: "summary_large_image", title, description },
  };
}
export default async function Details({ params, searchParams }: Props) {
  const { id } = await params;
  const [job, p] = await Promise.all([getJob(id), searchParams]);
  if (!job) notFound();
  const from =
    typeof p.from === "string" && /^\/search(?:\?|$)/.test(p.from)
      ? p.from
      : `/search?category=${job.category || "jobs"}`;
  const schema = jobSchema(job);
  const action = {
    id: job.id,
    title: job.title,
    company: job.company,
    location: job.location,
    url: job.url,
    source: job.source,
    deadline: job.deadline,
    salary_min: job.salary_min,
    salary_max: job.salary_max,
    salary_currency: job.salary_currency,
    salary_period: job.salary_period,
    can_apply: job.can_apply,
    category: job.category,
  };
  return (
    <>
      <Header />
      <main id="main-content" className="shell job-detail">
        <Link href={from} className="back-link">
          ← Back to your results
        </Link>
        {schema && (
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify(schema).replace(/</g, "\\u003c"),
            }}
          />
        )}
        <div className="detail-heading">
          <div>
            <p className="eyebrow">{job.source}</p>
            <h1>{job.title}</h1>
            <p>
              {job.company} · {job.location}
            </p>
            <div className="job-tags">
              {job.remote && <span className="tag">Remote from Ghana</span>}
              <span className="tag">
                {job.job_type === "unspecified"
                  ? "Employment type not stated"
                  : job.job_type}
              </span>
              {job.category === "scholarships" && (
                <span className="tag">
                  {job.listing_status === "open"
                    ? "Open for applications"
                    : job.listing_status === "closed"
                      ? "Closed archive"
                      : "Deadline unconfirmed"}
                </span>
              )}
            </div>
          </div>
          <JobActions job={action} />
        </div>
        <dl className="job-facts">
          <div>
            <dt>Application deadline</dt>
            <dd>{displayDate(job.deadline)}</dd>
          </div>
          <div>
            <dt>Last source check</dt>
            <dd>{displayDate(job.checked_at)}</dd>
          </div>
          {job.category !== "scholarships" && (
            <div>
              <dt>Experience</dt>
              <dd>
                {experienceLevels.find(([v]) => v === job.experience)?.[1] ||
                  "Level not stated"}
                {job.experience_years_min != null
                  ? ` · ${job.experience_years_min}${job.experience_years_max ? `–${job.experience_years_max}` : "+"} years requested`
                  : ""}
              </dd>
            </div>
          )}
          {job.category === "scholarships" && (
            <div>
              <dt>Study levels</dt>
              <dd>
                {job.study_levels
                  ?.map((v) => studyLevels.find(([k]) => k === v)?.[1] || v)
                  .join(", ") || "See official notice"}
              </dd>
            </div>
          )}
          <div>
            <dt>Listed salary</dt>
            <dd>
              {job.salary_min != null || job.salary_max != null
                ? `${job.salary_currency || "Currency not stated"} ${job.salary_min?.toLocaleString() || ""}${job.salary_max != null ? ` to ${job.salary_max.toLocaleString()}` : ""}${job.salary_period ? ` per ${job.salary_period}` : " · period not stated"}`
                : "Not stated by the source"}
            </dd>
          </div>
        </dl>
        <section className="detail-description">
          <h2>
            {job.description_kind === "source_summary"
              ? "Opportunity summary"
              : "About the opportunity"}
          </h2>
          {job.category === "scholarships" && (
            <p>
              {job.eligibility_note}. Published by the Ghana Scholarships
              Authority. This platform is independent.
            </p>
          )}
          <p className="job-description-copy">{job.description}</p>
          {job.description_kind === "source_summary" && (
            <p>
              <a
                className="portal-text-link"
                href={job.source_url || job.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Read the full requirements and instructions at {job.source} ↗
              </a>
            </p>
          )}
          {job.search_terms && job.search_terms.length > 0 && (
            <p className="field-help">
              Mentioned by the source: {job.search_terms.join(", ")}.
            </p>
          )}
        </section>
        <p className="field-help">
          Confirm requirements and availability on the original posting.
          Publication at the last check does not verify every employer claim.{" "}
          <a
            href={job.source_url || job.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            View source ↗
          </a>
        </p>
        {job.source_urls && job.source_urls.length > 1 && (
          <details>
            <summary>Other matching source notices</summary>
            {job.source_urls.map((url) => (
              <p key={url}>
                <a href={url} target="_blank" rel="noopener noreferrer">
                  {new URL(url).hostname} ↗
                </a>
              </p>
            ))}
          </details>
        )}
      </main>
      <Footer />
    </>
  );
}
