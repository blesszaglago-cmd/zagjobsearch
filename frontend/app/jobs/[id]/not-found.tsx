import Link from "next/link";
export default function NotFound() {
  return (
    <main id="main-content" className="shell legal-page">
      <h1>This opportunity is no longer available.</h1>
      <p>Your saved application history remains in your tracker.</p>
      <Link href="/search" className="btn-primary">
        Find current opportunities
      </Link>
    </main>
  );
}
