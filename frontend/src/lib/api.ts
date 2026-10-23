import type { AnalyzeRequest, AnalyzeResponse, Place } from "../types";
import { expandHeatmap, type CompactHeatmap } from "./heatmap";

const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "";

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    return data.detail || data.message || res.statusText;
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function healthCheck(): Promise<{
  status: string;
  here_configured: boolean;
  routing_provider: string;
  note?: string;
}> {
  const res = await fetch(`${API_BASE}/api/health/`);
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function geocodePlace(q: string): Promise<Place> {
  const res = await fetch(
    `${API_BASE}/api/geocode/?q=${encodeURIComponent(q)}`,
  );
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

type RawAnalyze = Omit<AnalyzeResponse, "heatmap"> & {
  heatmap: AnalyzeResponse["heatmap"] | CompactHeatmap;
};

export async function analyzeTrip(
  body: AnalyzeRequest,
): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/analyze/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  const raw = (await res.json()) as RawAnalyze;
  return {
    ...raw,
    heatmap: expandHeatmap(raw.heatmap),
  };
}
