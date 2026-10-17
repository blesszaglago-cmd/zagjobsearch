"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main id="main-content" className="shell legal-page">
      <h1>This page could not load.</h1>
      <p>
        The service may be temporarily unavailable. Your saved application
        records remain in your account.
      </p>
      <button className="btn-primary" onClick={reset}>
        Try again
      </button>{" "}
      <a href="/search">Return to search</a>
    </main>
  );
}
