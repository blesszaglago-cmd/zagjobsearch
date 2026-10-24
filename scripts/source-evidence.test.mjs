import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  truncateSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  inspectNetwork,
  inspectScript,
  compareNetwork,
} from "./source-evidence.mjs";

const scope = ["https://source.example"];
const record = (url, status = 200, method = "GET") => ({
  request: { url, method },
  response: {
    status,
    content: { mimeType: "application/json; charset=utf-8" },
  },
});
const capture = (...entries) => ({ log: { version: "1.2", entries } });

test("network evidence groups observed IDs and parameter names without retaining secret values", () => {
  const result = inspectNetwork(
    capture(
      {
        ...record(
          "https://source.example/api/jobs/123?page=1&token=secret-token",
        ),
        request: {
          method: "GET",
          url: "https://source.example/api/jobs/123?page=1&token=secret-token",
          headers: [{ name: "Authorization", value: "secret-auth" }],
          cookies: [{ name: "session", value: "secret-cookie" }],
        },
        response: {
          status: 200,
          content: {
            mimeType: "application/json",
            text: '{"private":"secret-body"}',
          },
        },
      },
      record("https://source.example/api/jobs/456?page=2", 503),
    ),
    scope,
  );
  assert.equal(result.surfaces.length, 1);
  const group = result.surfaces[0];
  assert.equal(group.path_template, "/api/jobs/{numeric}");
  assert.deepEqual(group.statuses, [200, 503]);
  assert.deepEqual(group.query_names, ["page", "token"]);
  assert.deepEqual(group.record_ordinals, [0, 1]);
  assert.equal(group.template_basis, "format-inference");
  assert.doesNotMatch(JSON.stringify(result), /secret-|123|456|Authorization/);
});

test("only selected origins are included; malformed URLs and credentials remain excluded", () => {
  const result = inspectNetwork(
    capture(
      record("https://source.example/jobs"),
      record("https://unselected.example/jobs?private=secret"),
      record("https://owner:secret@source.example/jobs"),
      record("javascript:secret"),
      record("https://source.example/jobs", 200, "unknown method"),
      {},
    ),
    scope,
  );
  assert.deepEqual(result.records, { supplied: 6, included: 1, excluded: 5 });
  assert.equal(result.exclusions["outside-selected-origins"], 1);
  assert.equal(result.exclusions["unusable-or-credential-bearing-url"], 3);
  assert.doesNotMatch(JSON.stringify(result), /unselected|owner|secret/);
});

test("REA format rules distinguish UUIDs, hashes and actual dates, preserving raw dot paths", () => {
  const result = inspectNetwork(
    capture(
      record(
        "https://source.example/items/123e4567-e89b-12d3-a456-426614174000",
      ),
      record("https://source.example/items/" + "a".repeat(32)),
      record("https://source.example/dates/2026-10-24"),
      record("https://source.example/dates/2026-02-30"),
      record("https://source.example/a/../jobs"),
    ),
    scope,
  );
  const paths = result.surfaces.map((group) => group.path_template);
  for (const path of [
    "/items/{uuid}",
    "/items/{hex}",
    "/dates/{iso-date}",
    "/dates/2026-02-30",
    "/a/../jobs",
  ])
    assert.ok(paths.includes(path));
});

test("token and email path values and unsafe query names are masked", () => {
  const result = inspectNetwork(
    capture(
      record("https://source.example/reset/short-secret"),
      record(
        "https://source.example/user/person%40example.com?email%40example.com=secret",
      ),
      record("https://source.example/" + "x".repeat(100)),
    ),
    scope,
  );
  assert.doesNotMatch(
    JSON.stringify(result),
    /short-secret|person|example.com|x{10}/,
  );
  assert.ok(
    result.surfaces.every((group) =>
      group.path_template.includes("{redacted}"),
    ),
  );
});

test("missing responses stay unknown and metadata-only observations preserve provenance", () => {
  const result = inspectNetwork(
    {
      format: "public-source-observations-v1",
      observations: [
        {
          request: { method: "GET", url: "https://source.example/jobs" },
          failure: "TimeoutError",
        },
      ],
    },
    scope,
  );
  assert.deepEqual(result.surfaces[0].statuses, []);
  assert.equal(result.surfaces[0].unknown_responses, 1);
  assert.equal(result.records.included, 1);
});

test("network analysis rejects missing scope, inappropriate input and oversized inventories", () => {
  for (const allowed of [
    [],
    ["https://source.example/path"],
    ["https://secret@source.example"],
    ["file:///tmp/source"],
  ])
    assert.throws(() => inspectNetwork(capture(), allowed));
  for (const input of [
    {},
    { log: { entries: {} } },
    capture(...Array(50_001).fill({})),
  ])
    assert.throws(() => inspectNetwork(input, scope));
});

test("JavaScript discovery parses literal candidates without executing the source", () => {
  globalThis.__source_evidence_executed = false;
  const source = `
    globalThis.__source_evidence_executed = true;
    fetch('/api/' + 'jobs?page=2&token=secret-value', { method: 'POST' });
    axios.get('https://api.source.example/jobs');
    axios.post('/applications');
    const client = { baseURL: 'https://api.source.example/v1/' };
    fetch(dynamicValue);
    const unknown = { baseURL: process.env.API_URL };
    // fetch('/comment-only');
    const text = "fetch('/string-only')";
    new Map().get('/not-a-request');
  `;
  const result = inspectScript(source, "https://source.example/");
  assert.equal(globalThis.__source_evidence_executed, false);
  delete globalThis.__source_evidence_executed;
  assert.equal(result.candidates.length, 4);
  assert.equal(result.unresolved_candidates, 2);
  assert.equal(result.candidates[0].method, null);
  assert.equal(result.candidates[2].method, "POST");
  assert.deepEqual(result.candidates[0].query_names, ["page", "token"]);
  assert.ok(
    result.candidates.every(
      (item) => item.basis === "static-candidate" && item.source_line > 0,
    ),
  );
  assert.doesNotMatch(
    JSON.stringify(result),
    /secret-value|comment-only|string-only|not-a-request/,
  );
});

test("JavaScript parsing does not manufacture candidates from malformed code or invalid bases", () => {
  assert.throws(
    () => inspectScript("fetch('secret-value'", "https://source.example/"),
    /could not be parsed/,
  );
  for (const base of [
    undefined,
    "file:///tmp/index.html",
    "https://secret@source.example/",
    "https://source.example/?token=secret",
  ])
    assert.throws(() => inspectScript("fetch('/api/jobs')", base));
});

test("comparison reports observed changes without calling an absent request a closed listing", () => {
  const before = inspectNetwork(
    capture(
      record("https://source.example/jobs", 500),
      record("https://source.example/old"),
    ),
    scope,
  );
  const after = inspectNetwork(
    capture(
      record("https://source.example/jobs", 200),
      record("https://source.example/new"),
    ),
    scope,
  );
  const diff = compareNetwork(before, after);
  assert.equal(diff.newly_observed[0].path_template, "/new");
  assert.equal(diff.not_observed_after[0].path_template, "/old");
  assert.deepEqual(diff.changed[0].before.statuses, [500]);
  assert.deepEqual(diff.changed[0].after.statuses, [200]);
  assert.match(diff.limitations[0], /does not prove/);
});

test("comparison refuses different origin scopes and unrelated files", () => {
  const report = inspectNetwork(capture(), scope);
  assert.throws(() =>
    compareNetwork(
      report,
      inspectNetwork(capture(), ["https://other.example"]),
    ),
  );
  assert.throws(() => compareNetwork(report, {}));
});

test("CLI writes private reports, refuses overwrite and sanitizes JSON errors", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "zag-source-test-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const input = join(dir, "capture.json"),
    output = join(dir, "report.json");
  writeFileSync(
    input,
    JSON.stringify(
      capture(record("https://source.example/jobs?token=secret-value")),
    ),
  );
  const script = fileURLToPath(
    new URL("./source-evidence.mjs", import.meta.url),
  );
  const args = [
    script,
    "network",
    input,
    "--origin",
    scope[0],
    "--out",
    output,
  ];
  const first = spawnSync(process.execPath, args, {
    encoding: "utf8",
    timeout: 10000,
  });
  assert.equal(first.status, 0, first.stderr);
  const contents = readFileSync(output, "utf8");
  assert.doesNotMatch(contents, /secret-value/);
  assert.match(JSON.parse(contents).artifact_sha256, /^[a-f0-9]{64}$/);
  if (process.platform !== "win32")
    assert.equal(statSync(output).mode & 0o777, 0o600);
  assert.equal(
    spawnSync(process.execPath, args, { encoding: "utf8", timeout: 10000 })
      .status,
    1,
  );
  assert.equal(readFileSync(output, "utf8"), contents);
  writeFileSync(input, '{"secret-value": malformed');
  const failed = spawnSync(
    process.execPath,
    [script, "network", input, "--origin", scope[0]],
    { encoding: "utf8", timeout: 10000 },
  );
  assert.equal(failed.status, 1);
  assert.equal(failed.stderr.trim(), "Invalid JSON input.");
  assert.equal(failed.stdout, "");
});

test("CLI rejects an oversized capture before parsing it", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "zag-source-large-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const input = join(dir, "large.json");
  writeFileSync(input, "");
  truncateSync(input, 33 * 1024 * 1024);
  const result = spawnSync(
    process.execPath,
    [
      fileURLToPath(new URL("./source-evidence.mjs", import.meta.url)),
      "network",
      input,
      "--origin",
      scope[0],
    ],
    { encoding: "utf8", timeout: 10000 },
  );
  assert.equal(result.status, 1);
  assert.match(result.stderr, /32 MiB/);
});
