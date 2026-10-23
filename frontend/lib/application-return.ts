// Continue only to a public listing. Reject external URLs and other endpoints.
export function applicationReturnPath(value: unknown): string | undefined {
  return typeof value === "string" && /^\/jobs\/[a-f0-9]{32}$/.test(value)
    ? value
    : undefined;
}
