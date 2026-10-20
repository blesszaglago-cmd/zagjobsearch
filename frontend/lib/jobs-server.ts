import "server-only";
import { cache } from "react";
import { API_URL } from "./api";
import type { Job } from "./jobs";
export const getSearchResult = cache(async function getSearchResult(
  query: string,
) {
  const p = new URLSearchParams(query);
  p.delete("country");
  const r = await fetch(`${API_URL}/catalogue?${p}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!r.ok) throw new Error("The Ghana catalogue is temporarily unavailable.");
  return r.json();
});
export async function searchJobs(params: URLSearchParams) {
  return getSearchResult(params.toString());
}
export const getJob = cache(async function getJob(
  id: string,
  verify = false,
): Promise<Job | undefined> {
  const r = await fetch(
    `${API_URL}/catalogue/${encodeURIComponent(id)}${verify ? "?verify=true" : ""}`,
    {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    },
  );
  if (r.status === 404 || r.status === 410) return;
  if (!r.ok)
    throw new Error("The original source could not confirm this opportunity.");
  return r.json();
});
