import { sentenceCase } from "@/lib/format";


export function StatusPill({ status }: { status: string }) {
  const tone = ["available", "complete", "current", "success"].includes(status)
    ? "good"
    : status === "failed"
      ? "bad"
      : ["partial", "stale"].includes(status)
        ? "warn"
        : "muted";
  return <span className={`status-pill ${tone}`}>{sentenceCase(status)}</span>;
}
