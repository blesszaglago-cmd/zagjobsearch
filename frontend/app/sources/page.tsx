import type { Metadata } from "next";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { API_URL } from "@/lib/api";

export const metadata: Metadata = {
  title: "Our Ghana job sources",
  description:
    "See where jobs.ac.ghana finds Ghana jobs, internships and scholarships, which sources were checked, and other places to search.",
  alternates: { canonical: "/sources" },
};

type Source = {
  key?: string;
  name: string;
  url: string;
  kind: string;
  note: string;
  state?: string;
  accepted?: number;
};
type Coverage = {
  updated_at: string | null;
  imported: Source[];
  external: Source[];
};

export default async function Sources() {
  let coverage: Coverage | null = null;
  try {
    const response = await fetch(`${API_URL}/catalogue/sources`, {
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
    if (response.ok) coverage = await response.json();
  } catch {
    /* The rest of the page remains useful when source status is unavailable. */
  }
  const checked =
    coverage?.imported.filter((s) => s.state === "ok").length ?? 0;
  return (
    <>
      <Header />
      <main id="main-content" className="sources-page">
        <section className="sources-hero portal-watermark">
          <div className="shell">
            <p className="portal-eyebrow">GHANA FIRST · SOURCE BY SOURCE</p>
            <h1>
              Know where your
              <br />
              next move comes from.
            </h1>
            <p>
              Employer career pages, Ghana job boards, recruitment agencies and
              official notices. Clear sources. Direct application links.
            </p>
            <Link href="/search" className="btn-primary">
              Find opportunities ↗
            </Link>
          </div>
        </section>
        <section className="portal-section">
          <div className="shell">
            <div className="portal-section-heading">
              <div>
                <p className="portal-eyebrow">PART OF YOUR SEARCH</p>
                <h2>Sources we check.</h2>
              </div>
              <div>
                <p>
                  We check for updates automatically, normally every six hours.
                  A source may have no current Ghana vacancies. Coverage is
                  growing and may not include every opportunity.
                </p>
                {coverage?.updated_at && (
                  <p className="sources-updated">
                    {checked} sources checked successfully in the latest refresh
                    ·{" "}
                    {new Intl.DateTimeFormat("en-GH", {
                      dateStyle: "medium",
                      timeStyle: "short",
                      timeZone: "Africa/Accra",
                    }).format(new Date(coverage.updated_at))}{" "}
                    GMT
                  </p>
                )}
              </div>
            </div>
            {!coverage && (
              <p role="status" className="source-warning">
                Source status is temporarily unavailable. You can still search
                recently checked opportunities.
              </p>
            )}
            <div className="sources-grid">
              {coverage?.imported.map((source) => (
                <article className="source-card" key={source.key}>
                  <div className="source-card-top">
                    <span>{source.kind}</span>
                    <span
                      className={`source-health ${source.state === "ok" ? "checked" : "pending"}`}
                    >
                      {source.state === "ok"
                        ? "Checked"
                        : source.state === "unavailable"
                          ? "Check unavailable"
                          : "Awaiting check"}
                    </span>
                  </div>
                  <h3>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {source.name} ↗
                    </a>
                  </h3>
                  <p>{source.note}</p>
                  <div className="source-card-bottom">
                    {source.state === "ok"
                      ? `${source.accepted ?? 0} eligible records at last check`
                      : "Only recently confirmed records appear in search"}
                  </div>
                </article>
              ))}
            </div>
            <aside className="sources-explainer">
              <h3>A live page is only one check.</h3>
              <p>
                We check closing dates and Ghana work locations. Job-board
                postings without deadlines are withheld after 60 days when their
                publication age is known. Official employer feeds may retain
                older roles that are still explicitly published. Listings that
                have not been checked within 48 hours leave search. Board
                summaries link to full requirements at the source. Apply checks
                the source again before sending you outside this website.
                Employers can still close recruitment between checks.
              </p>
            </aside>
          </div>
        </section>
        <section className="portal-section sources-more portal-watermark">
          <div className="shell">
            <div className="portal-section-heading">
              <div>
                <p className="portal-eyebrow">KEEP EXPLORING</p>
                <h2>More places to look.</h2>
              </div>
              <p>
                These are useful external destinations. Their vacancies are not
                automatically imported here. Some require an approved feed,
                permission or a public vacancy service.
              </p>
            </div>
            <div className="sources-grid">
              {coverage?.external.map((source) => (
                <article className="source-card" key={source.name}>
                  <div className="source-card-top">
                    <span>{source.kind}</span>
                    <span className="source-health external">
                      External website
                    </span>
                  </div>
                  <h3>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {source.name} ↗
                    </a>
                  </h3>
                  <p>{source.note}</p>
                </article>
              ))}
            </div>
            <p className="sources-independence">
              Source names identify where opportunities are published. Inclusion
              does not imply a partnership or endorsement. We are an independent
              platform.
            </p>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
