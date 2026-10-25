import "server-only";
import { API_URL } from "@/lib/api";
import type { Job } from "@/lib/jobs";

export async function homeOpportunities(): Promise<{
  jobs: Job[];
  unavailable: boolean;
}> {
  const read = async (category: string) => {
    const response = await fetch(
      `${API_URL}/catalogue?category=${category}&availability=open`,
      {
        next: { revalidate: 60 },
        signal: AbortSignal.timeout(5000),
      },
    );
    if (!response.ok) throw new Error("Opportunity preview unavailable");
    const data = await response.json();
    if (!Array.isArray(data.jobs))
      throw new Error("Opportunity preview unavailable");
    return data.jobs.filter((job: Job) => {
      if (
        !job ||
        typeof job !== "object" ||
        !/^[a-f0-9]{32}$/.test(job.id) ||
        typeof job.title !== "string" ||
        !job.title.trim() ||
        typeof job.company !== "string" ||
        !job.company.trim() ||
        job.category !== category ||
        job.can_apply === false
      )
        return false;
      return !job.deadline || new Date(job.deadline).getTime() >= Date.now();
    }) as Job[];
  };
  const results = await Promise.allSettled([
    read("jobs"),
    read("scholarships"),
  ]);
  const roles = results[0].status === "fulfilled" ? results[0].value : [];
  const awards = results[1].status === "fulfilled" ? results[1].value : [];
  return {
    jobs: [...roles.slice(0, awards.length ? 2 : 3), ...awards.slice(0, 1)],
    unavailable: results.every((result) => result.status === "rejected"),
  };
}
