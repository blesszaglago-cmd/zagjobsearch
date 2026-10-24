import type { Metadata } from "next";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import CookieSettingsButton from "@/components/CookieSettingsButton";
export const metadata: Metadata = {
  title: "Cookie Policy",
  description:
    "Understand jobs.ac.ghana session cookies, temporary sign-in cookies and optional Google Analytics, and learn how to manage your cookie preferences.",
  alternates: { canonical: "/cookies" },
};
const content =
  "# Cookie Policy\n\nLast updated: October 24, 2026\n\njobs.ac.ghana uses essential cookies for account security and cookie preferences. Optional Google Analytics stays off until you accept it. Rejecting optional cookies does not prevent browsing, creating an account or applying after sign-in.\n\n## Essential cookies\n\nzag_session is an HttpOnly sign-in cookie lasting up to 12 hours. Logging out revokes account sessions on the server. zag_pkce, zag_oauth_state and zag_oauth_next protect optional Google sign-in and return you to your selected listing. They expire after 10 minutes. Account cookies use SameSite=Lax and Secure in production.\n\nzag_cookie_consent remembers your analytics choice, policy version and the time you chose for up to 180 days. It does not contain your account ID, email or application information. It is limited to this website, uses SameSite=Lax and Secure on HTTPS, and is readable by our cookie controls so they can apply your choice.\n\nSaved searches and application records belong to your account in the database. They are not stored in analytics cookies.\n\n## Optional analytics\n\nAccept all or enabling Optional analytics in Manage preferences permits Google Analytics. It measures public page views and fixed actions such as Apply, sign-in, saving and sharing. We exclude search query parameters, URL fragments, private-page URLs, names, emails and application contents. Google may process device, browser, approximate location and the origin of a referring website. Advertising features are disabled.\n\nAnalytics cookies include _ga and _ga_3N6T2M5ED8, configured to expire after 180 days without extending that period on each visit. They are created only after you opt in. No advertising cookies or session replay are installed.\n\n## Browser preferences\n\nThe localStorage item zag_cookie_consent_sync signals preference changes to other tabs. It contains only the same choice, version and timestamp and cannot enable analytics without a valid consent cookie. The old zag_analytics_consent_v1 setting no longer enables analytics and is removed when you save a new choice. Existing visitors are asked to choose again.\n\nAn expired or invalid choice keeps analytics off and shows the banner again. If your browser blocks saving the preference, your choice applies to the current page only and the site displays a notice. You may be asked again on your next visit.\n\n## Your control\n\nUse Cookie settings at the bottom of any page or the button on this policy page to reopen your preferences. Essential cookies are always on. Accept all enables optional analytics; Reject optional or saving with the analytics switch off disables it. Closing the preferences without saving does not change your choice.\n\nWithdrawing permission disables analytics and clears this site's analytics cookies. It does not clear sign-in cookies or reload the page, so application edits stay in place. Active tabs synchronize saved choices; expiry is checked on navigation, focus and at least once a minute while the page is open. Clearing browser data signs you out and resets preferences. External application websites manage their own cookies under their policies.\n\n## Contact\n\nBless Mawumenyo Zaglago \u00b7 blesszaglago@gmail.com\n";
export default function Page() {
  return (
    <>
      <Header />
      <main id="main-content" className="shell legal-page">
        <h1>Cookie Policy</h1>
        <CookieSettingsButton className="btn-primary">
          Manage cookie preferences
        </CookieSettingsButton>
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
