import Header from "@/components/Header";
import Footer from "@/components/Footer";
import Link from "next/link";
import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "About this Ghana job platform",
  description:
    "An independent Ghana-focused job search and application tracker. Learn how sources, deadlines and reports work.",
  alternates: { canonical: "/about" },
};
export default function About() {
  return (
    <>
      <Header />
      <main id="main-content" className="shell legal-page">
        <p className="eyebrow">INDEPENDENT. GHANA FOCUSED.</p>
        <h1>One place to organise your job search.</h1>
        <p>
          jobs.ac.ghana helps you find Ghana-based jobs, early-career
          opportunities, remote roles explicitly accepting people in Ghana, and
          scholarships open to Ghanaians. Search is public. An account gives you
          a private application tracker and saved searches.
        </p>
        <h2>Where listings come from</h2>
        <p>
          We check public employer career boards, Ghana job boards, recruitment
          agencies and official scholarship notices. Each opportunity links to
          its original source. Some sources provide short factual summaries;
          full requirements stay at the publisher.
        </p>
        <Link href="/sources" className="btn-outline">
          See sources and current coverage
        </Link>
        <h2>What a source check means</h2>
        <p>
          We check dates, location and available publication information. This
          confirms what a source published at that check. It does not guarantee
          an employer is still hiring or that every claim is accurate. Use
          Report a problem on a listing if its details or destination need
          review.
        </p>
        <h2>Your applications remain yours</h2>
        <p>
          A saved role starts as Started. Confirm Applied after submitting at
          the source. Export your records, change account settings or delete
          your account from Settings.
        </p>
        <h2>Who runs it</h2>
        <p>
          Built by Bless Mawumenyo Zaglago. This is an independent platform,
          separate from government agencies, employers and the Ghana
          Scholarships Authority.
        </p>
        <p>
          Working website:{" "}
          <a href="https://zagjobsearch.vercel.app">zagjobsearch.vercel.app</a>.
          The name jobs.ac.ghana is the platform brand.
        </p>
        <p>
          Contact:{" "}
          <a href="mailto:blesszaglago@gmail.com">blesszaglago@gmail.com</a>.
        </p>
      </main>
      <Footer />
    </>
  );
}
