import Icon from "@/components/Icon";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Employer and sponsorship enquiries",
  description:
    "Enquire about one-off featured opportunities and sponsorships supporting free Ghana job search. No job seeker subscription.",
  alternates: { canonical: "/sponsor" },
};
export default function Sponsor() {
  return (
    <>
      <Header />
      <main id="main-content" className="shell legal-page">
        <p className="eyebrow">SUPPORT FREE JOB SEARCH</p>
        <h1>Reach people looking for their next opportunity.</h1>
        <p>
          Employers and organisations can enquire about a one-off featured
          vacancy or a clearly labelled sponsorship. Job seekers keep free
          access to search and application tracking.
        </p>
        <h2>Featured opportunities</h2>
        <p>
          Provide your organisation name, official vacancy link, Ghana location
          or Ghana eligibility, and closing date. Requests require review.
          Payment does not establish that a job is genuine or guarantee
          placement, applications or hires.
        </p>
        <h2>Sponsorships</h2>
        <p>
          Ask about a labelled placement supporting the platform. Availability
          and terms are agreed individually. Sponsored content must remain
          distinguishable from regular listings.
        </p>
        <p>
          No subscription or checkout is required to enquire. No paid placement
          is active until its terms and content are approved.
        </p>
        <a
          className="btn-primary"
          href="mailto:blesszaglago@gmail.com?subject=jobs.ac.ghana%20employer%20or%20sponsorship%20enquiry"
        >
          Enquire by email <Icon name="arrow-up-right" />
        </a>
        <p>
          Never pay an application fee to jobs.ac.ghana. We do not sell
          applicants’ personal records or contact details.
        </p>
      </main>
      <Footer />
    </>
  );
}
