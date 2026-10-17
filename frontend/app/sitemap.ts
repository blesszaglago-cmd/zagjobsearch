import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site";
export default function sitemap():MetadataRoute.Sitemap{return ["","/sources","/privacy","/terms","/cookies"].map(path=>({url:`${siteUrl}${path}`,changeFrequency:"monthly",priority:path?0.3:1}));}
