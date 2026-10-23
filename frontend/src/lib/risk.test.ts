import {
  RISK_COLORS,
  averageRiskLabel,
  formatAverageRisk,
  formatDuration,
  formatMiles,
  riskTextColor,
} from "./risk";

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

assert(RISK_COLORS.Low === "#2f9e6b", "Low color");
assert(RISK_COLORS["No Travel"] === "#4a0d0d", "No Travel color");
assert(RISK_COLORS.Unknown === "#6b7280", "Unknown color");
assert(riskTextColor("Unknown") === "#6b7280", "Unknown text color");
assert(formatDuration(3660) === "1h 1m", "duration format");
assert(formatMiles(123.4) === "123 mi", "miles format");

// All-Low corridors score 0.00 — must still read as Low, not "missing"
assert(averageRiskLabel(0) === "Low", "0 => Low");
assert(averageRiskLabel(0.4) === "Low", "0.4 => Low");
assert(averageRiskLabel(1.0) === "Moderate", "1 => Moderate");
assert(averageRiskLabel(2.0) === "High", "2 => High");
assert(averageRiskLabel(3.0) === "Severe", "3 => Severe");
assert(averageRiskLabel(4.0) === "No Travel", "4 => No Travel");
assert(
  formatAverageRisk(0) === "Low (0.00/4)",
  `format 0 got ${formatAverageRisk(0)}`,
);
assert(
  formatAverageRisk(1.25) === "Moderate (1.25/4)",
  `format 1.25 got ${formatAverageRisk(1.25)}`,
);

console.log("risk.test.ts passed");
