// Extracted from REA 6.7.0, copyright (c) 2026 morluto. MIT, see LICENSE.
export const segmentRule = (value) => {
  if (/^[0-9]+$/u.test(value)) return "numeric";
  if (
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu.test(
      value,
    )
  )
    return "uuid";
  if (/^[0-9a-f]{32,}$/iu.test(value)) return "hex";
  if (/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/u.test(value)) {
    const date = new Date(`${value}T00:00:00.000Z`);
    if (
      Number.isFinite(date.getTime()) &&
      date.toISOString().slice(0, 10) === value
    )
      return "iso-date";
  }
  return null;
};
