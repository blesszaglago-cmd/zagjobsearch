import type { Job } from "./jobs";
import { siteUrl } from "./site";
export function jobSchema(job: Job) {
  if (
    job.category === "scholarships" ||
    job.description_kind === "source_summary" ||
    job.date_kind !== "published" ||
    !job.created ||
    !job.description ||
    job.description.length < 200 ||
    job.can_apply === false
  )
    return null;
  const employment: Record<string, string> = {
    "full-time": "FULL_TIME",
    permanent: "FULL_TIME",
    "part-time": "PART_TIME",
    contract: "CONTRACTOR",
    internship: "INTERN",
    graduate: "FULL_TIME",
    apprenticeship: "INTERN",
  };
  return {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    identifier: { "@type": "PropertyValue", name: job.company, value: job.id },
    title: job.title,
    description: job.description,
    datePosted: job.created,
    ...(job.deadline ? { validThrough: job.deadline } : {}),
    hiringOrganization: { "@type": "Organization", name: job.company },
    jobLocation: {
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressCountry: "GH",
        addressLocality: job.location,
      },
    },
    ...(job.remote
      ? {
          jobLocationType: "TELECOMMUTE",
          applicantLocationRequirements: { "@type": "Country", name: "Ghana" },
        }
      : {}),
    ...(employment[job.job_type || ""]
      ? { employmentType: employment[job.job_type || ""] }
      : {}),
    url: `${siteUrl}/jobs/${job.id}`,
  };
}
