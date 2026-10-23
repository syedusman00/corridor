import clsx from "clsx";
import { ShieldCheck, AlertTriangle, Timer, Milestone } from "lucide-react";
import type { Recommendation, RouteResult } from "../types";
import { RiskBadge } from "./RiskBadge";
import {
  ROUTE_COLORS,
  formatAverageRisk,
  formatDuration,
  formatMiles,
  averageRiskLabel,
  riskTextColor,
} from "../lib/risk";

interface Props {
  routes: RouteResult[];
  recommendation: Recommendation | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  routingProvider?: string | null;
}

export function RouteCards({
  routes,
  recommendation,
  selectedId,
  onSelect,
  routingProvider,
}: Props) {
  if (!routes.length) return null;

  const provider = routingProvider || routes[0]?.provider;
  const isOsrm = provider === "osrm";

  return (
    <div className="flex flex-col gap-3">
      {recommendation ? (
        <div className="rounded-2xl border border-[var(--color-accent)]/30 bg-[var(--color-accent-soft)] p-3.5">
          <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-[var(--color-accent-deep)]">
            <ShieldCheck size={16} /> Recommended route
          </div>
          <p className="text-sm text-[var(--color-ink)]">
            <span className="font-semibold">
              {recommendation.route_id.replace("route-", "Route ")}
            </span>
            {" — "}
            {recommendation.reason}
          </p>
          <p className="mt-1.5 text-xs text-[var(--color-ink-muted)]">
            {isOsrm
              ? "Ranked by weather and load risk only. Paths use OSRM driving geometry and are not truck-restricted."
              : "Ranked by weather and load risk on HERE truck-mode paths."}
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border border-[var(--color-danger)]/30 bg-red-50 p-3.5">
          <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-[var(--color-danger)]">
            <AlertTriangle size={16} /> No weather-safe recommendation
          </div>
          <p className="text-sm text-[var(--color-ink)]">
            Every option has No Travel and/or incomplete weather (Unknown). Do
            not dispatch until forecasts are complete and conditions improve.
          </p>
        </div>
      )}

      {routes.map((route, idx) => {
        const isRec = recommendation?.route_id === route.id;
        const selected = selectedId === route.id;
        const color = ROUTE_COLORS[idx % ROUTE_COLORS.length];
        const avgLabel = averageRiskLabel(Number(route.average_risk ?? 0));

        return (
          <button
            key={route.id}
            type="button"
            onClick={() => onSelect(route.id)}
            className={clsx(
              "rounded-2xl border p-3.5 text-left transition",
              selected
                ? "border-transparent shadow-md ring-2"
                : "border-[var(--color-line)] bg-white hover:border-[var(--color-accent)]/50",
              route.has_no_travel && "opacity-90",
            )}
            style={
              selected
                ? ({
                    ["--tw-ring-color" as string]: color,
                    background: `${color}10`,
                  } as React.CSSProperties)
                : undefined
            }
          >
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: color }}
                  />
                  <h3 className="font-display text-base font-semibold">
                    Route {idx + 1}
                  </h3>
                  {isRec && (
                    <span className="rounded-md bg-[var(--color-accent)] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                      Recommended
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-[var(--color-ink-muted)]">
                  {route.provider === "here"
                    ? "HERE · truck mode"
                    : "OSRM · driving (not truck-restricted)"}
                </p>
              </div>
              <RiskBadge level={route.max_risk} size="sm" />
            </div>

            <div className="mb-2 grid grid-cols-2 gap-2 text-sm">
              <Stat
                icon={<Milestone size={14} />}
                label="Distance"
                value={formatMiles(route.distance_miles)}
              />
              <Stat
                icon={<Timer size={14} />}
                label="Travel time"
                value={formatDuration(route.duration_seconds)}
              />
            </div>

            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-[var(--color-ink-muted)]">
              <span>
                Severe:{" "}
                <strong className="text-[var(--color-ink)]">
                  {Number(route.severe_miles ?? 0).toFixed(0)} mi
                </strong>
              </span>
              <span>
                High:{" "}
                <strong className="text-[var(--color-ink)]">
                  {Number(route.high_miles ?? 0).toFixed(0)} mi
                </strong>
              </span>
              <span className="col-span-2 sm:col-span-1">
                Avg risk:{" "}
                <strong style={{ color: riskTextColor(avgLabel) }}>
                  {formatAverageRisk(Number(route.average_risk ?? 0))}
                </strong>
              </span>
              <span>
                Checkpoints:{" "}
                <strong className="text-[var(--color-ink)]">
                  {Number(
                    route.checkpoint_count ?? route.checkpoints?.length ?? 0,
                  )}
                </strong>
              </span>
            </div>

            {route.has_no_travel && (
              <p className="mt-2 text-xs font-medium text-[var(--color-danger)]">
                Contains No Travel — excluded from recommendation.
              </p>
            )}
            {route.weather_incomplete && (
              <p className="mt-2 text-xs font-medium text-[var(--color-ink-muted)]">
                Incomplete weather (Unknown) — excluded from recommendation.
              </p>
            )}
          </button>
        );
      })}
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-[var(--color-surface)] px-2.5 py-1.5">
      <div className="mb-0.5 flex items-center gap-1 text-[11px] text-[var(--color-ink-muted)]">
        {icon}
        {label}
      </div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
