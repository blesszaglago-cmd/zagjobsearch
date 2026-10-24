import Link from "next/link";
import Logo from "./Logo";
export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="shell portal-footer-grid">
        <div>
          <Logo />
          <p>
            Website: zagjobsearch.vercel.app. Connecting your ambition with the
            next opportunity. Jobs, internships and scholarships, with Ghana at
            the centre.
          </p>
        </div>
        <div>
          <h2>Find your opportunity</h2>
          <nav aria-label="Footer opportunities">
            <Link href="/search?category=jobs">Jobs in Ghana</Link>
            <Link href="/search?category=early&job_type=internship">
              Internships & early careers
            </Link>
            <Link href="/search?category=remote">Remote from Ghana</Link>
            <Link href="/search?category=scholarships">Scholarships</Link>
            <Link href="/sources">Where our listings come from</Link>
          </nav>
        </div>
        <div>
          <h2>Your next step</h2>
          <nav aria-label="Footer account and policies">
            <Link href="/tracker">Application tracker</Link>
            <Link href="/saved-searches">Saved searches</Link>
            <Link href="/about">About this platform</Link>
            <Link href="/sponsor">Employer & sponsorship enquiries</Link>
            <Link href="/signup">Create an account</Link>
            <Link href="/privacy">Privacy policy</Link>
            <Link href="/terms">Terms of use</Link>
            <Link href="/cookies">Cookie policy</Link>
          </nav>
        </div>
      </div>
      <div className="shell portal-footer-note">
        Independent opportunity platform. jobs.ac.ghana is not a government
        agency and is not affiliated with the Ghana Scholarships Authority.{" "}
        <details>
          <summary>Photography credits</summary>
          <p>
            Professional photography:{" "}
            <a
              href="https://nappy.co/photo/wocintech-microsoft-225+K_HF7htJUu_2JlJ3sPocz"
              target="_blank"
              rel="noopener noreferrer"
            >
              WOCInTech / Nappy (CC0)
            </a>
            . Ghana student photography:{" "}
            <a
              href="https://unsplash.com/photos/jDXMQf3LPX8"
              target="_blank"
              rel="noopener noreferrer"
            >
              Creab ThePolymath / Unsplash
            </a>
            . Office photography via Unsplash. Images illustrate work and study;
            people pictured are not presented as jobs.ac.ghana users or
            endorsers.
          </p>
        </details>
      </div>
      <div className="shell footer-bottom">
        <span>
          © {new Date().getFullYear()} jobs.ac.ghana. Built by Bless Zaglago.
        </span>
        <span>Rooted in Ghana. Made for your next move.</span>
      </div>
    </footer>
  );
}
