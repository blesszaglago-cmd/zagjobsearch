import AuthForm from "@/components/AuthForm";
import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Account assistance",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export default function Page() {
  return <AuthForm mode="recovery" />;
}
