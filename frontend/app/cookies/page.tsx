import type { Metadata } from "next";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
export const metadata: Metadata = {
  title: "Cookie Policy",
  description:
    "Understand jobs.ac.ghana session cookies, temporary sign-in cookies and optional Google Analytics, and learn how to change your analytics choice.",
  alternates: { canonical: "/cookies" },
};
const content =
  "# Cookie Policy\n\nLast updated: October 17, 2026\n\njobs.ac.ghana uses essential sign-in storage and optional analytics.\n\n## Essential storage\n\nzag_session is an HttpOnly sign-in cookie lasting up to 12 hours. Logging out revokes account sessions on the server. zag_pkce and zag_oauth_state protect optional Google sign-in and expire after 10 minutes. Essential cookies use SameSite=Lax and Secure in production.\n\nSaved searches and application records belong to your account in the database. CV assistance is retired and no new CV text is accepted.\n\n## Optional analytics\n\nGoogle Analytics loads only after Allow analytics. It measures public page views and fixed actions such as Apply, sign-in, saving and sharing. We exclude search query parameters, URL fragments, private-page URLs, names, emails and application contents. Google may process device, browser, approximate location and the origin of a referring website.\n\nAnalytics cookies include _ga and _ga_3N6T2M5ED8, configured to expire after six months. Your choice is stored on this browser in localStorage as zag_analytics_consent_v1. Declining keeps analytics off. Withdrawing consent clears the analytics cookies used by this site and reloads the page to unload the script.\n\n## Your control\n\nUse Analytics settings at the bottom of any page to change your choice. Clearing browser data signs you out and resets preferences. No advertising cookies or session replay are installed.\n\n## Contact\n\nBless Mawumenyo Zaglago \u00b7 blesszaglago@gmail.com\n";
export default function Page() {
  return (
    <>
      <Header />
      <main id="main-content" className="shell legal-page">
        <h1>Cookie Policy</h1>
        <div className="legal-copy">
          {content
            .split("\n")
            .slice(1)
            .map((line, i) =>
              line.startsWith("## ") ? (
                <h2 key={i}>{line.slice(3)}</h2>
              ) : (
                <p key={i}>{line.replace(/\*\*/g, "")}</p>
              ),
            )}
        </div>
      </main>
      <Footer />
    </>
  );
}
