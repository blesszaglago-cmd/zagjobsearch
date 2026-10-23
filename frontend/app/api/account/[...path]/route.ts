import { NextRequest, NextResponse } from "next/server";
import { createHash, randomBytes } from "node:crypto";
import { API_URL } from "@/lib/api";
import { boundedBody, RequestBodyError } from "@/lib/request-body";
import { clientIpHeaders } from "@/lib/proxy-client";
import { applicationReturnPath } from "@/lib/application-return";
const cookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: 43200,
};
const allowed =
  /^(me|applications(?:\/[a-zA-Z0-9-]+(?:\/(?:events|restore))?)?|profile|settings|password|email|verify-email|export|saved-searches(?:\/[a-zA-Z0-9-]+)?|recovery|complete|login|signup|logout|google(?:\/callback)?|config)$/;
async function handle(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const name = path.join("/");
  if (!allowed.test(name))
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  if (
    request.method !== "GET" &&
    request.headers.get("origin") !== request.nextUrl.origin
  )
    return NextResponse.json(
      { detail: "Invalid request origin" },
      { status: 403 },
    );
  try {
    if (name === "google" && request.method === "GET") {
      const configResponse = await fetch(`${API_URL}/auth/config`, {
        cache: "no-store",
      });
      const config = await configResponse.json();
      if (!config.google_enabled)
        return NextResponse.redirect(
          new URL("/login?error=google_setup", request.url),
        );
      const verifier = randomBytes(32).toString("base64url");
      const state = randomBytes(24).toString("hex");
      const callback = `${request.nextUrl.origin}/api/account/google/callback?state=${state}`;
      const target = new URL(`${config.supabase_url}/auth/v1/authorize`);
      target.search = new URLSearchParams({
        provider: "google",
        redirect_to: callback,
        code_challenge: createHash("sha256")
          .update(verifier)
          .digest("base64url"),
        code_challenge_method: "s256",
      }).toString();
      const response = NextResponse.redirect(target);
      response.cookies.set("zag_pkce", verifier, {
        ...cookieOptions,
        maxAge: 600,
      });
      response.cookies.set("zag_oauth_state", state, {
        ...cookieOptions,
        maxAge: 600,
      });
      const nextPath = applicationReturnPath(
        request.nextUrl.searchParams.get("next"),
      );
      if (nextPath)
        response.cookies.set("zag_oauth_next", nextPath, {
          ...cookieOptions,
          maxAge: 600,
        });
      else response.cookies.delete("zag_oauth_next");
      return response;
    }
    let endpoint = `${API_URL}/${["login", "signup"].includes(name) ? name : ["config", "recovery", "complete"].includes(name) ? `auth/${name}` : `account/${name}`}`;
    let body: BodyInit | undefined;
    let headers: Record<string, string> = {};
    let method = request.method;
    if (name === "google/callback" && request.method === "GET") {
      const state = request.cookies.get("zag_oauth_state")?.value;
      const verifier = request.cookies.get("zag_pkce")?.value;
      const code = request.nextUrl.searchParams.get("code");
      if (
        !state ||
        state !== request.nextUrl.searchParams.get("state") ||
        !verifier ||
        !code
      )
        return NextResponse.redirect(
          new URL("/login?error=google_failed", request.url),
        );
      const config = await (
        await fetch(`${API_URL}/auth/config`, { cache: "no-store" })
      ).json();
      const tokens = await fetch(
        `${config.supabase_url}/auth/v1/token?grant_type=pkce`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            apikey: config.publishable_key,
          },
          body: JSON.stringify({ auth_code: code, code_verifier: verifier }),
        },
      );
      if (!tokens.ok)
        return NextResponse.redirect(
          new URL("/login?error=google_failed", request.url),
        );
      const session = await tokens.json();
      endpoint = `${API_URL}/auth/google`;
      method = "POST";
      headers = { "Content-Type": "application/json" };
      body = JSON.stringify({ access_token: session.access_token });
    } else {
      if (
        !["login", "signup", "config", "recovery", "complete"].includes(name)
      ) {
        const token = request.cookies.get("zag_session")?.value;
        if (!token)
          return NextResponse.json(
            { detail: "Log in to use this feature." },
            { status: 401 },
          );
        headers.Authorization = `Bearer ${token}`;
      }
      if (request.method !== "GET") {
        body = await boundedBody(request);
        headers["Content-Type"] =
          request.headers.get("content-type") || "application/json";
      }
    }
    headers = {
      ...headers,
      ...clientIpHeaders(request, method, new URL(endpoint).pathname),
    };
    const upstream = await fetch(endpoint, {
      method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(25000),
    });
    if (name === "google/callback" && !upstream.ok)
      return NextResponse.redirect(
        new URL("/login?error=google_failed", request.url),
      );
    if (name === "export" && upstream.ok)
      return new Response(await upstream.text(), {
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition":
            'attachment; filename="jobs-ac-ghana-applications.csv"',
          "Cache-Control": "no-store",
        },
      });
    const data = await upstream.json();
    const token = data.access_token;
    delete data.access_token;
    if (name === "login" && upstream.ok && !token)
      return NextResponse.json(
        {
          detail:
            "The account API needs the workspace update. Please try again once setup is complete.",
        },
        { status: 503 },
      );
    const response =
      name === "google/callback" && upstream.ok
        ? NextResponse.redirect(
            new URL(
              data.onboarding_complete === false
                ? "/settings?setup=1"
                : applicationReturnPath(
                    request.cookies.get("zag_oauth_next")?.value,
                  ) || "/tracker",
              request.url,
            ),
          )
        : NextResponse.json(data, {
            status: upstream.status,
            headers: { "Cache-Control": "no-store" },
          });
    if (
      upstream.ok &&
      (name === "logout" ||
        name === "password" ||
        (name === "settings" && request.method === "DELETE"))
    )
      response.cookies.delete("zag_session");
    if (token && upstream.ok)
      response.cookies.set("zag_session", token, cookieOptions);
    if (name === "google/callback") {
      response.cookies.delete("zag_pkce");
      response.cookies.delete("zag_oauth_state");
      response.cookies.delete("zag_oauth_next");
    }
    return response;
  } catch (error) {
    if (error instanceof RequestBodyError)
      return NextResponse.json(
        { detail: error.message },
        { status: error.status },
      );
    return NextResponse.json(
      { detail: "Account service is unavailable. Please try again shortly." },
      { status: 503 },
    );
  }
}
async function accountHandler(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const response = await handle(request, context);
  response.headers.set("Cache-Control", "no-store");
  if (
    request.nextUrl.pathname === "/api/account/google/callback" &&
    response instanceof NextResponse
  ) {
    response.cookies.delete("zag_pkce");
    response.cookies.delete("zag_oauth_state");
    response.cookies.delete("zag_oauth_next");
  }
  return response;
}
export const GET = accountHandler;
export const POST = accountHandler;
export const PUT = accountHandler;
export const DELETE = accountHandler;
