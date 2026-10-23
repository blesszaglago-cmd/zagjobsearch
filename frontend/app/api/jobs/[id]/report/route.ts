import { NextRequest } from "next/server";
import { API_URL } from "@/lib/api";
import { boundedBody, RequestBodyError } from "@/lib/request-body";
import { clientIpHeaders } from "@/lib/proxy-client";
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  if (request.headers.get("origin") !== request.nextUrl.origin)
    return Response.json({ detail: "Invalid request origin" }, { status: 403 });
  const { id } = await params;
  try {
    const body = await boundedBody(request, 12 * 1024);
    const endpoint = `/catalogue/${encodeURIComponent(id)}/report`;
    const r = await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...clientIpHeaders(request, "POST", endpoint),
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
    });
    if (r.status >= 500) throw Error("Provider unavailable");
    return Response.json(await r.json(), {
      status: r.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    if (error instanceof RequestBodyError)
      return Response.json(
        { detail: error.message },
        { status: error.status, headers: { "Cache-Control": "no-store" } },
      );
    return Response.json(
      { detail: "Report could not be saved. Please try again." },
      { status: 503 },
    );
  }
}
