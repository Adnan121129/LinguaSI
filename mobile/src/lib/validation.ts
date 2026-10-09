/** Valid future date in YYYY-MM-DD form, or an explanation of what's wrong. Works in local calendar days. */
export function checkTestDate(value: string, today = new Date()): string | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return "Use the format YYYY-MM-DD, e.g. 2027-03-14.";
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return "That date doesn't exist.";
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (date < start) return "Choose a date in the future.";
  return null;
}
