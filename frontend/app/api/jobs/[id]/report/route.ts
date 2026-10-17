import { NextRequest } from "next/server";
import { API_URL } from "@/lib/api";
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  if (request.headers.get("origin") !== request.nextUrl.origin)
    return Response.json({ detail: "Invalid request origin" }, { status: 403 });
  const { id } = await params;
  try {
    const text = await request.text();
    if (text.length > 5000)
      return Response.json({ detail: "Report is too long" }, { status: 413 });
    const r = await fetch(
      `${API_URL}/catalogue/${encodeURIComponent(id)}/report`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-forwarded-for":
            request.headers.get("x-vercel-forwarded-for") ||
            request.headers.get("x-forwarded-for") ||
            "unknown",
        },
        body: text,
        signal: AbortSignal.timeout(12000),
      },
    );
    return Response.json(await r.json(), { status: r.status });
  } catch {
    return Response.json(
      { detail: "Report could not be saved. Please try again." },
      { status: 503 },
    );
  }
}
