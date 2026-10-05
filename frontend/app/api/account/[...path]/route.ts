import { NextRequest, NextResponse } from "next/server";
import { createHash, randomBytes } from "node:crypto";
import { API_URL } from "@/lib/api";
const cookieOptions = { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax" as const, path: "/", maxAge: 43200 };
const allowed = /^(me|applications(?:\/[a-zA-Z0-9-]+(?:\/events)?)?|profile|cv\/(extract|prepare|cover-letter|export)|login|signup|logout|google(?:\/callback)?|config)$/;
async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const name = path.join("/");
  if (!allowed.test(name)) return NextResponse.json({ detail: "Not found" }, { status: 404 });
  if (request.method !== "GET" && request.headers.get("origin") !== request.nextUrl.origin) return NextResponse.json({ detail: "Invalid request origin" }, { status: 403 });
  if (name === "logout") {
    if (request.method !== "POST") return new Response(null, { status: 405 });
    const response = NextResponse.json({ logged_out: true }); response.cookies.delete("zag_session"); return response;
  }
  try {
    if (name === "google" && request.method === "GET") {
      const configResponse = await fetch(`${API_URL}/auth/config`, { cache: "no-store" });
      const config = await configResponse.json();
      if (!config.google_enabled) return NextResponse.redirect(new URL("/login?error=google_setup", request.url));
      const verifier = randomBytes(32).toString("base64url"); const state = randomBytes(24).toString("hex");
      const callback = `${request.nextUrl.origin}/api/account/google/callback?state=${state}`;
      const target = new URL(`${config.supabase_url}/auth/v1/authorize`);
      target.search = new URLSearchParams({ provider: "google", redirect_to: callback, code_challenge: createHash("sha256").update(verifier).digest("base64url"), code_challenge_method: "s256" }).toString();
      const response = NextResponse.redirect(target); response.cookies.set("zag_pkce", verifier, { ...cookieOptions, maxAge: 600 }); response.cookies.set("zag_oauth_state", state, { ...cookieOptions, maxAge: 600 }); return response;
    }
    let endpoint = `${API_URL}/${["login", "signup"].includes(name) ? name : name === "config" ? "auth/config" : `account/${name}`}`;
    let body: BodyInit | undefined;
    let headers: Record<string, string> = {};
    let method = request.method;
    if (name === "google/callback" && request.method === "GET") {
      const state = request.cookies.get("zag_oauth_state")?.value;
      const verifier = request.cookies.get("zag_pkce")?.value;
      const code = request.nextUrl.searchParams.get("code");
      if (!state || state !== request.nextUrl.searchParams.get("state") || !verifier || !code) return NextResponse.redirect(new URL("/login?error=google_failed", request.url));
      const config = await (await fetch(`${API_URL}/auth/config`, { cache: "no-store" })).json();
      const tokens = await fetch(`${config.supabase_url}/auth/v1/token?grant_type=pkce`, { method: "POST", headers: { "Content-Type": "application/json", apikey: config.publishable_key }, body: JSON.stringify({ auth_code: code, code_verifier: verifier }) });
      if (!tokens.ok) return NextResponse.redirect(new URL("/login?error=google_failed", request.url));
      const session = await tokens.json(); endpoint = `${API_URL}/auth/google`; method = "POST"; headers = { "Content-Type": "application/json" }; body = JSON.stringify({ access_token: session.access_token });
    } else {
      if (!["login", "signup", "config"].includes(name)) {
        const token = request.cookies.get("zag_session")?.value;
        if (!token) return NextResponse.json({ detail: "Log in to use this feature." }, { status: 401 });
        headers.Authorization = `Bearer ${token}`;
      }
      if (request.method !== "GET") { const size = Number(request.headers.get("content-length") || 0); if (size > 6 * 1024 * 1024) return NextResponse.json({ detail: "File too large" }, { status: 413 }); const bytes = await request.arrayBuffer(); if(bytes.byteLength > 6 * 1024 * 1024) return NextResponse.json({detail:"File too large"},{status:413}); body = bytes; headers["Content-Type"] = request.headers.get("content-type") || "application/json"; }
    }
    const upstream = await fetch(endpoint, { method, headers, body, cache: "no-store", signal: AbortSignal.timeout(25000) });
    if (name === "cv/export" && upstream.ok) return new Response(await upstream.arrayBuffer(), { headers: { "Content-Type": upstream.headers.get("content-type") || "application/octet-stream", "Content-Disposition": upstream.headers.get("content-disposition") || "attachment", "Cache-Control": "no-store" } });
    if(name === "google/callback" && !upstream.ok) return NextResponse.redirect(new URL("/login?error=google_failed",request.url));
    const data = await upstream.json();
    const token = data.access_token; delete data.access_token;
    if(name === "login" && upstream.ok && !token) return NextResponse.json({detail:"The account API needs the workspace update. Please try again once setup is complete."},{status:503});
    const response = name === "google/callback" && upstream.ok ? NextResponse.redirect(new URL("/tracker", request.url)) : NextResponse.json(data, { status: upstream.status, headers: { "Cache-Control": "no-store" } });
    if (token && upstream.ok) response.cookies.set("zag_session", token, cookieOptions);
    if (name === "google/callback") { response.cookies.delete("zag_pkce"); response.cookies.delete("zag_oauth_state"); }
    return response;
  } catch { return NextResponse.json({ detail: "Account service is unavailable. Please try again shortly." }, { status: 503 }); }
}
export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const DELETE = handle;
