import "server-only";
import { API_URL } from "./api";
import type { Job } from "./jobs";
export async function searchJobs(params: URLSearchParams) {
  const p = new URLSearchParams(params);
  p.delete("country");
  const r = await fetch(`${API_URL}/catalogue?${p}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!r.ok) throw new Error("The Ghana catalogue is temporarily unavailable.");
  return r.json();
}
export async function getJob(id: string): Promise<Job | undefined> {
  const r = await fetch(`${API_URL}/catalogue/${encodeURIComponent(id)}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (r.status === 404 || r.status === 410) return;
  if (!r.ok)
    throw new Error("The original source could not confirm this opportunity.");
  return r.json();
}
