import { getJob } from "@/lib/jobs-server";
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    const job = await getJob(id, true);
    if (!job || job.can_apply === false)
      return Response.json(
        { detail: "This opportunity is no longer open for applications." },
        { status: 410, headers: { "Cache-Control": "no-store" } },
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
    return Response.json(
      {
        detail:
          "The original source could not confirm this posting. Please try again shortly.",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
