import type { MetricDefinition } from "@schoolscope/shared";

/** Formats a metric's numeric value according to its configured unit.
 * Centralised so every place a metric is shown (school detail, charts,
 * exports) agrees on formatting. Returns a clear placeholder for null,
 * never "0" or a blank string that could be misread as a real zero. */
export function formatMetricValue(
  value: number | null,
  definition: MetricDefinition | null,
): string {
  if (value === null || value === undefined) return "Not available";
  const unit = definition?.unit ?? "";
  switch (unit) {
    case "percent":
      return `${formatNumber(value, 1)}%`;
    case "ratio":
      return `${formatNumber(value, 1)}:1`;
    case "places":
    case "fte":
      return formatNumber(value, 1);
    default:
      return formatNumber(value, 2);
  }
}

export function formatNumber(value: number, maximumFractionDigits = 0): string {
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits }).format(
    value,
  );
}

export function formatDate(value: Date | string | null | undefined): string {
  if (!value) return "Not available";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

export function formatDateTime(
  value: Date | string | null | undefined,
): string {
  if (!value) return "Not available";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** Human-readable label for a SchoolStatus enum value. */
export function formatSchoolStatus(status: string): string {
  switch (status) {
    case "OPEN":
      return "Open";
    case "OPEN_BUT_PROPOSED_TO_CLOSE":
      return "Open, proposed to close";
    case "PROPOSED_TO_OPEN":
      return "Proposed to open";
    case "CLOSED":
      return "Closed";
    default:
      return status;
  }
}

/** Distance formatting for the school search "distance from a point" sort
 * and the admissions boundary-distance display. */
export function formatDistanceMetres(metres: number): string {
  if (metres < 1000) return `${formatNumber(metres, 0)} m`;
  return `${formatNumber(metres / 1000, 1)} km`;
}
