import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

function load(name, fetchImpl) {
  const code = ts.transpileModule(
    readFileSync(new URL(`../lib/${name}.ts`, import.meta.url), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
  const mod = { exports: {} };
  vm.runInNewContext(code, {
    module: mod,
    exports: mod.exports,
    require: (id) => {
      if (id === "server-only") return {};
      if (id === "@/lib/api") return { API_URL: "https://backend.example" };
      throw Error(`Unexpected import: ${id}`);
    },
    fetch: fetchImpl,
    AbortSignal,
    Date,
    URL,
  });
  return mod.exports;
}
const job = (n, category = "jobs", extra = {}) => ({
  id: n.toString(16).padStart(32, "0"),
  title: "Engineer",
  company: "Test employer",
  category,
  ...extra,
});

test("homepage preview uses bounded cached public requests and mixes roles with funding", async () => {
  const calls = [];
  const { homeOpportunities } = load(
    "home-opportunities",
    async (url, options) => {
      calls.push({ url, options });
      return Response.json({
        jobs:
          new URL(url).searchParams.get("category") === "jobs"
            ? [job(1), job(2), job(3)]
            : [job(4, "scholarships")],
      });
    },
  );
  const result = await homeOpportunities();
  assert.deepEqual(
    Array.from(result.jobs, (j) => j.id),
    [1, 2, 4].map((n) => job(n).id),
  );
  assert.equal(result.unavailable, false);
  assert.equal(calls.length, 2);
  for (const { url, options } of calls) {
    assert.equal(new URL(url).searchParams.get("availability"), "open");
    assert.equal(options.next.revalidate, 60);
    assert.ok(options.signal instanceof AbortSignal);
    assert.equal(options.headers, undefined);
    assert.equal(options.credentials, undefined);
  }
});

test("one failed source preserves the other preview and both failures stay generic", async () => {
  let allFail = false;
  const { homeOpportunities } = load("home-opportunities", async (url) => {
    if (allFail || new URL(url).searchParams.get("category") === "jobs")
      throw Error("private provider error");
    return Response.json({ jobs: [job(4, "scholarships")] });
  });
  assert.equal((await homeOpportunities()).jobs.length, 1);
  allFail = true;
  const result = await homeOpportunities();
  assert.equal(result.jobs.length, 0);
  assert.equal(result.unavailable, true);
  assert.ok(!JSON.stringify(result).includes("private"));
});

test("preview excludes expired, malformed, closed or mismatched records", async () => {
  const { homeOpportunities } = load("home-opportunities", async (url) =>
    Response.json({
      jobs:
        new URL(url).searchParams.get("category") === "jobs"
          ? [
              job(1, "jobs", { deadline: "2000-01-01" }),
              job(2, "jobs", { deadline: "not a date" }),
              job(3, "jobs", { can_apply: false }),
              job(4, "early"),
              null,
              job(5, "jobs", { title: " " }),
              job(6, "jobs", { id: "../../../account" }),
              job(7),
            ]
          : [],
    }),
  );
  const result = await homeOpportunities();
  assert.deepEqual(
    Array.from(result.jobs, (j) => j.id),
    [job(7).id],
  );
});

test("empty responses differ from unavailable or malformed responses", async () => {
  for (const [response, unavailable] of [
    [() => Response.json({ jobs: [] }), false],
    [() => Response.json({ jobs: {} }), true],
    [() => new Response("upstream private text", { status: 503 }), true],
  ]) {
    const result = await load("home-opportunities", async () =>
      response(),
    ).homeOpportunities();
    assert.equal(result.unavailable, unavailable);
  }
});

test("source explanations use only known categories and safe bounded counts", () => {
  const { sourceMessages } = load("source-status");
  const messages = sourceMessages({
    queued_checks: 9000,
    diagnostics: {
      http_429: 1,
      validation: 1,
      budget: 2,
      "private injected text": 1,
    },
  });
  assert.ok(messages.some((m) => m.includes("640")));
  assert.ok(messages.some((m) => m.includes("publisher")));
  assert.ok(messages.some((m) => m.includes("formats")));
  assert.ok(!JSON.stringify(messages).includes("private"));
  assert.equal(
    sourceMessages({ diagnostics: { http_403: -1, timeout: NaN } }).length,
    0,
  );
  assert.ok(
    sourceMessages({ failure: { kind: "http", status: 403 } }).some((m) =>
      m.includes("refused"),
    ),
  );
});
