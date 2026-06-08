const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 60 * 60 * 24 * 365],
  ["month", 60 * 60 * 24 * 30],
  ["week", 60 * 60 * 24 * 7],
  ["day", 60 * 60 * 24],
  ["hour", 60 * 60],
  ["minute", 60],
];

const relativeFormatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return "";
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 45) return "Just now";

  for (const [unit, secondsInUnit] of RELATIVE_UNITS) {
    const value = Math.floor(seconds / secondsInUnit);
    if (value >= 1) return relativeFormatter.format(-value, unit);
  }
  return "Just now";
}

export function formatClockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function formatDayLabel(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  if (isSameDay(date, today)) return "Today";
  if (isSameDay(date, yesterday)) return "Yesterday";
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** WhatsApp contact numbers come back as bare E.164 digits (e.g. "14155551234"). */
export function formatPhone(phone: string): string {
  return phone.startsWith("+") ? phone : `+${phone}`;
}

export function contactDisplayName(name: string | null, phone: string): string {
  return name?.trim() || formatPhone(phone);
}

export function contactInitials(name: string | null, phone: string): string {
  const source = name?.trim();
  if (source) {
    const [first, second] = source.split(/\s+/).filter(Boolean);
    if (first && second) return (first.charAt(0) + second.charAt(0)).toUpperCase();
    return source.slice(0, 2).toUpperCase();
  }
  return phone.slice(-2);
}
