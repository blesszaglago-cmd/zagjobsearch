import type { Metadata } from "next";
import { siteUrl } from "@/lib/site";
import "./globals.css";
import "./scholsec-theme.css";
import localFont from "next/font/local";
import AnalyticsConsent from "@/components/AnalyticsConsent";
const lato = localFont({
  src: [
    { path: "../public/fonts/lato-400.ttf", weight: "400" },
    { path: "../public/fonts/lato-700.ttf", weight: "700" },
    { path: "../public/fonts/lato-900.ttf", weight: "900" },
  ],
  variable: "--font-lato",
  display: "swap",
  preload: true,
});
const raleway = localFont({
  src: [
    { path: "../public/fonts/raleway-600.ttf", weight: "600" },
    { path: "../public/fonts/raleway-700.ttf", weight: "700" },
    { path: "../public/fonts/raleway-800.ttf", weight: "800" },
    { path: "../public/fonts/raleway-900.ttf", weight: "900" },
  ],
  variable: "--font-raleway",
  display: "swap",
  preload: false,
});
export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "jobs.ac.ghana | Jobs in Ghana & Application Tracker",
    template: "%s | jobs.ac.ghana",
  },
  description:
    "Find jobs across Ghana, internships, scholarships and remote roles accepting Ghana-based applicants. Track your applications with jobs.ac.ghana.",
  applicationName: "jobs.ac.ghana",
  openGraph: {
    type: "website",
    siteName: "jobs.ac.ghana",
    title: "jobs.ac.ghana | Your next move",
    description:
      "Discover jobs in Ghana, internships, scholarships and Ghana-eligible remote roles. Search freely. Apply directly.",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "jobs.ac.ghana, your next move",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "jobs.ac.ghana | Your next move",
    description: "Find jobs, internships and scholarships for Ghana.",
    images: ["/opengraph-image"],
  },
  robots: { index: true, follow: true },
  verification: {
    google:
      process.env.GOOGLE_SITE_VERIFICATION ||
      "ccdjXJLmlwLDVpjItOdDxzoHX-4mf1GiKsKJTl4U3xI",
    other: { "msvalidate.01": "819718EA799FB55CC8FC11E90BE4A7E6" },
  },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${lato.variable} ${raleway.variable}`}>
      <body>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        {children}
        <AnalyticsConsent />
      </body>
    </html>
  );
}
