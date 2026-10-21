import { NextRequest, NextResponse } from "next/server";
import { API_URL } from "@/lib/api";

const privateHeaders = {
  "Cache-Control": "private, no-store",
  Vary: "Cookie",
};

export async function GET(request: NextRequest) {
  const token = request.cookies.get("zag_session")?.value;
  if (!token)
    return NextResponse.json({ signed_in: false }, { headers: privateHeaders });

  try {
    const upstream = await fetch(`${API_URL}/account/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(25000),
    });
    if (upstream.status === 401)
      return NextResponse.json({ signed_in: false }, { headers: privateHeaders });
    if (!upstream.ok)
      return NextResponse.json(
        { detail: "Account service is unavailable. Please try again shortly." },
        { status: 503, headers: privateHeaders },
      );
    return NextResponse.json({ signed_in: true }, { headers: privateHeaders });
  } catch {
    return NextResponse.json(
      { detail: "Account service is unavailable. Please try again shortly." },
      { status: 503, headers: privateHeaders },
    );
  }
}
