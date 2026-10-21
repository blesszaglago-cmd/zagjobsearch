import "server-only";
import { timingSafeEqual } from "node:crypto";

export function isCronAuthorized(authorization: string | null) {
  const secret = process.env.CRON_SECRET;
  if (!secret || !authorization) return false;
  const expected = Buffer.from(`Bearer ${secret}`);
  const actual = Buffer.from(authorization);
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}
