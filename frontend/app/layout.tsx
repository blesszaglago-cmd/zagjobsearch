import type { Metadata } from "next";
import { siteUrl } from "@/lib/site";
import "./globals.css";
import AnalyticsConsent from "@/components/AnalyticsConsent";
export const metadata: Metadata = {
 metadataBase: new URL(siteUrl),
 title: {default: "ZagJobSearch | Jobs in Ghana & Application Tracker", template: "%s | ZagJobSearch"},
 description: "Find jobs across Ghana, internships, scholarships and remote roles accepting Ghana-based applicants. Track your applications with ZagJobSearch.",
 applicationName: "ZagJobSearch",
 openGraph: {type:"website",siteName:"ZagJobSearch",title:"ZagJobSearch | Your next move",description:"Discover jobs in Ghana, internships, scholarships and Ghana-eligible remote roles. Search freely. Apply directly.",images:[{url:"/opengraph-image",width:1200,height:630,alt:"ZagJobSearch, your next move"}]},
 twitter: {card:"summary_large_image",title:"ZagJobSearch | Your next move",description:"Find jobs, internships and scholarships for Ghana.",images:["/opengraph-image"]},
 robots: {index:true,follow:true},
 verification: {
  google:process.env.GOOGLE_SITE_VERIFICATION || "ccdjXJLmlwLDVpjItOdDxzoHX-4mf1GiKsKJTl4U3xI",
  other: {"msvalidate.01": "819718EA799FB55CC8FC11E90BE4A7E6"},
 },
};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><a className="skip-link" href="#main-content">Skip to content</a>{children}<AnalyticsConsent/></body></html>}
