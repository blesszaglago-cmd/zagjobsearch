import Icon from "@/components/Icon";
import Image from "next/image";
import Link from "next/link";
import { homeOpportunities } from "@/lib/home-opportunities";
import { displayDate } from "@/lib/ghana";
export default async function HomeOpportunities() {
  const { jobs, unavailable } = await homeOpportunities();
  if (!jobs.length)
    return (
      <div className="portal-opportunity-empty">
        <p>
          {unavailable
            ? "The latest opportunities could not load here. You can try the full search."
            : "No recently checked opportunities are available in this selection right now."}
        </p>
        <Link href="/search" className="portal-text-link">
          Open opportunity search <Icon name="arrow-up-right" />
        </Link>
      </div>
    );
  return (
    <div className="portal-opportunity-grid">
      {jobs.map((job) => (
        <Link
          key={job.id}
          href={`/jobs/${encodeURIComponent(job.id)}`}
          className="portal-opportunity-card"
        >
          <div className="portal-opportunity-photo">
            <Image
              src={
                job.category === "scholarships"
                  ? "/images/ghana-students.jpg"
                  : "/images/professionals.jpg"
              }
              alt=""
              fill
              sizes="(max-width: 700px) 90vw, 380px"
            />
            <span>
              {job.category === "scholarships"
                ? "Study & research funding"
                : "Job in Ghana"}
            </span>
          </div>
          <div className="portal-opportunity-body">
            <p className="portal-opportunity-source">{job.company}</p>
            <h3>{job.title}</h3>
            <p className="portal-opportunity-location">
              {job.location || "See listing for location"}
            </p>
            {job.deadline ? (
              <p className="portal-opportunity-deadline">
                Deadline: {displayDate(job.deadline)}
              </p>
            ) : null}
            <span className="portal-card-link">
              Read the full details{" "}
              <span aria-hidden="true">
                <Icon name="arrow-up-right" />
              </span>
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}
