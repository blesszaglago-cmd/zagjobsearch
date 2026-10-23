import Icon from "@/components/Icon";
import { Suspense } from "react";
import CoverageOverview from "@/components/CoverageOverview";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import SearchForm from "@/components/SearchForm";
import HomeHero from "@/components/HomeHero";
import HomeOpportunities from "@/components/HomeOpportunities";
import { siteUrl } from "@/lib/site";

export const metadata: Metadata = {
  title: {
    absolute: "jobs.ac.ghana | Jobs in Ghana, Internships & Scholarships",
  },
  description:
    "Find jobs across Ghana, internships, remote roles accepting Ghana-based applicants and scholarships for Ghanaians. Track your applications in one place.",
  alternates: { canonical: "/" },
};
const pathways = [
  {
    title: "I’m looking for a job",
    description:
      "Permanent, part-time and contract opportunities, from Accra to the rest of Ghana.",
    href: "/search?category=jobs",
    image: "/images/professionals.jpg",
    label: "Find jobs in Ghana",
    number: "01",
  },
  {
    title: "I’m starting my career",
    description:
      "Find your first experience through internships, graduate roles and apprenticeships.",
    href: "/search?category=early",
    image: "/images/teamwork.jpg",
    label: "Explore early careers",
    number: "02",
  },
  {
    title: "I want to work remotely",
    description:
      "Explore remote roles that explicitly accept applications from people based in Ghana.",
    href: "/search?category=remote",
    image: "/images/workplace.jpg",
    label: "See Ghana-eligible roles",
    number: "03",
  },
  {
    title: "I’m looking for study or research funding",
    description:
      "Explore scholarships, research grants and fellowships by level, source and application status.",
    href: "/search?category=scholarships",
    image: "/images/ghana-students.jpg",
    label: "Explore funding opportunities",
    number: "04",
  },
];
export default function Home() {
  return (
    <>
      <Header />
      <main id="main-content" className="portal-home">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: "jobs.ac.ghana",
              alternateName: "Jobs AC Ghana",
              url: siteUrl,
            }).replace(/</g, "\\u003c"),
          }}
        />
        <HomeHero />
        <section className="portal-search shell" aria-label="Search Ghana jobs">
          <div className="portal-search-heading">
            <span>YOUR NEXT CHAPTER STARTS WITH A SEARCH</span>
            <Link href="/search?category=jobs&region=Greater+Accra">
              Start with Accra & Greater Accra <Icon name="arrow-up-right" />
            </Link>
          </div>
          <SearchForm />
          <div className="portal-search-shortcuts">
            <span>Explore</span>
            <Link href="/search?category=jobs">Jobs across Ghana</Link>
            <Link href="/search?category=early&job_type=internship">
              Internships
            </Link>
            <Link href="/search?category=scholarships">Scholarships</Link>
          </div>
        </section>
        <div
          className="portal-trust shell"
          aria-label="How jobs.ac.ghana works"
        >
          {[
            ["16", "Region filters across Ghana"],
            ["4", "Separate opportunity categories"],
            ["Free", "Search and apply at the source"],
            ["Private", "Your application workspace"],
          ].map(([value, label]) => (
            <div key={value}>
              <strong>{value}</strong>
              <span>{label}</span>
            </div>
          ))}
        </div>
        <section className="portal-section portal-latest portal-watermark watermark-office">
          <div className="shell">
            <div className="portal-section-heading">
              <div>
                <p className="portal-eyebrow">LATEST OPPORTUNITIES</p>
                <h2>
                  Your next step
                  <br />
                  could be right here.
                </h2>
              </div>
              <div>
                <p>
                  Explore source-linked roles and open scholarship notices. Read
                  the full details, then apply on the original website.
                </p>
                <Link href="/search" className="portal-text-link">
                  View all opportunities{" "}
                  <span aria-hidden="true">
                    <Icon name="arrow-up-right" />
                  </span>
                </Link>
              </div>
            </div>
            <HomeOpportunities />
            <Suspense fallback={<p>Loading current coverage…</p>}>
              <CoverageOverview />
            </Suspense>
          </div>
        </section>
        <section className="portal-section portal-routes portal-watermark watermark-students">
          <div className="shell">
            <div className="portal-section-heading centered">
              <div>
                <p className="portal-eyebrow">FIND YOUR ROUTE</p>
                <h2>
                  Different ambitions.
                  <br />A clear path for each.
                </h2>
                <p>
                  Start with what you’re looking for. Each category has its own
                  filters, so jobs, internships and scholarships stay organised.
                </p>
              </div>
            </div>
            <div className="portal-route-grid">
              {pathways.map((path) => (
                <Link
                  href={path.href}
                  className="portal-route-card"
                  key={path.number}
                >
                  <div className="portal-route-photo">
                    <Image
                      src={path.image}
                      alt=""
                      fill
                      sizes="(max-width: 600px) 90vw, (max-width: 1000px) 45vw, 280px"
                    />
                    <span>{path.number}</span>
                  </div>
                  <div className="portal-route-body">
                    <h3>{path.title}</h3>
                    <p>{path.description}</p>
                    <span className="portal-card-link">
                      {path.label}{" "}
                      <span aria-hidden="true">
                        <Icon name="arrow-up-right" />
                      </span>
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
        <section className="portal-section portal-workspace portal-watermark watermark-desk">
          <div className="shell portal-feature-grid">
            <div className="portal-photo-stack">
              <div className="portal-photo-main">
                <Image
                  src="/images/professionals.jpg"
                  alt="Professionals sharing ideas around a table"
                  fill
                  sizes="(max-width: 800px) 90vw, 560px"
                />
              </div>
              <div className="portal-photo-small">
                <Image
                  src="/images/ghana-students.jpg"
                  alt="Students on a university campus in Accra, Ghana"
                  fill
                  sizes="(max-width: 800px) 45vw, 260px"
                />
              </div>
              <span className="portal-photo-note">
                Your ambition deserves a clear next step.
              </span>
            </div>
            <div className="portal-feature-copy">
              <p className="portal-eyebrow">MORE THAN A SEARCH</p>
              <h2>
                One place for
                <br />
                your whole job hunt.
              </h2>
              <p>
                Finding the opportunity is only the beginning. Keep a private
                record of where you applied, what happened next and what you
                need to remember.
              </p>
              <ul className="portal-check-list">
                <li>
                  <Icon name="check" />
                  Save the role, company and original application link.
                </li>
                <li>
                  <Icon name="check" />
                  Update your status as your application progresses.
                </li>
                <li>
                  <Icon name="check" />
                  Keep notes, contacts and follow-up dates together.
                </li>
              </ul>
              <div className="portal-actions">
                <Link href="/tracker" className="portal-button green">
                  Open application tracker <Icon name="arrow-up-right" />
                </Link>
                <Link href="/signup" className="portal-text-link">
                  Create a free account <Icon name="arrow-right" />
                </Link>
              </div>
              <p className="portal-small-note">
                Browse without an account. Create a free account to apply and
                track your progress.
              </p>
            </div>
          </div>
        </section>
        <section className="portal-section portal-journey">
          <div className="shell">
            <div className="portal-section-heading">
              <div>
                <p className="portal-eyebrow">YOUR APPLICATION JOURNEY</p>
                <h2>
                  Less searching in circles.
                  <br />
                  More moving forward.
                </h2>
              </div>
              <p>
                From your first search to your next follow-up, keep the
                important steps in sight.
              </p>
            </div>
            <div className="portal-steps">
              {[
                [
                  "01",
                  "Find your opportunity",
                  "Choose a category, add your keywords and filter by the details that matter to you.",
                ],
                [
                  "02",
                  "Read the full details",
                  "Review the requirements, location, source and deadline before you take the next step.",
                ],
                [
                  "03",
                  "Apply at the source",
                  "Follow the external link and complete your application on the original website.",
                ],
                [
                  "04",
                  "Keep your record",
                  "Sign in to save the opportunity. Mark it Applied after you submit, then update your progress.",
                ],
              ].map(([number, title, description]) => (
                <div key={number}>
                  <span>{number}</span>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </div>
              ))}
            </div>
            <div className="portal-source-note">
              <span aria-hidden="true">
                <Icon name="arrow-up-right" />
              </span>
              <div>
                <strong>Clear sources. Informed applications.</strong>
                <p>
                  Supported sources are checked daily. Coverage varies by region
                  and industry, and availability can change between checks.
                  Always confirm the details on the original posting.
                </p>
              </div>
            </div>
          </div>
        </section>
        <section className="portal-section portal-faq portal-watermark watermark-office">
          <div className="shell portal-faq-grid">
            <div>
              <p className="portal-eyebrow">A FEW THINGS TO KNOW</p>
              <h2>
                Before your
                <br />
                next application.
              </h2>
              <p>
                A clearer search starts with knowing how the platform works.
              </p>
            </div>
            <div className="portal-questions">
              <details>
                <summary>Do I need an account to apply?</summary>
                <p>
                  Yes. Anyone can search and read listings. Create a free
                  account or log in before using Apply. You’ll complete your
                  application on the original website and can keep a private
                  record in your tracker.
                </p>
              </details>
              <details>
                <summary>Where do I send my application?</summary>
                <p>
                  Use the Apply at source button on a listing. You’ll leave
                  jobs.ac.ghana and complete your application on the original
                  company, organisation or scholarship website.
                </p>
              </details>
              <details>
                <summary>Are all scholarships still open?</summary>
                <p>
                  No. Open awards appear by default. Notices without a confirmed
                  deadline and closed notices have their own filters. Always
                  read the official notice for full eligibility and dates.
                </p>
              </details>
              <details>
                <summary>Does opening Apply mean I have applied?</summary>
                <p>
                  No. Visiting an application website does not complete an
                  application. If you use the tracker, mark it Applied only
                  after you submit at the source.
                </p>
              </details>
            </div>
          </div>
        </section>
        <section className="portal-final">
          <div className="shell">
            <p className="portal-eyebrow">
              ROOTED IN GHANA. BUILT FOR YOUR NEXT CHAPTER.
            </p>
            <h2>
              Your next opportunity
              <br />
              is worth looking for.
            </h2>
            <p>Find your path. Make your move. Keep your progress.</p>
            <div className="portal-actions">
              <Link href="/search" className="portal-button gold">
                Explore opportunities <Icon name="arrow-up-right" />
              </Link>
              <Link
                href="/search?category=scholarships"
                className="portal-button ghost"
              >
                Browse scholarships
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
