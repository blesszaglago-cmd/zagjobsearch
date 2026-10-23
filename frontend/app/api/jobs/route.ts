import { NextRequest } from "next/server";
import { CatalogueRequestError, searchJobs } from "@/lib/jobs-server";

export async function GET(request: NextRequest) {
  try {
    return Response.json(await searchJobs(request.nextUrl.searchParams));
  } catch (error) {
    return Response.json(
      {
        detail:
          error instanceof CatalogueRequestError
            ? error.message
            : "The Ghana catalogue is temporarily unavailable. Please try again shortly.",
      },
      {
        status: error instanceof CatalogueRequestError ? error.status : 503,
        headers: { "Cache-Control": "no-store" },
      },
    );
  }
}
