import { NextRequest, NextResponse } from "next/server";

const countryNames: Record<string, string[]> = { gh: ["ghana", "africa", "emea"], ng: ["nigeria", "africa", "emea"], ke: ["kenya", "africa", "emea"], za: ["south africa", "africa", "emea"], us: ["usa", "united states", "north america"], gb: ["uk", "united kingdom", "europe", "emea"], ca: ["canada", "north america"], de: ["germany", "europe", "eu", "emea"], fr: ["france", "europe", "eu", "emea"], in: ["india", "asia", "apac"], au: ["australia", "oceania", "apac"] };
function text(value: unknown): string { return typeof value === "string" ? value.replace(/<[^>]*>/g, " ").replace(/&amp;/g, "&").replace(/&#039;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, " ").trim() : ""; }
export async function GET(request: NextRequest) {
  const q = (request.nextUrl.searchParams.get("q") || "").trim().toLowerCase().slice(0, 200);
  const country = request.nextUrl.searchParams.get("country") || "gh";
  const page = Math.max(1, Math.min(10, Number(request.nextUrl.searchParams.get("page")) || 1));
  if (!q || !countryNames[country]) return NextResponse.json({ jobs: [] });
  try {
    // One common URL, persisted by Next's Data Cache, rather than one upstream request per user search.
    const response = await fetch("https://jobicy.com/api/v2/remote-jobs?count=200", { next: { revalidate: 3600 }, headers: { Accept: "application/json" }, signal: AbortSignal.timeout(12000) });
    if (!response.ok) throw new Error("Feed unavailable");
    const data = await response.json();
    if (data.success === false || !Array.isArray(data.jobs)) throw new Error("Invalid feed");
    const jobs = data.jobs.filter((job: Record<string, unknown>) => {
      const geo = text(job.jobGeo).toLowerCase();
      const places = geo.split(/[,;|]/).map(place => place.trim());
      const eligible = places.some(place => ["anywhere", "worldwide", "global"].includes(place) || countryNames[country].includes(place));
      const content = text(`${job.jobTitle || ""} ${job.companyName || ""} ${job.jobExcerpt || ""} ${job.jobDescription || ""}`).toLowerCase();
      return eligible && q.split(/\s+/).every(word => content.includes(word));
    }).slice((page - 1) * 20, page * 20).map((job: Record<string, unknown>) => ({ id: `jobicy:${job.id}`, title: text(job.jobTitle), company: text(job.companyName), location: text(job.jobGeo), description: text(job.jobExcerpt).slice(0, 300), url: text(job.url), created: job.pubDate, salary_min: job.salaryMin ?? null, salary_max: job.salaryMax ?? null, salary_currency: job.salaryCurrency ?? null, salary_period: job.salaryPeriod ?? null, source: "jobicy", remote: true }));
    return NextResponse.json({ jobs });
  } catch { return NextResponse.json({ jobs: [], errors: ["Jobicy temporarily unavailable"] }, { status: 503 }); }
}
