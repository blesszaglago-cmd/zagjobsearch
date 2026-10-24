#!/usr/bin/env node
/** Local, offline source investigation. No browser control or network requests. */
import { createHash } from "node:crypto";
import { readFileSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  parseRecordedTransportUrl,
  parseUrlQueryParameterNames,
} from "./vendor/rea/recorded-transport-url.mjs";
import { segmentRule } from "./vendor/rea/route-rule.mjs";

const format = "zag-source-evidence-v1";
const maxCaptureBytes = 32 * 1024 * 1024;
const maxScriptBytes = 4 * 1024 * 1024;
const digest = (value) => createHash("sha256").update(value).digest("hex");
const object = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const sorted = (values) => [...values].sort();

function origin(value) {
  const url = URL.parse(value);
  if (
    !url ||
    !["https:", "http:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  )
    throw Error(
      "Supply an HTTP(S) origin without credentials, a path, query or fragment.",
    );
  return url.origin;
}

function template(path) {
  let previous = "";
  return path
    .split("/")
    .map((part) => {
      const sensitive = /^(?:token|verify|reset|magic-link|callback)$/i.test(
        previous,
      );
      previous = part;
      const rule = segmentRule(part);
      if (rule) return `{${rule}}`;
      if (sensitive || part.length > 64 || /@|%40/i.test(part))
        return "{redacted}";
      return /^[A-Za-z0-9._~-]*$/.test(part) ? part : "{redacted}";
    })
    .join("/");
}

function coordinates(value) {
  if (typeof value !== "string" || value.length > 8192) return null;
  const parsed = parseRecordedTransportUrl(value, { includeQuery: true });
  if (
    !parsed.origin ||
    parsed.path === null ||
    parsed.credentials !== null ||
    !/^https?:\/\//.test(parsed.origin)
  )
    return null;
  return {
    origin: parsed.origin,
    path_template: template(parsed.path),
    query_names: sorted(
      new Set(
        [...parseUrlQueryParameterNames(parsed.query || "")].map((name) =>
          /^[A-Za-z_][A-Za-z0-9_.\[\]-]{0,63}$/.test(name)
            ? name
            : "{redacted}",
        ),
      ),
    ),
  };
}

export function inspectNetwork(input, allowedOrigins) {
  if (!Array.isArray(allowedOrigins) || allowedOrigins.length === 0)
    throw Error("Network inspection requires at least one explicit --origin.");
  const scope = new Set(allowedOrigins.map(origin));
  const entries =
    object(input?.log) && Array.isArray(input.log.entries)
      ? input.log.entries
      : input?.format === "public-source-observations-v1" &&
          Array.isArray(input.observations)
        ? input.observations
        : null;
  if (!entries || entries.length > 50_000)
    throw Error(
      "Supply a HAR with log.entries, or public-source-observations-v1, with at most 50000 records.",
    );
  const groups = new Map();
  const excluded = {};
  const skip = (reason) => {
    excluded[reason] = (excluded[reason] || 0) + 1;
  };
  let included = 0;
  entries.forEach((entry, ordinal) => {
    const request = entry?.request;
    const point = coordinates(request?.url);
    if (!point) {
      skip("unusable-or-credential-bearing-url");
      return;
    }
    if (!scope.has(point.origin)) {
      skip("outside-selected-origins");
      return;
    }
    const method = request?.method;
    if (typeof method !== "string" || !/^[A-Z]{3,12}$/.test(method)) {
      skip("unknown-method");
      return;
    }
    const key = JSON.stringify([method, point.origin, point.path_template]);
    let group = groups.get(key);
    if (!group) {
      group = {
        method,
        origin: point.origin,
        path_template: point.path_template,
        query_names: new Set(),
        statuses: new Set(),
        content_types: new Set(),
        record_ordinals: [],
        unknown_responses: 0,
      };
      groups.set(key, group);
    }
    const status = entry?.response?.status;
    if (Number.isInteger(status) && status >= 100 && status <= 599)
      group.statuses.add(status);
    else group.unknown_responses++;
    const mime = entry?.response?.content?.mimeType;
    if (typeof mime === "string") {
      const essence = mime.split(";", 1)[0].trim().toLowerCase();
      if (/^[a-z0-9!#$&^_.+-]+\/[a-z0-9!#$&^_.+-]+$/.test(essence))
        group.content_types.add(essence);
    }
    point.query_names.forEach((name) => group.query_names.add(name));
    group.record_ordinals.push(ordinal);
    included++;
  });
  const surfaces = [...groups.values()]
    .map((group) => ({
      ...group,
      template_basis: "format-inference",
      sample_count: group.record_ordinals.length,
      query_names: sorted(group.query_names),
      statuses: [...group.statuses].sort((a, b) => a - b),
      content_types: sorted(group.content_types),
    }))
    .sort((a, b) =>
      JSON.stringify([a.origin, a.path_template, a.method]).localeCompare(
        JSON.stringify([b.origin, b.path_template, b.method]),
        "en",
      ),
    );
  return {
    format,
    kind: "network",
    selected_origins: sorted(scope),
    records: {
      supplied: entries.length,
      included,
      excluded: entries.length - included,
    },
    exclusions: excluded,
    surfaces,
    limitations: [
      "Only supplied records were examined; this is not a full HAR schema validator.",
      "Route templates are format inferences, not proof of a shared handler or a public API.",
      "Headers, bodies, query values, fragments and observed variable path values are not included.",
    ],
  };
}

export function inspectScript(source, baseUrl) {
  const base = URL.parse(baseUrl);
  if (
    !base ||
    !["https:", "http:"].includes(base.protocol) ||
    base.username ||
    base.password ||
    base.search ||
    base.hash
  )
    throw Error(
      "Supply the public document's HTTP(S) --base-url without credentials, query or fragment.",
    );
  const require = createRequire(
    new URL("../frontend/package.json", import.meta.url),
  );
  const ts = require("typescript");
  const tree = ts.createSourceFile(
    "source.js",
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.JS,
  );
  if (tree.parseDiagnostics.length)
    throw Error(
      "JavaScript could not be parsed completely; no complete endpoint report was produced.",
    );
  const candidates = [];
  let unresolved = 0;
  function literal(node, depth = 0) {
    if (!node || depth > 16) return undefined;
    if (ts.isStringLiteralLike(node)) return node.text;
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.PlusToken
    ) {
      const left = literal(node.left, depth + 1),
        right = literal(node.right, depth + 1);
      if (left !== undefined && right !== undefined) return left + right;
    }
    return undefined;
  }
  function add(value, mechanism, method, node) {
    if (value === undefined) {
      unresolved++;
      return;
    }
    const url = URL.parse(value, base);
    const point = url && coordinates(url.href);
    if (!point) {
      unresolved++;
      return;
    }
    const position = tree.getLineAndCharacterOfPosition(node.getStart(tree));
    candidates.push({
      ...point,
      mechanism,
      method,
      source_line: position.line + 1,
      source_column: position.character + 1,
      basis: "static-candidate",
    });
  }
  function visit(node) {
    if (ts.isCallExpression(node)) {
      const call = node.expression;
      if (ts.isIdentifier(call) && call.text === "fetch")
        add(literal(node.arguments[0]), "fetch-call", null, node);
      if (
        ts.isPropertyAccessExpression(call) &&
        ts.isIdentifier(call.expression) &&
        call.expression.text === "axios" &&
        /^(get|post|put|patch|delete|head|options)$/.test(call.name.text)
      )
        add(
          literal(node.arguments[0]),
          "axios-call",
          call.name.text.toUpperCase(),
          node,
        );
    }
    if (
      ts.isPropertyAssignment(node) &&
      (ts.isIdentifier(node.name) || ts.isStringLiteralLike(node.name)) &&
      node.name.text === "baseURL"
    )
      add(literal(node.initializer), "client-base-url", null, node);
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return {
    format,
    kind: "javascript",
    source_sha256: digest(source),
    candidates,
    unresolved_candidates: unresolved,
    limitations: [
      "Source was parsed, never executed. No discovered URL was requested.",
      "Only literal fetch, axios and baseURL candidates are selected; bindings, aliases, dynamic values and reachability are not resolved.",
      "A fetch candidate's HTTP method remains unknown; an options object can override GET.",
    ],
  };
}

function networkReport(value) {
  if (
    value?.format !== format ||
    value.kind !== "network" ||
    !Array.isArray(value.surfaces) ||
    !Array.isArray(value.selected_origins)
  )
    throw Error("Compare requires two network reports produced by this tool.");
  return value;
}

export function compareNetwork(before, after) {
  before = networkReport(before);
  after = networkReport(after);
  if (
    JSON.stringify(sorted(before.selected_origins)) !==
    JSON.stringify(sorted(after.selected_origins))
  )
    throw Error("Compare reports made with the same selected origins.");
  const key = (group) =>
    JSON.stringify([group.method, group.origin, group.path_template]);
  const left = new Map(before.surfaces.map((group) => [key(group), group]));
  const right = new Map(after.surfaces.map((group) => [key(group), group]));
  const coordinate = (group) => ({
    method: group.method,
    origin: group.origin,
    path_template: group.path_template,
  });
  const state = (group) => ({
    statuses: group.statuses,
    content_types: group.content_types,
    query_names: group.query_names,
    unknown_responses: group.unknown_responses,
  });
  return {
    format,
    kind: "comparison",
    newly_observed: [...right]
      .filter(([id]) => !left.has(id))
      .map(([, group]) => coordinate(group)),
    not_observed_after: [...left]
      .filter(([id]) => !right.has(id))
      .map(([, group]) => coordinate(group)),
    changed: [...right]
      .filter(
        ([id, group]) =>
          left.has(id) &&
          JSON.stringify(state(left.get(id))) !== JSON.stringify(state(group)),
      )
      .map(([id, group]) => ({
        ...coordinate(group),
        before: state(left.get(id)),
        after: state(group),
      })),
    limitations: [
      "Differences describe these captures only. A missing request does not prove that a source or vacancy closed.",
    ],
  };
}

function readText(path, maximum) {
  if (statSync(path).size > maximum)
    throw Error(
      `Input exceeds the ${maximum / 1024 / 1024} MiB local analysis limit.`,
    );
  const bytes = readFileSync(path);
  if (bytes.length > maximum)
    throw Error("Input grew beyond the local analysis limit.");
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

export function main(args = process.argv.slice(2)) {
  const help =
    "Usage: node scripts/source-evidence.mjs network CAPTURE --origin https://source.example [--origin ...] [--out REPORT]\n       node scripts/source-evidence.mjs script FILE.js --base-url https://source.example/ [--out REPORT]\n       node scripts/source-evidence.mjs compare BEFORE AFTER [--out REPORT]";
  if (!args.length || args.includes("--help")) {
    console.log(help);
    return 0;
  }
  const command = args.shift();
  const files = [],
    origins = [];
  let output, baseUrl;
  while (args.length) {
    const arg = args.shift();
    if (["--origin", "--base-url", "--out"].includes(arg)) {
      const value = args.shift();
      if (!value || value.startsWith("--"))
        throw Error(`Missing value for ${arg}.`);
      if (arg === "--origin") origins.push(value);
      else if (arg === "--base-url" && baseUrl === undefined) baseUrl = value;
      else if (arg === "--out" && output === undefined) output = value;
      else throw Error(`Duplicate option ${arg}.`);
    } else if (arg.startsWith("--")) throw Error(`Unknown option ${arg}.`);
    else files.push(arg);
  }
  let result;
  if (command === "network" && files.length === 1 && baseUrl === undefined) {
    const raw = readText(files[0], maxCaptureBytes);
    result = {
      ...inspectNetwork(JSON.parse(raw), origins),
      artifact_sha256: digest(raw),
    };
  } else if (command === "script" && files.length === 1 && origins.length === 0)
    result = inspectScript(readText(files[0], maxScriptBytes), baseUrl);
  else if (
    command === "compare" &&
    files.length === 2 &&
    origins.length === 0 &&
    baseUrl === undefined
  )
    result = compareNetwork(
      ...files.map((file) => JSON.parse(readText(file, maxCaptureBytes))),
    );
  else throw Error(help);
  const text = JSON.stringify(result, null, 2) + "\n";
  if (output) writeFileSync(output, text, { flag: "wx", mode: 0o600 });
  else process.stdout.write(text);
  return 0;
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    process.exitCode = main();
  } catch (error) {
    // Never echo malformed input, provider bodies, credentials or parser excerpts.
    const known =
      error instanceof SyntaxError
        ? "Invalid JSON input."
        : error instanceof Error
          ? error.message
          : "Source analysis failed.";
    process.stderr.write(`${known}\n`);
    process.exitCode = 1;
  }
}
