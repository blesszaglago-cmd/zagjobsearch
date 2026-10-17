import Image from "next/image";
import Link from "next/link";
export default function Logo() {
  return (
    <Link href="/" className="brand brand-jobs" aria-label="jobs.ac.ghana home">
      <Image
        src="/brand/jobs-ac-ghana-mark.png"
        alt=""
        width={60}
        height={60}
        sizes="60px"
        priority
      />
      <span className="brand-wordmark">
        jobs.ac.<span>ghana</span>
      </span>
    </Link>
  );
}
