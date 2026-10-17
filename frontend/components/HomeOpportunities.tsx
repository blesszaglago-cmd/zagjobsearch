"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import type { Job } from "@/lib/jobs";
import { displayDate } from "@/lib/ghana";
export default function HomeOpportunities() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  useEffect(() => {
    const controller = new AbortController();
    const read = async (category: string) => {
      const response = await fetch(
        `/api/jobs?category=${category}&availability=open`,
        { signal: controller.signal },
      );
      if (!response.ok) throw new Error("Could not load opportunities");
      const data = await response.json();
      return Array.isArray(data.jobs) ? (data.jobs as Job[]) : [];
    };
    Promise.allSettled([read("jobs"), read("scholarships")]).then((results) => {
      if (controller.signal.aborted) return;
      const roles = results[0].status === "fulfilled" ? results[0].value : [];
      const awards = results[1].status === "fulfilled" ? results[1].value : [];
      setJobs([
        ...roles.slice(0, awards.length ? 2 : 3),
        ...awards.slice(0, 1),
      ]);
      setState(
        results.every((result) => result.status === "rejected")
          ? "error"
          : "ready",
      );
    });
    return () => controller.abort();
  }, []);
  if (state === "loading")
    return (
      <div className="portal-opportunity-loading" role="status">
        Checking the latest source-linked opportunities…
      </div>
    );
  if (!jobs.length)
    return (
      <div className="portal-opportunity-empty">
        <p>
          {state === "error"
            ? "The latest opportunities could not load here. You can try the full search."
            : "No recently checked opportunities are available in this selection right now."}
        </p>
        <Link href="/search" className="portal-text-link">
          Open opportunity search ↗
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
              {job.category === "scholarships" ? "Scholarship" : "Job in Ghana"}
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
              Read the full details <span aria-hidden="true">↗</span>
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}
