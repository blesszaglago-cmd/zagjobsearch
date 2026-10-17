"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { accountRequest } from "@/lib/workspace";
type Search = {
  id: string;
  name: string;
  filters: Record<string, string>;
  email_alert: boolean;
};
export default function SavedSearches() {
  const [items, setItems] = useState<Search[]>([]),
    [message, setMessage] = useState("");
  useEffect(() => {
    const c = new AbortController();
    accountRequest("saved-searches", { signal: c.signal })
      .then((d) => setItems(d.searches))
      .catch((e) => {
        if (!c.signal.aborted) setMessage(e.message);
      });
    return () => c.abort();
  }, []);
  return (
    <>
      <Header />
      <main id="main-content" className="shell settings-page">
        <p className="eyebrow">KEEP YOUR SEARCH ORGANISED</p>
        <h1>Saved searches</h1>
        <p>
          Return to the filters you use often. Email alerts are optional and
          require a verified address.
        </p>
        {message && (
          <p role="status" className="source-warning">
            {message} <Link href="/login">Log in</Link>
          </p>
        )}
        {items.map((item) => (
          <article className="saved-search-row" key={item.id}>
            <div>
              <h2>
                <Link href={`/search?${new URLSearchParams(item.filters)}`}>
                  {item.name}
                </Link>
              </h2>
              <small>
                {item.email_alert
                  ? "Daily email alerts enabled"
                  : "Saved filters, without email alerts"}
              </small>
            </div>
            <div className="inline-actions">
              <Link
                className="btn-primary"
                href={`/search?${new URLSearchParams(item.filters)}`}
              >
                View matches
              </Link>
              <button
                className="btn-outline"
                onClick={async () => {
                  if (
                    !window.confirm(
                      "Delete this saved search and stop its alerts?",
                    )
                  )
                    return;
                  try {
                    await accountRequest(`saved-searches/${item.id}`, {
                      method: "DELETE",
                    });
                    setItems(items.filter((s) => s.id !== item.id));
                  } catch (e) {
                    setMessage((e as Error).message);
                  }
                }}
              >
                Delete
              </button>
            </div>
          </article>
        ))}
        {!items.length && (
          <p>
            Use <Link href="/search">job search</Link> to choose filters, then
            select Save this search.
          </p>
        )}
      </main>
      <Footer />
    </>
  );
}
