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

function loadRoute(relative, fetchImpl = async () => { throw Error("Unexpected upstream call"); }, env = {}) {
  const filename = fileURLToPath(new URL(relative, import.meta.url));
  const code = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const routeModule = { exports: {} };
  const localRequire = (id) => {
    if (id === "server-only") return {};
    if (id === "@/lib/api") return { API_URL: "https://backend.example" };
    if (id === "@/lib/cron-auth") return loadRoute("../lib/cron-auth.ts", fetchImpl, env);
    return require(id);
  };
  vm.runInNewContext(code, {
    require: localRequire, module: routeModule, exports: routeModule.exports, fetch: fetchImpl,
    process: { env: { NODE_ENV: "production", CRON_SECRET: secret, ...env } },
    Buffer, AbortSignal, Response, URL,
  }, { filename });
  return routeModule.exports;
}

test("cron verification rejects malformed headers and missing configuration", () => {
  const { isCronAuthorized } = loadRoute("../lib/cron-auth.ts");
  assert.equal(isCronAuthorized(`Bearer ${secret}`), true);
  for (const value of [null, "", "Bearer wrong", `Bearer ${"é".repeat(secret.length)}`]) {
    assert.equal(isCronAuthorized(value), false);
  }
  const unconfigured = loadRoute("../lib/cron-auth.ts", undefined, { CRON_SECRET: "" });
  assert.equal(unconfigured.isCronAuthorized("Bearer "), false);
});

for (const file of ["../app/api/reminders/route.ts", "../app/api/catalogue/refresh/route.ts"]) {
  test(`${file}: malformed auth cannot reach maintenance operations`, async () => {
    let calls = 0;
    const route = loadRoute(file, async () => { calls++; throw Error("Unexpected request"); });
    const request = new NextRequest("https://site.example/api/private", {
      headers: { authorization: `Bearer ${"é".repeat(secret.length)}` },
    });
    assert.equal((await route.GET(request)).status, 401);
    assert.equal(calls, 0);
  });
}

test("account changes reject a different website origin before calling the backend", async () => {
  let calls = 0;
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => { calls++; });
  const response = await route.POST(new NextRequest("https://site.example/api/account/applications", {
    method: "POST", headers: { origin: "https://untrusted.example", cookie: "zag_session=test-only" }, body: "{}",
  }), { params: Promise.resolve({ path: ["applications"] }) });
  assert.equal(response.status, 403);
  assert.equal(calls, 0);
});

test("protected account reads reject guests without querying the backend", async () => {
  let calls = 0;
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => { calls++; });
  for (const path of ["me", "applications", "settings", "saved-searches"]) {
    const response = await route.GET(new NextRequest(`https://site.example/api/account/${path}`), {
      params: Promise.resolve({ path: [path] }),
    });
    assert.equal(response.status, 401);
  }
  assert.equal(calls, 0);
});

test("login keeps its session token in a secure HttpOnly cookie", async () => {
  const route = loadRoute("../app/api/account/[...path]/route.ts", async () => Response.json({
    access_token: "test-only-signed-session", user_id: "test-owner", message: "Login successful",
  }));
  const response = await route.POST(new NextRequest("https://site.example/api/account/login", {
    method: "POST", headers: { origin: "https://site.example", "content-type": "application/json" },
    body: JSON.stringify({ email: "test-only@example.com", password: "test-only-password" }),
  }), { params: Promise.resolve({ path: ["login"] }) });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).access_token, undefined);
  const cookie = response.headers.get("set-cookie");
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /Secure/);
  assert.match(cookie, /SameSite=lax/);
  assert.equal(response.headers.get("cache-control"), "no-store");
});
