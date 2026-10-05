import Image from "next/image";
import Link from "next/link";
export default function Logo(){return <Link href="/" className="brand brand-monogram" aria-label="ZagJobSearch home"><Image src="/images/zb-logo.webp" alt="ZB, ZagJobSearch" width={1536} height={1024} priority /></Link>}
