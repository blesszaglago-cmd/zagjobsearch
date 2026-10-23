import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

const require = createRequire(import.meta.url);
const { NextRequest } = require("next/server");
const secret = "test-only-cron-key-012345678901234";
const listingId = "a".repeat(32);

function loadApply(upstream, accountStatus = 200) {
  return loadRoute("../app/api/jobs/[id]/apply/route.ts", (url, options) =>
    new URL(url).pathname === "/account/me"
      ? Response.json({}, { status: accountStatus })
      : upstream(url, options),
  );
}

function loadRoute(
  relative,
  fetchImpl = async () => {
    throw Error("Unexpected upstream call");
  },
  env = {},
) {
  const filename = fileURLToPath(new URL(relative, import.meta.url));
  const code = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const routeModule = { exports: {} };
  const localRequire = (id) => {
    if (id === "server-only") return {};
    if (id === "@/lib/api") return { API_URL: "https://backend.example" };
    if (id === "./api") return { API_URL: "https://backend.example" };
    if (id === "@/lib/jobs-server")
      return loadRoute("../lib/jobs-server.ts", fetchImpl, env);
    if (id === "@/lib/request-body")
      return loadRoute("../lib/request-body.ts", fetchImpl, env);
    if (id === "@/lib/proxy-client")
      return loadRoute("../lib/proxy-client.ts", fetchImpl, env);
    if (id === "@/lib/application-return")
      return loadRoute("../lib/application-return.ts", fetchImpl, env);
    if (id === "@/lib/cron-auth")
      return loadRoute("../lib/cron-auth.ts", fetchImpl, env);
    return require(id);
  };
  vm.runInNewContext(
    code,
    {
      require: localRequire,
      module: routeModule,
      exports: routeModule.exports,
      fetch: fetchImpl,
      process: { env: { NODE_ENV: "production", CRON_SECRET: secret, ...env } },
      Buffer,
      AbortSignal,
      Response,
      URL,
      URLSearchParams,
      Uint8Array,
      TextDecoder,
      ReadableStream,
    },
    { filename },
  );
  return routeModule.exports;
}

test("cron verification rejects malformed headers and missing configuration", () => {
  const { isCronAuthorized } = loadRoute("../lib/cron-auth.ts");
  assert.equal(isCronAuthorized(`Bearer ${secret}`), true);
  for (const value of [
    null,
    "",
    "Bearer wrong",
    `Bearer ${"é".repeat(secret.length)}`,
  ]) {
    assert.equal(isCronAuthorized(value), false);
  }
  const unconfigured = loadRoute("../lib/cron-auth.ts", undefined, {
    CRON_SECRET: "",
  });
  assert.equal(unconfigured.isCronAuthorized("Bearer "), false);
});

for (const file of [
  "../app/api/reminders/route.ts",
  "../app/api/catalogue/refresh/route.ts",
]) {
  test(`${file}: malformed auth cannot reach maintenance operations`, async () => {
    let calls = 0;
    const route = loadRoute(file, async () => {
      calls++;
      throw Error("Unexpected request");
    });
    const request = new NextRequest("https://site.example/api/private", {
      headers: { authorization: `Bearer ${"é".repeat(secret.length)}` },
    });
    assert.equal((await route.GET(request)).status, 401);
    assert.equal(calls, 0);
  });
}

test("account changes reject a different website origin before calling the backend", async () => {
  let calls = 0;
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => {
    calls++;
  });
  const response = await route.POST(
    new NextRequest("https://site.example/api/account/applications", {
      method: "POST",
      headers: {
        origin: "https://untrusted.example",
        cookie: "zag_session=test-only",
      },
      body: "{}",
    }),
    { params: Promise.resolve({ path: ["applications"] }) },
  );
  assert.equal(response.status, 403);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(calls, 0);
});

test("protected account reads reject guests without querying the backend", async () => {
  let calls = 0;
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => {
    calls++;
  });
  for (const path of ["me", "applications", "settings", "saved-searches"]) {
    const response = await route.GET(
      new NextRequest(`https://site.example/api/account/${path}`),
      {
        params: Promise.resolve({ path: [path] }),
      },
    );
    assert.equal(response.status, 401);
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
  assert.equal(calls, 0);
});

test("account upstream failures remain private and cannot be cached", async () => {
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => {
    throw Error("test-only-private-provider-detail");
  });
  const response = await route.POST(
    new NextRequest("https://site.example/api/account/signup", {
      method: "POST",
      headers: {
        origin: "https://site.example",
        "content-type": "application/json",
      },
      body: "{}",
    }),
    { params: Promise.resolve({ path: ["signup"] }) },
  );
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.deepEqual(await response.json(), {
    detail: "Account service is unavailable. Please try again shortly.",
  });
});

test("login keeps its session token in a secure HttpOnly cookie", async () => {
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () =>
    Response.json({
      access_token: "test-only-signed-session",
      user_id: "test-owner",
      message: "Login successful",
    }),
  );
  const response = await route.POST(
    new NextRequest("https://site.example/api/account/login", {
      method: "POST",
      headers: {
        origin: "https://site.example",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        email: "test-only@example.com",
        password: "test-only-password",
      }),
    }),
    { params: Promise.resolve({ path: ["login"] }) },
  );
  assert.equal(response.status, 200);
  assert.equal((await response.json()).access_token, undefined);
  const cookie = response.headers.get("set-cookie");
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /Secure/);
  assert.match(cookie, /SameSite=lax/);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("invalid catalogue filters keep their actionable 400 response", async () => {
  const route = loadRoute("../app/api/jobs/route.ts", async () =>
    Response.json(
      {
        detail: "Enter a valid page and salary range.",
      },
      { status: 400 },
    ),
  );
  const response = await route.GET(
    new NextRequest("https://site.example/api/jobs?salary_min=-1"),
  );
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), {
    detail: "Enter a valid page and salary range.",
  });
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("catalogue provider and connection failures never disclose upstream details", async () => {
  for (const upstream of [
    async () =>
      Response.json(
        { detail: "test-only-private-database-error" },
        { status: 500 },
      ),
    async () => {
      throw Error("test-only-private-network-error");
    },
  ]) {
    const route = loadRoute("../app/api/jobs/route.ts", upstream);
    const response = await route.GET(
      new NextRequest("https://site.example/api/jobs"),
    );
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.doesNotMatch(await response.text(), /test-only-private/);
  }
});

test("catalogue filters reach the backend intact without the retired country option", async () => {
  let target;
  const route = loadRoute("../app/api/jobs/route.ts", async (url) => {
    target = new URL(url);
    return Response.json({ jobs: [], total: 0, page: 2, has_more: false });
  });
  const response = await route.GET(
    new NextRequest(
      "https://site.example/api/jobs?category=scholarships&source=daad-ghana&salary_period=month&page=2&country=US",
    ),
  );
  assert.equal(response.status, 200);
  assert.equal(target.searchParams.get("source"), "daad-ghana");
  assert.equal(target.searchParams.get("salary_period"), "month");
  assert.equal(target.searchParams.get("page"), "2");
  assert.equal(target.searchParams.has("country"), false);
});

test("tracker validation messages reach the person editing their application", async () => {
  const workspace = loadRoute("../lib/workspace.ts", async () =>
    Response.json(
      {
        detail: [
          { msg: "The maximum salary must be at least the minimum salary." },
        ],
      },
      { status: 422 },
    ),
  );
  await assert.rejects(workspace.accountRequest("applications"), (error) => {
    assert.equal(error.status, 422);
    assert.match(error.message, /maximum salary/);
    return true;
  });
});

test("non-JSON account errors provide a usable retry message", async () => {
  const workspace = loadRoute(
    "../lib/workspace.ts",
    async () => new Response("<h1>Unavailable</h1>", { status: 503 }),
  );
  await assert.rejects(workspace.accountRequest("applications"), (error) => {
    assert.equal(error.status, 503);
    assert.equal(error.message, "Could not complete this request.");
    return true;
  });
});

test("closed and temporarily unavailable Apply responses cannot be cached", async () => {
  for (const status of [404, 503]) {
    const route = loadApply(async () =>
      Response.json({ detail: "Unavailable" }, { status }),
    );
    const response = await route.GET(
      new NextRequest(`https://site.example/api/jobs/${listingId}/apply`, {
        headers: { cookie: "zag_session=test-only" },
      }),
      { params: Promise.resolve({ id: listingId }) },
    );
    assert.equal(response.status, status === 404 ? 410 : 503);
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
});

test("browser Apply failures lead to a friendly page while JSON clients keep their status", async () => {
  for (const status of [404, 503]) {
    const route = loadApply(async () =>
      Response.json({ detail: "Unavailable" }, { status }),
    );
    const request = new NextRequest(
      `https://site.example/api/jobs/${listingId}/apply`,
      {
        headers: {
          accept: "text/html,application/xhtml+xml",
          cookie: "zag_session=test-only",
        },
      },
    );
    const response = await route.GET(request, {
      params: Promise.resolve({ id: listingId }),
    });
    assert.equal(response.status, 303);
    assert.equal(
      response.headers.get("location"),
      `https://site.example/application-unavailable?reason=${status === 404 ? "closed" : "temporary"}`,
    );
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("x-robots-tag"), "noindex, nofollow");
    assert.equal(response.headers.get("vary"), "Accept, Cookie");
  }
});

test("browser Apply still redirects directly to a confirmed external posting", async () => {
  const route = loadApply(async () =>
    Response.json({
      id: "test",
      can_apply: true,
      url: "https://employer.example/jobs/123",
    }),
  );
  const request = new NextRequest(
    `https://site.example/api/jobs/${listingId}/apply`,
    {
      headers: { accept: "text/html", cookie: "zag_session=test-only" },
    },
  );
  const response = await route.GET(request, {
    params: Promise.resolve({ id: listingId }),
  });
  assert.equal(response.status, 302);
  assert.equal(
    response.headers.get("location"),
    "https://employer.example/jobs/123",
  );
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("chunked account bodies cannot bypass the size cap with a false Content-Length", async () => {
  let calls = 0;
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => {
    calls++;
  });
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(40000));
      controller.enqueue(new Uint8Array(40000));
      controller.close();
    },
  });
  const request = new NextRequest("https://site.example/api/account/login", {
    method: "POST",
    headers: { origin: "https://site.example", "content-length": "1" },
    body,
    duplex: "half",
  });
  const response = await route.POST(request, {
    params: Promise.resolve({ path: ["login"] }),
  });
  assert.equal(response.status, 413);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(calls, 0);
});

test("compressed account submissions are rejected before contacting the API", async () => {
  let calls = 0;
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => {
    calls++;
  });
  const response = await route.POST(
    new NextRequest("https://site.example/api/account/login", {
      method: "POST",
      headers: { origin: "https://site.example", "content-encoding": "gzip" },
      body: "test-only",
    }),
    { params: Promise.resolve({ path: ["login"] }) },
  );
  assert.equal(response.status, 415);
  assert.equal(calls, 0);
});

test("a failed OAuth state check clears the old PKCE cookies without exchanging a code", async () => {
  let calls = 0;
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => {
    calls++;
  });
  const response = await route.GET(
    new NextRequest(
      "https://site.example/api/account/google/callback?code=fake&state=attacker",
      {
        headers: {
          cookie: "zag_oauth_state=owner-state; zag_pkce=owner-verifier",
        },
      },
    ),
    { params: Promise.resolve({ path: ["google", "callback"] }) },
  );
  assert.equal(new URL(response.headers.get("location")).pathname, "/login");
  assert.match(response.headers.get("set-cookie"), /zag_pkce=;/);
  assert.match(response.headers.get("set-cookie"), /zag_oauth_state=;/);
  assert.equal(calls, 0);
});

test("visitor IP forwarding uses the platform header and a route-bound signature", () => {
  const { clientIpHeaders } = loadRoute("../lib/proxy-client.ts", undefined, {
    VERCEL: "1",
    INTERNAL_PROXY_SECRET: "test-only-proxy-secret",
  });
  const request = new NextRequest("https://site.example/api/account/login", {
    headers: {
      "x-vercel-forwarded-for": "8.8.8.8",
      "x-forwarded-for": "attacker-input",
    },
  });
  const result = clientIpHeaders(request, "POST", "/login");
  assert.equal(result["X-Zag-Client-IP"], "8.8.8.8");
  const { createHmac } = require("node:crypto");
  const expected = createHmac("sha256", "test-only-proxy-secret")
    .update(
      [
        "zagjobsearch/client-ip/v1",
        result["X-Zag-Client-Time"],
        "POST",
        "/login",
        "8.8.8.8",
      ].join("\n"),
    )
    .digest("hex");
  assert.equal(result["X-Zag-Client-Signature"], expected);
  assert.notEqual(
    clientIpHeaders(request, "POST", "/signup")["X-Zag-Client-Signature"],
    expected,
  );
  const local = loadRoute("../lib/proxy-client.ts", undefined, {
    VERCEL: "",
    INTERNAL_PROXY_SECRET: "test-only-proxy-secret",
  });
  assert.deepEqual(
    Object.keys(local.clientIpHeaders(request, "POST", "/login")),
    [],
  );
});

test("Apply refuses URLs with credentials, insecure schemes or unusual ports", async () => {
  for (const url of [
    "https://owner:password@employer.example/job",
    "https://employer.example:8443/job",
    "javascript:alert(1)",
    "http://employer.example/job",
  ]) {
    const route = loadApply(async () =>
      Response.json({ can_apply: true, url }),
    );
    const response = await route.GET(
      new NextRequest(`https://site.example/api/jobs/${listingId}/apply`, {
        headers: { cookie: "zag_session=test-only" },
      }),
      { params: Promise.resolve({ id: listingId }) },
    );
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("location"), null);
  }
});

test("guest Apply requires an account without fetching the posting", async () => {
  let calls = 0;
  const route = loadApply(async () => {
    calls++;
    throw Error("Guest must not reach source verification");
  });
  const context = { params: Promise.resolve({ id: listingId }) };
  const browser = await route.GET(
    new NextRequest(`https://site.example/api/jobs/${listingId}/apply`, {
      headers: { accept: "text/html" },
    }),
    context,
  );
  assert.equal(browser.status, 303);
  const target = new URL(browser.headers.get("location"));
  assert.equal(target.origin, "https://site.example");
  assert.equal(target.pathname, "/signup");
  assert.equal(target.searchParams.get("next"), `/jobs/${listingId}`);
  assert.equal(browser.headers.get("cache-control"), "private, no-store");
  const json = await route.GET(
    new NextRequest(`https://site.example/api/jobs/${listingId}/apply`),
    context,
  );
  assert.equal(json.status, 401);
  assert.match((await json.json()).login_url, /^\/login\?/);
  assert.equal(calls, 0);
});

test("Apply forwards the session for server validation and expired sessions return to login", async () => {
  for (const status of [200, 401, 403]) {
    let calls = 0;
    const route = loadApply(async (url, options) => {
      calls++;
      assert.equal(new URL(url).pathname, `/catalogue/${listingId}`);
      assert.equal(new URL(url).searchParams.get("verify"), "true");
      assert.equal(options.headers.Authorization, "Bearer test-only-session");
      return Response.json(
        { can_apply: true, url: "https://employer.example/open-role" },
        { status },
      );
    });
    const response = await route.GET(
      new NextRequest(`https://site.example/api/jobs/${listingId}/apply`, {
        headers: {
          accept: "text/html",
          cookie: "zag_session=test-only-session",
        },
      }),
      { params: Promise.resolve({ id: listingId }) },
    );
    const target = new URL(response.headers.get("location"));
    if (status === 200) {
      assert.equal(response.status, 302);
      assert.equal(target.toString(), "https://employer.example/open-role");
    } else {
      assert.equal(response.status, 303);
      assert.equal(target.pathname, "/login");
      assert.equal(target.searchParams.get("next"), `/jobs/${listingId}`);
    }
    assert.equal(calls, 1);
  }
});

test("account continuations cannot become external redirects or protected actions", () => {
  const { applicationReturnPath } = loadRoute("../lib/application-return.ts");
  assert.equal(
    applicationReturnPath(`/jobs/${listingId}`),
    `/jobs/${listingId}`,
  );
  for (const value of [
    null,
    "https://untrusted.example/",
    "//untrusted.example/",
    "/\\untrusted.example",
    "/api/reminders",
    `/jobs/${listingId}?next=https://untrusted.example/`,
    `/jobs/${listingId}\n`,
    "javascript:alert(1)",
  ])
    assert.equal(applicationReturnPath(value), undefined);
});

test("a forged cookie or unavailable account service cannot reach Apply verification", async () => {
  for (const accountStatus of [401, 403, 500]) {
    let sourceCalls = 0;
    const route = loadApply(async () => {
      sourceCalls++;
      throw Error("Source must not be called");
    }, accountStatus);
    const response = await route.GET(
      new NextRequest(`https://site.example/api/jobs/${listingId}/apply`, {
        headers: { cookie: "zag_session=forged" },
      }),
      { params: Promise.resolve({ id: listingId }) },
    );
    assert.equal(response.status, accountStatus === 500 ? 503 : 401);
    assert.equal(sourceCalls, 0);
    assert.equal(response.headers.get("location"), null);
  }
});

test("successful OAuth resumes only a safe listing and clears continuation cookies", async () => {
  for (const next of [`/jobs/${listingId}`, "//untrusted.example/"]) {
    const route = loadRoute(
      "../app/api/account/[...path]/route.ts",
      async (url) => {
        if (url.endsWith("/auth/config"))
          return Response.json({
            supabase_url: "https://auth.example",
            publishable_key: "test-only-public-key",
          });
        if (url.includes("/auth/v1/token"))
          return Response.json({ access_token: "test-only-provider-token" });
        return Response.json({
          access_token: "test-only-session",
          onboarding_complete: true,
        });
      },
    );
    const response = await route.GET(
      new NextRequest(
        "https://site.example/api/account/google/callback?state=matching-state&code=test-only-code",
        {
          headers: {
            cookie: `zag_oauth_state=matching-state; zag_pkce=test-only-verifier; zag_oauth_next=${encodeURIComponent(next)}`,
          },
        },
      ),
      { params: Promise.resolve({ path: ["google", "callback"] }) },
    );
    assert.equal(response.status, 307);
    assert.equal(
      response.headers.get("location"),
      `https://site.example${next.startsWith("/jobs/") ? next : "/tracker"}`,
    );
    assert.match(response.headers.get("set-cookie"), /zag_oauth_next=;/);
  }
});

test("report requests have a streaming limit and hide upstream server errors", async () => {
  const route = loadRoute("../app/api/jobs/[id]/report/route.ts", async () =>
    Response.json(
      { detail: "test-only-private-database-reply" },
      { status: 500 },
    ),
  );
  const makeRequest = (body) =>
    new NextRequest("https://site.example/api/jobs/test/report", {
      method: "POST",
      headers: { origin: "https://site.example" },
      body,
    });
  const context = { params: Promise.resolve({ id: listingId }) };
  const large = await route.POST(makeRequest("x".repeat(13000)), context);
  assert.equal(large.status, 413);
  const failed = await route.POST(makeRequest('{"reason":"closed"}'), context);
  assert.equal(failed.status, 503);
  assert.doesNotMatch(await failed.text(), /test-only-private/);
});

test("browser policy blocks inline event handlers, plugins, frames and base-tag injection", async () => {
  const config = loadRoute("../next.config.ts").default;
  const groups = await config.headers();
  const csp = groups[0].headers.find(
    (header) => header.key === "Content-Security-Policy",
  ).value;
  for (const directive of [
    "script-src-attr 'none'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    "form-action 'self'",
  ])
    assert.ok(csp.includes(directive));
  assert.ok(!csp.includes("unsafe-eval"));
});
