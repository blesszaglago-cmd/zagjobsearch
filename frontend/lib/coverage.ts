import "server-only";
import { cache } from "react";
import { API_URL } from "./api";
export type Coverage = {
  categories: Record<string, number>;
  regions: Record<string, number>;
  updated_at?: string;
  healthy: boolean;
  last_error?: string;
  sources_with_listings: number;
};
export const getCoverage = cache(async (): Promise<Coverage | null> => {
  try {
    const r = await fetch(`${API_URL}/catalogue/coverage`, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(12000),
    });
    return r.ok ? r.json() : null;
  } catch {
    return null;
  }
});
export function regionSlug(region: string) {
  return region.toLowerCase().replaceAll(" ", "-");
}
