import { sentenceCase } from "@/lib/format";


export function StatusPill({ status }: { status: string }) {
  const tone = ["available", "complete", "current", "success"].includes(status)
    ? "good"
    : ["failed", "provider_error", "invalid_payload", "future_observation"].includes(status)
      ? "bad"
      : ["partial", "stale", "delayed_publication", "missing_measurement"].includes(status)
        ? "warn"
        : "muted";
  return <span className={`status-pill ${tone}`}>{sentenceCase(status)}</span>;
}
