import "server-only";
import { cache } from "react";
import { API_URL } from "./api";
import type { Job } from "./jobs";
export class CatalogueRequestError extends Error {
  constructor(
    message: string,
    public readonly status: 400 | 503,
  ) {
    super(message);
    this.name = "CatalogueRequestError";
  }
}
export const getSearchResult = cache(async function getSearchResult(
  query: string,
) {
  const p = new URLSearchParams(query);
  p.delete("country");
  const r = await fetch(`${API_URL}/catalogue?${p}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (r.status === 400) {
    const data = await r.json().catch(() => null);
    throw new CatalogueRequestError(
      typeof data?.detail === "string"
        ? data.detail
        : "Check your search filters and try again.",
      400,
    );
  }
  if (!r.ok)
    throw new CatalogueRequestError(
      "The Ghana catalogue is temporarily unavailable. Please try again shortly.",
      503,
    );
  return r.json();
});
export async function searchJobs(params: URLSearchParams) {
  return getSearchResult(params.toString());
}
export const getJob = cache(async function getJob(
  id: string,
  verify = false,
  verificationHeaders?: Record<string, string>,
): Promise<Job | undefined> {
  const r = await fetch(
    `${API_URL}/catalogue/${encodeURIComponent(id)}${verify ? "?verify=true" : ""}`,
    {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
      headers: verify ? verificationHeaders : undefined,
    },
  );
  if (r.status === 404 || r.status === 410) return;
  if (!r.ok)
    throw new Error("The original source could not confirm this opportunity.");
  return r.json();
});
