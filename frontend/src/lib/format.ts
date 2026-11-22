import type { Category, Domain, Risk, Verdict } from "./types";

export const pct = (x: number | null | undefined, digits = 0) =>
  x == null ? "—" : `${(x * 100).toFixed(digits)}%`;

export const signedPoints = (x: number | null | undefined) => {
  if (x == null) return "—";
  const points = Math.round(x * 100);
  return `${points > 0 ? "+" : points < 0 ? "−" : ""}${Math.abs(points)} pts`;
};

export const fixed = (x: number | null | undefined, digits = 2) =>
  x == null ? "—" : x.toFixed(digits);

export const compact = (x: number) =>
  new Intl.NumberFormat(undefined, { notation: x >= 10_000 ? "compact" : "standard" }).format(x);

const dateFormat = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const dateYearFormat = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});
const monthFormat = new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric" });
const timeFormat = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** Parse "YYYY-MM-DD" as a local calendar date (not UTC midnight, which can shift the day). */
export function parseDay(value: string): Date {
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1);
}

export const formatDay = (value: string, withYear = false) =>
  (withYear ? dateYearFormat : dateFormat).format(
    value.length === 10 ? parseDay(value) : new Date(value),
  );

export const formatMonth = (yyyyMm: string) => monthFormat.format(parseDay(`${yyyyMm}-01`));
export const formatTime = (iso: string) => timeFormat.format(new Date(iso));

export function daysFromToday(day: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((parseDay(day).getTime() - today.getTime()) / 86_400_000);
}

export function relativeDay(day: string): string {
  const diff = daysFromToday(day);
  if (diff === 0) return "today";
  if (diff === 1) return "tomorrow";
  if (diff === -1) return "yesterday";
  return diff > 0 ? `in ${diff} days` : `${-diff} days ago`;
}

export function isoDayFromToday(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export const CATEGORY: Record<Category, { label: string; hint: string }> = {
  time: { label: "Time", hint: "durations, schedules, free time" },
  self: { label: "Self", hint: "your own skill, discipline, motivation" },
  people: { label: "People", hint: "what other people will do" },
  money: { label: "Money", hint: "costs, income, value for money" },
  external: { label: "External", hint: "tools, markets, institutions" },
  other: { label: "Other", hint: "everything else" },
};

export const DOMAIN_LABEL: Record<Domain, string> = {
  career: "Career",
  study: "Study",
  projects: "Projects",
  health: "Health",
  money: "Money",
  relationships: "Relationships",
  other: "Other",
};

export const RISK_LABEL: Record<Risk, string> = {
  low: "Low risk",
  medium: "Medium risk",
  high: "High risk",
};

export const VERDICT_LABEL: Record<Verdict, string> = {
  held: "Held",
  failed: "Failed",
  unclear: "Unclear",
};

export function providerLabel(provider: string | null): string {
  if (!provider) return "unknown";
  if (provider.startsWith("seed:")) return "hand-labeled demo data";
  if (provider.startsWith("heuristic:")) return "offline heuristic";
  return provider.replace("gemini:", "Gemini · ");
}
