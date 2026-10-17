import Link from "next/link";
import Logo from "./Logo";
import AccountNav from "./AccountNav";
export default function Header() {
  return (
    <header className="site-header">
      <nav className="shell nav-inner" aria-label="Main navigation">
        <Logo />
        <div className="nav-links">
          <Link href="/search">Find jobs</Link>
          <Link href="/tracker">Application tracker</Link>
          <Link href="/search?category=early&job_type=internship">
            Internships
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
        <Link href="/search?category=scholarships">Scholarships</Link>
      </nav>
    </header>
  );
}
