import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { regions } from "@/lib/ghana";
import { regionSlug } from "@/lib/coverage";
import { getSearchResult } from "@/lib/jobs-server";
import type { Job } from "@/lib/jobs";
type Props = { params: Promise<{ region: string }> };
const categories = [
  ["jobs", "Jobs", "jobs"],
  [
    "early",
    "Internships, graduate roles and apprenticeships",
    "early-career opportunities",
  ],
  ["remote", "Ghana-eligible remote roles", "remote roles"],
] as const;
async function read(p: Props) {
  const { region } = await p.params;
  const name = regions.find((r) => regionSlug(r) === region);
  if (!name) notFound();
  const buckets = await Promise.all(
    categories.map(async ([key, label, shortLabel]) => ({
      key,
      label,
      shortLabel,
      data: await getSearchResult(
        new URLSearchParams({ category: key, region: name }).toString(),
      ),
    })),
  );
  return { name, buckets, slug: region };
}
export async function generateMetadata(p: Props): Promise<Metadata> {
  const { name, buckets, slug } = await read(p);
  return {
    title: `Jobs in ${name}, Ghana`,
    description: `Explore source-linked jobs in Ghana's ${name} region. Review deadlines and requirements, apply at the source and track your applications.`,
    robots: { index: buckets[0].data.total > 0, follow: true },
    alternates: { canonical: `/regions/${slug}` },
  };
}
export default async function Region(p: Props) {
  const { name, buckets } = await read(p);
  const total = buckets.reduce((sum, bucket) => sum + bucket.data.total, 0);
  return (
    <>
      <Header />
      <main id="main-content" className="shell legal-page">
        <p className="eyebrow">JOBS ACROSS GHANA</p>
        <h1>Work and training opportunities in {name}</h1>
        <p>
          {total} current opportunities mapped to {name}, including nationwide
          programmes available in this region. Source checks confirm published
          information; selection and recruitment depend on the provider.
        </p>
        {buckets.map((bucket) => (
          <section key={bucket.key} aria-labelledby={`region-${bucket.key}`}>
            <h2 id={`region-${bucket.key}`}>
              {bucket.label} · {bucket.data.total}
            </h2>
            {bucket.data.jobs.map((j: Job) => (
              <article className="saved-search-row" key={j.id}>
                <div>
                  <h3>
                    <Link
                      href={`/jobs/${j.id}?from=${encodeURIComponent(`/search?${new URLSearchParams({ category: bucket.key, region: name })}`)}`}
                    >
                      {j.title}
                    </Link>
                  </h3>
                  <p>
                    {j.company} · {j.location}
                  </p>
                </div>
                <Link className="btn-outline" href={`/jobs/${j.id}`}>
                  View details
                </Link>
              </article>
            ))}
            {!bucket.data.total && (
              <p>
                No current {bucket.shortLabel} with a confirmed location in this
                region.
              </p>
            )}
            <Link
              className="btn-primary"
              href={`/search?${new URLSearchParams({ category: bucket.key, region: name })}`}
            >
              Filter {name} {bucket.shortLabel}
            </Link>
          </section>
        ))}
        <p>
          <Link href="/search">Search all Ghana opportunities</Link> ·{" "}
          <Link href="/sources">Review source coverage</Link>
        </p>
      </main>
      <Footer />
    </>
  );
}
