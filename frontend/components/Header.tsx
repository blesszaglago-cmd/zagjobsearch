import Link from "next/link";
import Logo from "./Logo";
export default function Header(){return <header className="site-header"><nav className="shell nav-inner" aria-label="Main navigation"><Logo/><div className="nav-links"><Link href="/search">Find jobs</Link><Link href="/#explore">Explore</Link><Link href="/#how-it-works">How it works</Link></div><div className="nav-actions"><Link href="/login">Log in</Link><Link href="/signup" className="btn-primary">Create account <span aria-hidden="true">↗</span></Link></div></nav></header>}
