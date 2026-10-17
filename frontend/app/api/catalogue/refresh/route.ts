import { API_URL } from "@/lib/api";
export const maxDuration = 180;
export async function GET(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret || request.headers.get("authorization") !== `Bearer ${secret}`)
    return Response.json({ detail: "Not authorised" }, { status: 401 });
  try {
    const r = await fetch(`${API_URL}/catalogue/refresh`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${secret}` },
      signal: AbortSignal.timeout(170000),
    });
    return new Response(await r.text(), {
      status: r.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return Response.json(
      { detail: "Catalogue refresh unavailable" },
      { status: 503 },
    );
  }
}
