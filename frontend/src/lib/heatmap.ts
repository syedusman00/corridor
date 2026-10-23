import type { Heatmap, HeatmapCell, RiskLevel } from "../types";
import { RISK_COLORS } from "./risk";

/** Compact heatmap payload from backend (`format: compact_v1`). */
export interface CompactHeatmap {
  points: Heatmap["points"];
  hours: number[];
  base_time?: string | null;
  format: "compact_v1";
  risk: string[][];
  wind: (number | null)[][];
  rain: (number | null)[][];
  snow: (number | null)[][];
  valid: boolean[][];
}

const RISK_SCORE: Record<string, number> = {
  Low: 0,
  Moderate: 1,
  High: 2,
  Severe: 3,
  "No Travel": 4,
  Unknown: -1,
};

export function expandHeatmap(raw: Heatmap | CompactHeatmap | null | undefined): Heatmap {
  if (!raw) {
    return { points: [], hours: [], grid: [], base_time: null };
  }

  if (!("format" in raw) || raw.format !== "compact_v1") {
    return raw as Heatmap;
  }

  const grid: HeatmapCell[][] = raw.risk.map((row, i) =>
    row.map((overall, h) => {
      const risk = (overall || "Unknown") as RiskLevel;
      return {
        hour_offset: h,
        wind_mph: raw.wind[i]?.[h] ?? null,
        rain_in_hr: raw.rain[i]?.[h] ?? null,
        snow_in_hr: raw.snow[i]?.[h] ?? null,
        overall_risk: risk,
        risk_score: RISK_SCORE[risk] ?? -1,
        weather_valid: raw.valid[i]?.[h] ?? false,
      };
    }),
  );

  return {
    points: raw.points,
    hours: raw.hours,
    grid,
    base_time: raw.base_time,
  };
}

export function heatmapColor(risk: RiskLevel | string): string {
  return RISK_COLORS[risk as RiskLevel] ?? RISK_COLORS.Unknown;
}
