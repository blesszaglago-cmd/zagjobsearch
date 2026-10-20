import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { regions } from "@/lib/ghana";
import { regionSlug } from "@/lib/coverage";
import { getSearchResult } from "@/lib/jobs-server";
type Props = { params: Promise<{ region: string }> };
async function read(p: Props) {
  const { region } = await p.params;
  const name = regions.find((r) => regionSlug(r) === region);
  if (!name) notFound();
  const data = await getSearchResult(
    new URLSearchParams({ category: "jobs", region: name }).toString(),
  );
  return { name, data, slug: region };
}
export async function generateMetadata(p: Props): Promise<Metadata> {
  const { name, data, slug } = await read(p);
  return {
    title: `Jobs in ${name}, Ghana`,
    description: `Explore source-linked jobs in Ghana's ${name} region. Review deadlines and requirements, apply at the source and track your applications.`,
    robots: { index: data.total > 0, follow: true },
    alternates: { canonical: `/regions/${slug}` },
  };
}
export default async function Region(p: Props) {
  const { name, data } = await read(p);
  return (
    <>
      <Header />
      <main id="main-content" className="shell legal-page">
        <p className="eyebrow">JOBS ACROSS GHANA</p>
        <h1>Jobs in {name}</h1>
        <p>
          {data.total} current opportunities with a work location mapped to{" "}
          {name}. Source checks confirm published information, not a guarantee
          of recruitment.
        </p>
        {data.jobs.map(
          (j: {
            id: string;
            title: string;
            company: string;
            location: string;
          }) => (
            <article className="saved-search-row" key={j.id}>
              <div>
                <h2>
                  <Link
                    href={`/jobs/${j.id}?from=${encodeURIComponent(`/search?${new URLSearchParams({ category: "jobs", region: name })}`)}`}
                  >
                    {j.title}
                  </Link>
                </h2>
                <p>
                  {j.company} · {j.location}
                </p>
              </div>
              <Link className="btn-outline" href={`/jobs/${j.id}`}>
                View details
              </Link>
            </article>
          ),
        )}
        {!data.total && (
          <p>
            No current verified-location matches are available here. Ghana-wide
            opportunities without a specific town may still appear in the full
            search.
          </p>
        )}
        <Link
          className="btn-primary"
          href={`/search?${new URLSearchParams({ category: "jobs", region: name })}`}
        >
          Search and filter {name} jobs
        </Link>
        <p>
          <Link href="/search">Search all Ghana opportunities</Link> ·{" "}
          <Link href="/sources">Review source coverage</Link>
        </p>
      </main>
      <Footer />
    </>
  );
}
