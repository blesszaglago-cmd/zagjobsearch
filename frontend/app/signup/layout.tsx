import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Create an account",
  description:
    "Create your jobs.ac.ghana account to track applications and manage follow-ups. Browse job listings and apply at the source without an account.",
  robots: { index: false, follow: true },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
