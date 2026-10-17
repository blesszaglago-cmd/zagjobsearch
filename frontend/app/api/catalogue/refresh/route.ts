import { API_URL } from "@/lib/api";
export const maxDuration = 180;
export async function GET() {
  try {
    const r = await fetch(`${API_URL}/catalogue/refresh`, {
      cache: "no-store",
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
