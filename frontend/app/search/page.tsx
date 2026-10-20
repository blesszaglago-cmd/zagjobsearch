import type { Metadata } from "next";
import SearchContent from "@/components/SearchContent";
import { getSearchResult } from "@/lib/jobs-server";
type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};
function filters(p: Record<string, string | string[] | undefined>) {
  return new URLSearchParams(
    Object.fromEntries(
      Object.entries(p).filter(([, v]) => typeof v === "string") as [
        string,
        string,
      ][],
    ),
  );
}
export async function generateMetadata({
  searchParams,
}: Props): Promise<Metadata> {
  const p = filters(await searchParams);
  const category = p.get("category") || "jobs";
  const names: Record<string, string> = {
    jobs: "Jobs in Ghana",
    early: "Internships and graduate opportunities in Ghana",
    remote: "Remote jobs accepting Ghana-based applicants",
    scholarships: "Scholarships for Ghanaians",
  };
  const filtered = [...p.keys()].some((k) => k !== "category");
  let hasResults = false;
  try {
    hasResults = (await getSearchResult(p.toString())).total > 0;
  } catch {}
  return {
    title: names[category] || names.jobs,
    description:
      "Search current Ghana opportunities with source links, application deadlines and a private application tracker.",
    robots: { index: !filtered && hasResults, follow: true },
    alternates: {
      canonical:
        category === "jobs" ? "/search" : `/search?category=${category}`,
    },
  };
}
export default async function Page({ searchParams }: Props) {
  const p = filters(await searchParams);
  const query = p.toString();
  let data;
  try {
    data = await getSearchResult(query);
  } catch {
    data = {
      jobs: [],
      total: 0,
      has_more: false,
      error:
        "The catalogue is temporarily unavailable. Please try again shortly.",
    };
  }
  return <SearchContent key={query} initialFilter={query} initialData={data} />;
}
