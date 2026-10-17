import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Log in",
  description:
    "Log in to jobs.ac.ghana to manage your applications, update your job search records and keep your follow-up notes together.",
  robots: { index: false, follow: true },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
