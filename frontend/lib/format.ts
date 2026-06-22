export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "Unavailable";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(date);
}

export function formatPercent(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "Unknown";
  }

  return `${Math.round(value * 100)}%`;
}

export function sentenceCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

export function objectStatusLabel(status: string): string {
  switch (status) {
    case "visible_now":
      return "I can see it now";
    case "visible_recently":
      return "Last seen recently";
    case "not_seen_recently":
      return "Last seen earlier";
    case "unknown":
      return "Not sure yet";
    default:
      return sentenceCase(status);
  }
}
