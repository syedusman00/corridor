import type { RiskLevel } from "../types";

export const RISK_COLORS: Record<RiskLevel, string> = {
  Low: "#2f9e6b",
  Moderate: "#d4a017",
  High: "#e07a2f",
  Severe: "#c23b2e",
  "No Travel": "#4a0d0d",
  Unknown: "#6b7280",
};

export const ROUTE_COLORS = ["#0d7a6f", "#2b6cb0", "#9a5b13"];

/** Mile-weighted average uses Low=0 … No Travel=4 (Unknown excluded). */
export function averageRiskLabel(score: number): RiskLevel {
  if (Number.isNaN(score) || score < 0) return "Unknown";
  if (score < 0.5) return "Low";
  if (score < 1.5) return "Moderate";
  if (score < 2.5) return "High";
  if (score < 3.5) return "Severe";
  return "No Travel";
}

/**
 * Display mile-weighted average risk.
 * All-Low corridors correctly score 0.00 — show the band name so it is not mistaken for "missing data".
 */
export function formatAverageRisk(score: number): string {
  const n = Number(score ?? 0);
  const label = averageRiskLabel(n);
  return `${label} (${n.toFixed(2)}/4)`;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  if (h <= 0) return `${m}m`;
  return `${h}h ${m}m`;
}

export function formatMiles(miles: number): string {
  return `${miles.toFixed(0)} mi`;
}

export function riskTextColor(level: RiskLevel): string {
  return RISK_COLORS[level] ?? RISK_COLORS.Unknown;
}
