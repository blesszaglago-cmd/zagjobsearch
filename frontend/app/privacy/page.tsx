import type { Metadata } from "next";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "Learn how jobs.ac.ghana handles account information, application records and optional analytics, and how to manage your data.",
  alternates: { canonical: "/privacy" },
};
const content =
  "# Privacy Policy\n\nLast updated: October 24, 2026\n\njobs.ac.ghana is an independent Ghana opportunity search and application tracker operated by Bless Mawumenyo Zaglago at zagjobsearch.vercel.app. It is not a government service.\n\n## Information we use\n\nAccounts contain your name, email address, country, password hash and account verification state. New registration asks you to confirm that you are at least 13 and accept the Terms; it does not store a new date of birth. Dates of birth supplied by older accounts remain part of those accounts until deletion. Google sign-in, when configured, also stores the provider's user identifier and verified email.\n\nYour private workspace contains the application fields, notes, contacts, deadlines and reminder choices you enter, plus status history. Saved searches store the filters you choose. Search keywords are used to answer the current search; they are not added to an account history unless you save that search. Avoid including unnecessary sensitive personal information in notes.\n\nCV assistance is retired. New CV uploads and text updates are disabled. Previously saved career-profile text remains available for deletion in Settings; it is not used for job matching or analytics.\n\nProblem reports contain the selected listing, reason, optional text and time. Do not put sensitive information in reports. Abuse prevention stores hashed rate-limit identifiers rather than a raw IP address in our rate-limit table. Hosting providers may separately keep operational request logs.\n\n## How information is used\n\nWe provide search, sign-in, your application tracker and saved searches. Email verification, recovery, deadline reminders and saved-search alerts work only when an email provider is configured. Reminder and search emails require your opt-in and a verified email address; you can disable reminders or delete a saved search. Recovery and verification links expire after 30 minutes and are single use.\n\nWe do not sell your personal information. Public sponsor enquiries do not give sponsors access to applicant records. Applying opens a source website governed by its own policies; saving an application here does not submit it to an employer.\n\n## Providers\n\nVercel hosts the website and API. Supabase stores application data and supports optional Google sign-in. Public Ghana boards, official employer feeds and the Ghana Scholarships Authority provide attributed opportunity information. Google processes sign-in information when enabled, and optional Analytics after consent. A configured SMTP provider processes emails we send. Each provider has its own policies.\n\n## Optional analytics\n\nGoogle Analytics loads only after you accept optional analytics through the cookie controls. Public page views exclude search parameters and URL fragments. With that same consent, fixed events measure sign-ups, logins, Apply clicks, saved applications, saved searches and sharing. We do not send names, emails, CV text, application notes, application contents or private-page URLs. Advertising features are disabled. Device, browser, approximate location, referring website origin and a limited campaign-source label may be processed. Your cookie choice lasts up to 180 days on this browser. Change it through Cookie settings at the bottom of any page. Withdrawing permission disables analytics and clears its cookies without signing you out. Google's privacy policy is https://policies.google.com/privacy.\n\n## Your controls\n\nSettings lets you correct your name and country, change a password, request a verified email change, sign out other sessions, export application records as CSV, delete old career-profile text and delete your account. Some email actions require configured delivery. Contact blesszaglago@gmail.com for other access, correction or data requests, including existing date-of-birth data. Account deletion requires confirmation and a password or a recent verified Google sign-in.\n\n## Retention and protection\n\nAccount data is retained while the account is active. An application removed in the tracker is hidden immediately and can be restored using Undo; scheduled cleanup permanently removes it after 30 days. Account deletion removes the active account and its linked workspace records. Transient email queue records are retained for up to seven days; expired account tokens and rate-limit records are removed by scheduled cleanup. Hosting logs and provider backups have their own retention schedules. Any separately encrypted operational backup requires restricted access and a defined retention period; deleted records can remain there until it expires.\n\nPasswords are hashed. Private database tables use row-level security and service-only access; authenticated API requests enforce ownership. Session cookies are HttpOnly and secure in production. No session replay is installed. No system can promise absolute security.\n\n## Children and policy changes\n\nThis service is for people aged 13 or older. Registration requires age confirmation; it is not independent identity or age verification. Contact us if an underage account is discovered. We publish policy changes on this page.\n\n## Contact\n\nBless Mawumenyo Zaglago \u00b7 Ghana\nblesszaglago@gmail.com\n";
export default function Page() {
  return (
    <>
      <Header />
      <main id="main-content" className="shell legal-page">
        <h1>Privacy Policy</h1>
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
