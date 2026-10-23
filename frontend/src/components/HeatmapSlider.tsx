import { CloudSun } from "lucide-react";
import { RISK_COLORS } from "../lib/risk";
import type { RiskLevel } from "../types";

interface Props {
  hour: number;
  onChange: (hour: number) => void;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  baseTime?: string | null;
}

const LEGEND: RiskLevel[] = [
  "Low",
  "Moderate",
  "High",
  "Severe",
  "No Travel",
  "Unknown",
];

export function HeatmapSlider({
  hour,
  onChange,
  enabled,
  onToggle,
  baseTime,
}: Props) {
  const labelTime = baseTime
    ? new Date(new Date(baseTime).getTime() + hour * 3600_000)
    : null;

  return (
    <div className="panel rounded-2xl p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CloudSun size={18} className="text-[var(--color-accent)]" />
          <div>
            <h3 className="font-display text-sm font-semibold">
              Corridor weather-risk heatmap
            </h3>
            <p className="text-xs text-[var(--color-ink-muted)]">
              Offset from trip departure along the corridor (0–48h)
            </p>
          </div>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onToggle(e.target.checked)}
            className="accent-[var(--color-accent)]"
          />
          Show on map
        </label>
      </div>

      <div className="flex items-center gap-4">
        <input
          type="range"
          min={0}
          max={48}
          step={1}
          value={hour}
          disabled={!baseTime}
          aria-label="Forecast hour offset 0 to 48"
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-2 w-full flex-1 cursor-pointer appearance-none rounded-full bg-[var(--color-line)] accent-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-40"
        />
        <div className="min-w-[88px] rounded-xl bg-[var(--color-ink)] px-3 py-2 text-center text-sm font-semibold text-white">
          +{hour}h
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--color-ink-muted)]">
        <span>
          {labelTime
            ? labelTime.toLocaleString(undefined, {
                weekday: "short",
                month: "short",
                day: "numeric",
                hour: "numeric",
              })
            : "Run an analysis to enable the forecast slider"}
        </span>
        <div className="flex flex-wrap gap-2">
          {LEGEND.map((level) => (
            <span key={level} className="inline-flex items-center gap-1">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: RISK_COLORS[level] }}
              />
              {level}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
