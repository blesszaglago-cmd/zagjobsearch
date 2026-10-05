import type { Metadata } from "next";
import { siteUrl } from "@/lib/site";
import "./globals.css";
export const metadata: Metadata = {
 metadataBase: new URL(siteUrl),
 title: {default: "ZagJobSearch | Find Local & Remote Jobs", template: "%s | ZagJobSearch"},
 description: "Find your next role with ZagJobSearch. Explore local and remote jobs from multiple sources, filter by country, and apply directly at the original listing.",
 applicationName: "ZagJobSearch",
 openGraph: {type:"website",siteName:"ZagJobSearch",title:"ZagJobSearch | Your next move",description:"Discover local and remote jobs in one place. Search freely. Apply directly.",images:[{url:"/opengraph-image",width:1200,height:630,alt:"ZagJobSearch, your next move"}]},
 twitter: {card:"summary_large_image",title:"ZagJobSearch | Your next move",description:"Discover local and remote jobs in one place.",images:["/opengraph-image"]},
 robots: {index:true,follow:true},
 verification: {google:process.env.GOOGLE_SITE_VERIFICATION},
};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><a className="skip-link" href="#main-content">Skip to content</a>{children}</body></html>}
