import { NextRequest } from "next/server";
import { getJob, JobRequestError } from "@/lib/jobs-server";
import { clientIpHeaders } from "@/lib/proxy-client";
import { API_URL } from "@/lib/api";

function unavailable(request: Request, status: 410 | 503, detail: string) {
  const headers = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    Vary: "Accept, Cookie",
  };
  if (request.headers.get("accept")?.includes("text/html")) {
    const target = new URL("/application-unavailable", request.url);
    target.searchParams.set("reason", status === 410 ? "closed" : "temporary");
    return new Response(null, {
      status: 303,
      headers: { ...headers, Location: target.toString() },
    });
  }
  return Response.json({ detail }, { status, headers });
}

function accountRequired(request: NextRequest, id: string, expired = false) {
  const query = new URLSearchParams({ next: `/jobs/${id}` });
  const signup = `/signup?${query}`;
  const login = `/login?${query}`;
  const headers = {
    "Cache-Control": "private, no-store",
    "X-Robots-Tag": "noindex, nofollow",
    Vary: "Accept, Cookie",
  };
  if (request.headers.get("accept")?.includes("text/html")) {
    return new Response(null, {
      status: 303,
      headers: {
        ...headers,
        Location: new URL(expired ? login : signup, request.url).toString(),
      },
    });
  }
  return Response.json(
    {
      detail: "Create a free account or log in before applying.",
      signup_url: signup,
      login_url: login,
    },
    { status: 401, headers },
  );
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!/^[a-f0-9]{32}$/.test(id))
    return Response.json(
      { detail: "Listing not found." },
      { status: 404, headers: { "Cache-Control": "no-store" } },
    );
  const token = request.cookies.get("zag_session")?.value;
  if (!token) return accountRequired(request, id);
  try {
    const account = await fetch(`${API_URL}/account/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
        ...clientIpHeaders(request, "GET", "/account/me"),
      },
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (account.status === 401 || account.status === 403)
      return accountRequired(request, id, true);
    if (!account.ok) throw new Error("Account check unavailable");
    const job = await getJob(id, true, {
      Authorization: `Bearer ${token}`,
      ...clientIpHeaders(
        request,
        "GET",
        `/catalogue/${encodeURIComponent(id)}`,
      ),
    });
    if (!job || job.can_apply === false)
      return unavailable(
        request,
        410,
        "This opportunity is no longer open for applications.",
      );
    const target = new URL(job.url);
    if (
      target.protocol !== "https:" ||
      target.username ||
      target.password ||
      (target.port && target.port !== "443")
    )
      throw Error("Unsupported destination");
    return new Response(null, {
      status: 302,
      headers: {
        Location: target.toString(),
        "Cache-Control": "no-store",
        "X-Robots-Tag": "noindex, nofollow",
        Vary: "Cookie",
      },
    });
  } catch (error) {
    if (
      error instanceof JobRequestError &&
      (error.status === 401 || error.status === 403)
    )
      return accountRequired(request, id, true);
    return unavailable(
      request,
      503,
      "The original source could not confirm this posting. Please try again shortly.",
    );
  }
}
