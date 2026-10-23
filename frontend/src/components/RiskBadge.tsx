import clsx from "clsx";
import type { RiskLevel } from "../types";
import { RISK_COLORS } from "../lib/risk";

export function RiskBadge({
  level,
  size = "md",
}: {
  level: RiskLevel;
  size?: "sm" | "md";
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-md font-medium tracking-wide",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
      )}
      style={{
        background: `${RISK_COLORS[level]}22`,
        color: RISK_COLORS[level],
        border: `1px solid ${RISK_COLORS[level]}55`,
      }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: RISK_COLORS[level] }}
      />
      {level}
    </span>
  );
}
