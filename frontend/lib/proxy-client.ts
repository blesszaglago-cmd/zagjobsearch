import "server-only";
import { createHmac } from "node:crypto";
import { isIP } from "node:net";

// Vercel replaces this platform header. Do not trust a caller's arbitrary XFF.
export function clientIpHeaders(
  request: Request,
  method: string,
  path: string,
): Record<string, string> {
  const address = process.env.VERCEL
    ? request.headers.get("x-vercel-forwarded-for")?.trim()
    : undefined;
  const secret = process.env.INTERNAL_PROXY_SECRET;
  if (!address || !isIP(address) || !secret) return {};
  const stamp = String(Math.floor(Date.now() / 1000));
  const signature = createHmac("sha256", secret)
    .update(
      ["zagjobsearch/client-ip/v1", stamp, method, path, address].join("\n"),
    )
    .digest("hex");
  return {
    "X-Zag-Client-IP": address,
    "X-Zag-Client-Time": stamp,
    "X-Zag-Client-Signature": signature,
  };
}
