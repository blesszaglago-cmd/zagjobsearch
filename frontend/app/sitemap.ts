import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site";
import { API_URL } from "@/lib/api";
import { getCoverage, regionSlug } from "@/lib/coverage";
export const dynamic = "force-dynamic";
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const urls: MetadataRoute.Sitemap = [
    "",
    "/search",
    "/sources",
    "/about",
    "/sponsor",
    "/privacy",
    "/terms",
    "/cookies",
  ].map((path) => ({
    url: `${siteUrl}${path}`,
    changeFrequency: "weekly",
    priority: path ? 0.5 : 1,
  }));
  const coverage = await getCoverage();
  for (const [region, count] of Object.entries(coverage?.regions || {}))
    if (count > 0)
      urls.push({
        url: `${siteUrl}/regions/${regionSlug(region)}`,
        changeFrequency: "daily",
        priority: 0.7,
      });
  try {
    let offset = 0;
    while (offset < 49000) {
      const r = await fetch(`${API_URL}/catalogue/sitemap?offset=${offset}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      });
      if (!r.ok) break;
      const data = await r.json();
      for (const job of data.jobs || [])
        urls.push({
          url: `${siteUrl}/jobs/${job.id}`,
          lastModified: new Date(job.updated_at),
          changeFrequency: "daily",
          priority: 0.8,
        });
      if (!data.has_more) break;
      offset = data.next_offset;
    }
  } catch {
    /* Keep static discovery links available during API maintenance. */
  }
  return urls;
}
