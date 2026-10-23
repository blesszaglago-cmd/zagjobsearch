import Link from "next/link";
import Logo from "./Logo";
import AccountNav from "./AccountNav";
export default function Header() {
  return (
    <header className="site-header">
      <div className="portal-topbar">
        <div className="shell">
          <span>
            <span className="ghana-flag" role="img" aria-label="Ghana flag" />
            Independent Ghana opportunity platform.
          </span>
          <span>Browse freely. Sign in to apply.</span>
        </div>
      </div>
      <nav className="shell nav-inner" aria-label="Main navigation">
        <Logo />
        <div className="nav-links">
          <Link href="/">Home</Link>
          <Link href="/search">Find jobs</Link>
          <Link href="/tracker">Tracker</Link>
          <Link href="/search?category=early&job_type=internship">
            Internships
          </Link>
          <Link href="/search?category=scholarships">
            Scholarships & research
          </Link>
        </div>
        <AccountNav />
      </nav>
      <nav className="shell gh-mobile-nav" aria-label="Mobile navigation">
        <Link href="/search">Find jobs</Link>
        <Link href="/search?category=early&job_type=internship">
          Internships
        </Link>
        <Link href="/tracker">Tracker</Link>
        <Link href="/search?category=scholarships">
          Scholarships & research
        </Link>
      </nav>
    </header>
  );
}
