export type SourceDiagnostics = {
  queued_checks?: number;
  diagnostics?: Record<string, number>;
  failure?: { kind?: string; status?: number } | null;
};

export function sourceMessages(source: SourceDiagnostics): string[] {
  const messages: string[] = [];
  const diagnostics = source.diagnostics ?? {};
  const has = (key: string) =>
    Number.isInteger(diagnostics[key]) && diagnostics[key] > 0;
  const http = (status: number) =>
    has(`http_${status}`) ||
    (source.failure?.kind === "http" && source.failure.status === status);
  if (
    Number.isInteger(source.queued_checks) &&
    (source.queued_checks ?? 0) > 0
  ) {
    messages.push(
      `${Math.min(640, source.queued_checks!)} detail checks are saved for a later refresh.`,
    );
  }
  if (http(429))
    messages.push(
      "The publisher requested fewer requests. Checks pause before retrying.",
    );
  if (http(403))
    messages.push(
      "The publisher refused automated access. We do not bypass its access controls.",
    );
  if (
    has("validation") ||
    has("reader") ||
    ["validation", "reader"].includes(source.failure?.kind ?? "")
  ) {
    messages.push(
      "Some source formats need review before more listings can be confirmed.",
    );
  }
  if (
    has("timeout") ||
    has("connection") ||
    ["timeout", "connection"].includes(source.failure?.kind ?? "")
  ) {
    messages.push(
      "Some source connections could not finish and need another check.",
    );
  }
  if ([500, 502, 503, 504].some(http))
    messages.push(
      "The publisher is temporarily unavailable; another check is needed.",
    );
  if (has("budget"))
    messages.push(
      "The collection window ended before every detail could be checked.",
    );
  if (has("queue_limit"))
    messages.push(
      "Discovery exceeded this source's queue limit; coverage is incomplete.",
    );
  return messages;
}
