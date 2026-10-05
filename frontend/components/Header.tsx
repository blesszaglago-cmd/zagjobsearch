import Link from "next/link";
import Logo from "./Logo";
import AccountNav from "./AccountNav";
export default function Header(){return <header className="site-header"><nav className="shell nav-inner" aria-label="Main navigation"><Logo/><div className="nav-links"><Link href="/search">Find jobs</Link><Link href="/tracker">Application tracker</Link><Link href="/cv">CV studio</Link></div><AccountNav/></nav></header>}
