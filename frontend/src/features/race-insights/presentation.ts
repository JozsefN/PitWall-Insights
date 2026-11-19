import { eventLabels } from "./contracts.ts";
import type { EstimateValue, EventKind, RaceEvent } from "./contracts.ts";

export const defaultEventTypes = Object.keys(eventLabels) as EventKind[];
export function snapshotCutoff(time: number) {
  return Math.max(0, Math.floor(time / 5000) * 5000);
}
export function notificationCapacity(height: number, maximum: unknown): number {
  if ([3, 5, 10].includes(Number(maximum))) return Number(maximum);
  return Math.max(1, Math.min(12, Math.floor((height - 170) / 85) || 3));
}
export function filterEvents(
  events: RaceEvent[],
  options: Record<string, unknown>,
  selected: string[],
  cutoff: number,
): RaceEvent[] {
  const types = Array.isArray(options.eventTypes)
    ? options.eventTypes
    : defaultEventTypes;
  const severity = { info: 0, watch: 1, warning: 2 };
  const minimum = severity[options.minSeverity as keyof typeof severity] ?? 0;
  const minutes = [1, 3, 5].includes(Number(options.lookbackMinutes))
    ? Number(options.lookbackMinutes)
    : 5;
  const ids = new Set<string>();
  return events
    .filter((event) => {
      if (
        ids.has(event.id) ||
        event.time_ms > cutoff ||
        event.time_ms < cutoff - minutes * 60000
      )
        return false;
      ids.add(event.id);
      return (
        types.includes(event.kind) &&
        severity[event.severity] >= minimum &&
        (options.includeCandidates !== false ||
          event.classification !== "candidate") &&
        (options.driverScope !== "selected" ||
          event.entry_id === null ||
          selected.includes(event.entry_id) ||
          (event.rival_entry_id !== null &&
            selected.includes(event.rival_entry_id)))
      );
    })
    .sort((a, b) => b.time_ms - a.time_ms || a.id.localeCompare(b.id));
}
export function formatEstimate(metric?: EstimateValue): string {
  if (!metric || metric.status !== "available" || metric.value === null)
    return "Unavailable";
  if (typeof metric.value === "string") return metric.value;
  return `${metric.value.toLocaleString("en-GB", { maximumFractionDigits: metric.unit === "count" ? 0 : 2 })}${metric.unit === "%" ? "%" : metric.unit === "index" ? " / 100" : ` ${metric.unit}`}`;
}
export function numericEstimate(metric?: EstimateValue) {
  return metric?.status === "available" &&
    typeof metric.value === "number" &&
    Number.isFinite(metric.value)
    ? metric.value
    : null;
}
export function raceTime(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(seconds / 3600)
    .toString()
    .padStart(2, "0")}:${Math.floor((seconds / 60) % 60)
    .toString()
    .padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}
