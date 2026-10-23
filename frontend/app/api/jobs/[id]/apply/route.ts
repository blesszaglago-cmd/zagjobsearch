import { getJob } from "@/lib/jobs-server";

function unavailable(request: Request, status: 410 | 503, detail: string) {
  const headers = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    Vary: "Accept",
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

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    const job = await getJob(id, true);
    if (!job || job.can_apply === false)
      return unavailable(
        request,
        410,
        "This opportunity is no longer open for applications.",
      );
    const target = new URL(job.url);
    if (target.protocol !== "https:") throw Error("Unsupported destination");
    return new Response(null, {
      status: 302,
      headers: {
        Location: target.toString(),
        "Cache-Control": "no-store",
        "X-Robots-Tag": "noindex, nofollow",
      },
    });
  } catch {
    return unavailable(
      request,
      503,
      "The original source could not confirm this posting. Please try again shortly.",
    );
  }
}
