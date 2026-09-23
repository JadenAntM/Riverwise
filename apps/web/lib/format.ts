export function formatAtlantic(value: string, includeDate = true): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Halifax",
    month: includeDate ? "short" : undefined,
    day: includeDate ? "numeric" : undefined,
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: includeDate ? "short" : undefined,
  }).format(new Date(value));
}

export function formatNumber(value: number | null, suffix = "", digits = 1): string {
  return value === null ? "Unavailable" : `${value.toFixed(digits)}${suffix}`;
}

export function sentenceCase(value: string): string {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}
