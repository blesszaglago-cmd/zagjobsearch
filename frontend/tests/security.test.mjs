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
    const route = loadRoute("../app/api/jobs/[id]/apply/route.ts", async () =>
      Response.json({ detail: "Unavailable" }, { status }),
    );
    const response = await route.GET(
      new Request("https://site.example/api/jobs/test/apply"),
      { params: Promise.resolve({ id: "test" }) },
    );
    assert.equal(response.status, status === 404 ? 410 : 503);
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
});

test("browser Apply failures lead to a friendly page while JSON clients keep their status", async () => {
  for (const status of [404, 503]) {
    const route = loadRoute("../app/api/jobs/[id]/apply/route.ts", async () =>
      Response.json({ detail: "Unavailable" }, { status }),
    );
    const request = new Request("https://site.example/api/jobs/test/apply", {
      headers: { accept: "text/html,application/xhtml+xml" },
    });
    const response = await route.GET(request, {
      params: Promise.resolve({ id: "test" }),
    });
    assert.equal(response.status, 303);
    assert.equal(
      response.headers.get("location"),
      `https://site.example/application-unavailable?reason=${status === 404 ? "closed" : "temporary"}`,
    );
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("x-robots-tag"), "noindex, nofollow");
    assert.equal(response.headers.get("vary"), "Accept");
  }
});

test("browser Apply still redirects directly to a confirmed external posting", async () => {
  const route = loadRoute("../app/api/jobs/[id]/apply/route.ts", async () =>
    Response.json({
      id: "test",
      can_apply: true,
      url: "https://employer.example/jobs/123",
    }),
  );
  const request = new Request("https://site.example/api/jobs/test/apply", {
    headers: { accept: "text/html" },
  });
  const response = await route.GET(request, {
    params: Promise.resolve({ id: "test" }),
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
    const route = loadRoute("../app/api/jobs/[id]/apply/route.ts", async () =>
      Response.json({ can_apply: true, url }),
    );
    const response = await route.GET(
      new Request("https://site.example/api/jobs/test/apply"),
      { params: Promise.resolve({ id: "test" }) },
    );
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("location"), null);
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
  const context = { params: Promise.resolve({ id: "test" }) };
  const large = await route.POST(makeRequest("x".repeat(13000)), context);
  assert.equal(large.status, 413);
  const failed = await route.POST(makeRequest('{"reason":"closed"}'), context);
  assert.equal(failed.status, 503);
  assert.doesNotMatch(await failed.text(), /test-only-private/);
});

test("browser policy blocks inline event handlers, plugins, frames and base-tag injection", async () => {
  const config = loadRoute("../next.config.ts").default;
  const groups = await config.headers();
  const csp = groups[0].headers.find((header) => header.key === "Content-Security-Policy").value;
  for (const directive of ["script-src-attr 'none'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'none'", "form-action 'self'"])
    assert.ok(csp.includes(directive));
  assert.ok(!csp.includes("unsafe-eval"));
});
