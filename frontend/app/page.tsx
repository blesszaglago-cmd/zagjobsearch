import type { Metadata } from "next";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import SearchForm from "@/components/SearchForm";
import { siteUrl } from "@/lib/site";
export const metadata: Metadata = {
  title: {
    absolute: "ZagJobSearch | Jobs in Ghana, Internships & Scholarships",
  },
  description:
    "Find jobs across Ghana, internships, remote roles accepting Ghana-based applicants and scholarships for Ghanaians. Track your applications in one place.",
  alternates: { canonical: "/" },
};
const paths = [
  [
    "01",
    "Jobs in Ghana",
    "From Accra to opportunities across the country.",
    "/search?category=jobs",
    "lavender",
  ],
  [
    "02",
    "Internships & early careers",
    "Internships, graduate programmes and apprenticeships.",
    "/search?category=early",
    "mint",
  ],
  [
    "03",
    "Remote from Ghana",
    "Roles with explicit eligibility for Ghana-based applicants.",
    "/search?category=remote",
    "peach",
  ],
  [
    "04",
    "Scholarships",
    "Study in Ghana or abroad, with Ghanaian eligibility.",
    "/search?category=scholarships",
    "lavender",
  ],
];
export default function Home() {
  return (
    <>
      <Header />
      <main id="main-content" className="gh-home">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: "ZagJobSearch",
              url: siteUrl,
            }).replace(/</g, "\\u003c"),
          }}
        />
        <div className="shell">
          <section className="gh-hero photo-section photo-team">
            <div className="gh-hero-copy">
              <p className="eyebrow">
                <span className="ghana-flag" aria-label="Ghana flag">
                  ★
                </span>{" "}
                MADE FOR YOUR NEXT MOVE IN GHANA
              </p>
              <h1>
                Your talent.
                <br />
                Your next role.
                <br />
                <span>Right here in Ghana.</span>
              </h1>
              <p>
                Find jobs, internships and scholarships with clear sources and
                application links. Keep your applications organised as you move
                forward.
              </p>
              <Link href="/search" className="btn-primary">
                Explore Ghana jobs ↗
              </Link>
            </div>
            <div className="gh-hero-art" aria-hidden="true">
              <div className="kente-ribbon" />
              <div className="gh-art-card">
                <span className="gh-art-label">YOUR SEARCH, YOUR WAY</span>
                <h2>
                  Where will
                  <br />
                  you go next?
                </h2>
                <div className="gh-city-list">
                  <span>Accra</span>
                  <span>Kumasi</span>
                  <span>Takoradi</span>
                  <span>Tamale</span>
                  <span>Ho</span>
                  <span>Across Ghana</span>
                </div>
                <p>Jobs · Internships · Scholarships</p>
              </div>
              <div className="ghana-star">★</div>
            </div>
          </section>
          <section
            className="search-section photo-section photo-desk"
            aria-label="Search Ghana jobs"
          >
            <SearchForm />
            <div className="search-bottom">
              <div className="popular">
                <span>Start here</span>
                <Link href="/search?category=jobs&region=Greater+Accra">
                  Accra & Greater Accra ↗
                </Link>
                <Link href="/search?category=early&job_type=internship">
                  Internships ↗
                </Link>
                <Link href="/search?category=jobs">Across Ghana ↗</Link>
              </div>
            </div>
          </section>
          <section className="gh-pathways photo-section photo-workplace">
            <div className="section-heading">
              <div>
                <p className="eyebrow muted">CHOOSE YOUR PATH</p>
                <h2>
                  Different opportunities.
                  <br />A search that fits each one.
                </h2>
              </div>
            </div>
            <div className="gh-path-grid">
              {paths.map(([n, title, desc, url, tone]) => (
                <Link className={`gh-path ${tone}`} href={url} key={n}>
                  <span className="gh-path-number">{n}</span>
                  <h3>{title}</h3>
                  <p>{desc}</p>
                  <span className="gh-path-cta">Explore →</span>
                </Link>
              ))}
            </div>
          </section>
          <section className="gh-tracker photo-section photo-desk">
            <div>
              <p className="eyebrow">KEEP YOUR NEXT STEP IN SIGHT</p>
              <h2>
                Every application.
                <br />
                One private workspace.
              </h2>
              <p>
                Remember where you applied, update your progress and keep notes
                for your follow-up. Search and apply freely. Create an account
                when you want to track your applications.
              </p>
              <Link href="/tracker" className="btn-primary">
                Open application tracker ↗
              </Link>
            </div>
            <div className="gh-tracker-preview" aria-hidden="true">
              <span>YOUR APPLICATION JOURNEY</span>
              <div>
                <i />
                Started
              </div>
              <div>
                <i />
                Applied
              </div>
              <div>
                <i />
                Interview
              </div>
              <p>Illustration of tracker statuses</p>
            </div>
          </section>
          <section className="gh-quality">
            <p className="eyebrow muted">CLEAR SOURCES. USEFUL DETAILS.</p>
            <h2>Know what you’re applying for.</h2>
            <div className="steps-grid">
              {[
                [
                  "01",
                  "Check the listing",
                  "See the employer, location, source and deadline when provided.",
                ],
                [
                  "02",
                  "Apply at the source",
                  "Read the requirements and complete your application on the original website.",
                ],
                [
                  "03",
                  "Keep your record",
                  "Save the opportunity and confirm Applied after you submit.",
                ],
              ].map(([n, t, d]) => (
                <div className="step" key={n}>
                  <span className="step-number">{n}</span>
                  <h3>{t}</h3>
                  <p>{d}</p>
                </div>
              ))}
            </div>
            <p className="coverage-note">
              We collect from supported employer and official sources, check
              them daily and hide stale listings. Coverage varies by region and
              industry. A source check does not guarantee an employer’s decision
              or availability between checks.
            </p>
          </section>
          <section className="bottom-cta gh-banner">
            <p className="eyebrow">YOUR NEXT OPPORTUNITY STARTS HERE</p>
            <h2>Built for job seekers in Ghana.</h2>
            <Link
              href="/search?category=jobs&region=Greater+Accra"
              className="btn-primary"
            >
              Explore Accra jobs ↗
            </Link>
            <Link href="/search" className="cta-link">
              Search across Ghana →
            </Link>
          </section>
        </div>
      </main>
      <Footer />
    </>
  );
}
