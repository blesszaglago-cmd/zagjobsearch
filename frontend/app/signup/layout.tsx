import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Create an account",
  description:
    "Browse jobs, internships and scholarships freely. Create your free jobs.ac.ghana account to apply at the source, track applications and manage follow-ups.",
  robots: { index: false, follow: true },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
