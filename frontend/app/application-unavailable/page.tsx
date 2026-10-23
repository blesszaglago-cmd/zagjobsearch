import type { Metadata } from "next";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "Application source unavailable",
  robots: { index: false, follow: true },
};

export default async function ApplicationUnavailable({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string | string[] }>;
}) {
  const closed = (await searchParams).reason === "closed";
  return (
    <>
      <Header />
      <main id="main-content" className="shell legal-page">
        <p className="eyebrow">APPLICATION SOURCE CHECK</p>
        <h1>
          {closed
            ? "This opportunity is no longer open."
            : "We could not confirm the application link."}
        </h1>
        <p>
          {closed
            ? "The posting has closed or the source no longer lists it as available. Browse the current opportunities for another role or funding call."
            : "The original website is temporarily unavailable or could not confirm this posting. Try again shortly or browse another opportunity."}
        </p>
        <p>Your saved application history remains in your tracker.</p>
        <p>
          <Link href="/search" className="btn-primary">
            Find current opportunities
          </Link>
        </p>
        <p>
          <Link href="/tracker">Open your application tracker</Link>
        </p>
      </main>
      <Footer />
    </>
  );
}
