import { useEffect, useMemo, useState } from "react";
import { formatISO, parseISO } from "date-fns";
import { AlertCircle, Truck } from "lucide-react";
import { TripForm } from "./components/TripForm";
import { RouteCards } from "./components/RouteCards";
import { RouteMap } from "./components/RouteMap";
import { HeatmapSlider } from "./components/HeatmapSlider";
import { analyzeTrip, healthCheck } from "./lib/api";
import { riskTextColor } from "./lib/risk";
import type { AnalyzeRequest, AnalyzeResponse } from "./types";

function defaultDepartureLocal(): string {
  const d = new Date();
  d.setMinutes(0, 0, 0);
  d.setHours(d.getHours() + 1);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function providerBadge(
  data: AnalyzeResponse | null,
  apiInfo: string | null,
): string {
  if (data?.routing_provider === "osrm") {
    return "API online · OSRM driving fallback (not truck-restricted)";
  }
  if (data?.routing_provider === "here") {
    return "API online · HERE truck routing";
  }
  return apiInfo || "Checking API…";
}

export default function App() {
  const [form, setForm] = useState<AnalyzeRequest>({
    origin: "Chicago, IL",
    destination: "Denver, CO",
    departure: defaultDepartureLocal(),
    load_lbs: 35000,
    interval_miles: 25,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [heatmapHour, setHeatmapHour] = useState(0);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [apiInfo, setApiInfo] = useState<string | null>(null);

  useEffect(() => {
    healthCheck()
      .then((h) => {
        setApiInfo(
          h.here_configured
            ? "API online · HERE key present (verify with Analyze)"
            : "API online · no HERE key · OSRM driving fallback",
        );
      })
      .catch(() => setApiInfo("API offline — start the Django backend"));
  }, []);

  useEffect(() => {
    if (!data) return;
    const preferred =
      data.recommendation?.route_id || data.routes[0]?.id || null;
    setSelectedRouteId(preferred);
    setHeatmapHour(0);
  }, [data]);

  const selectedRoute = useMemo(
    () => data?.routes.find((r) => r.id === selectedRouteId) || null,
    [data, selectedRouteId],
  );

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    try {
      const local = parseISO(form.departure);
      const departureIso = formatISO(local);
      const result = await analyzeTrip({
        ...form,
        departure: departureIso,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-full max-w-[1400px] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-[var(--color-line)] bg-white/80 px-3 py-1 text-xs font-semibold text-[var(--color-accent-deep)]">
            <Truck size={14} /> Spotter AI assessment
          </div>
          <h1 className="font-display text-3xl font-bold tracking-tight text-[var(--color-ink)] sm:text-4xl">
            Corridor
          </h1>
          <p className="mt-1 max-w-xl text-sm text-[var(--color-ink-muted)] sm:text-base">
            Weather-aware truck routing — pick the safest path by wind, rain,
            snow, and load before you roll.
          </p>
        </div>
        <p className="rounded-full border border-[var(--color-line)] bg-white px-3 py-1.5 text-xs text-[var(--color-ink-muted)]">
          {providerBadge(data, apiInfo)}
        </p>
      </header>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12 lg:items-start">
        <aside className="flex flex-col gap-4 lg:col-span-4 xl:col-span-3">
          <section className="panel rounded-2xl p-4 shadow-sm">
            <h2 className="font-display mb-3 text-lg font-semibold">
              Trip details
            </h2>
            <TripForm
              value={form}
              loading={loading}
              onChange={setForm}
              onSubmit={handleAnalyze}
            />
            {error && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-[var(--color-danger)]">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </section>

          {data && (
            <section className="panel rounded-2xl p-4 shadow-sm">
              <h2 className="font-display mb-3 text-lg font-semibold">
                Route options
              </h2>
              <RouteCards
                routes={data.routes}
                recommendation={data.recommendation}
                selectedId={selectedRouteId}
                onSelect={setSelectedRouteId}
                routingProvider={data.routing_provider}
              />
            </section>
          )}
        </aside>

        <main className="flex min-w-0 flex-col gap-4 lg:col-span-8 xl:col-span-9">
          {/* Fixed height — avoids flex-1 blank map; shorter on small phones */}
          <div className="h-[min(55vh,420px)] w-full shrink-0 sm:h-[480px] lg:h-[560px]">
            <RouteMap
              data={data}
              selectedRouteId={selectedRouteId}
              heatmapHour={heatmapHour}
              showHeatmap={showHeatmap}
            />
          </div>

          <HeatmapSlider
            hour={heatmapHour}
            onChange={setHeatmapHour}
            enabled={showHeatmap}
            onToggle={setShowHeatmap}
            baseTime={data?.heatmap.base_time}
          />

          {selectedRoute && (
            <section className="panel max-h-[min(50vh,420px)] overflow-hidden rounded-2xl p-4 shadow-sm sm:max-h-[420px]">
              <h2 className="font-display mb-2 text-lg font-semibold">
                Selected route summary
              </h2>
              <p className="text-sm text-[var(--color-ink-muted)]">
                {data?.origin.label} → {data?.destination.label} · Departs{" "}
                {new Date(data!.departure).toLocaleString()} · Load{" "}
                {data!.load_lbs.toLocaleString()} lbs · Checkpoints every{" "}
                {data!.interval_miles} mi · Provider{" "}
                <strong>
                  {data!.routing_provider === "here"
                    ? "HERE truck"
                    : "OSRM driving (not truck-restricted)"}
                </strong>
              </p>
              <div className="mt-3 max-h-[min(40vh,300px)] overflow-auto overscroll-contain [-webkit-overflow-scrolling:touch]">
                <table className="w-full min-w-[560px] text-left text-sm">
                  <thead className="sticky top-0 z-[1] bg-white/95 backdrop-blur-sm">
                    <tr className="border-b border-[var(--color-line)] text-xs uppercase tracking-wide text-[var(--color-ink-muted)]">
                      <th className="py-2 pr-3 font-semibold">Mile</th>
                      <th className="py-2 pr-3 font-semibold">ETA</th>
                      <th className="py-2 pr-3 font-semibold">Wind (mph)</th>
                      <th className="py-2 pr-3 font-semibold">Rain (in/hr)</th>
                      <th className="py-2 pr-3 font-semibold">Snow (in/hr)</th>
                      <th className="py-2 font-semibold">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRoute.checkpoints.map((cp) => (
                      <tr
                        key={cp.index}
                        className="border-b border-[var(--color-line)]/70"
                      >
                        <td className="py-2 pr-3 font-medium">
                          {cp.distance_miles.toFixed(0)}
                        </td>
                        <td className="py-2 pr-3 text-[var(--color-ink-muted)]">
                          {new Date(cp.eta).toLocaleString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                        </td>
                        <td className="py-2 pr-3">
                          {cp.weather.wind_mph == null
                            ? "—"
                            : `${cp.weather.wind_mph.toFixed(0)} mph`}
                        </td>
                        <td className="py-2 pr-3">
                          {cp.weather.rain_in_hr == null
                            ? "—"
                            : cp.weather.rain_in_hr.toFixed(2)}
                        </td>
                        <td className="py-2 pr-3">
                          {cp.weather.snow_in_hr == null
                            ? "—"
                            : cp.weather.snow_in_hr.toFixed(2)}
                        </td>
                        <td className="py-2">
                          <span
                            className="font-semibold"
                            style={{ color: riskTextColor(cp.overall_risk) }}
                          >
                            {cp.overall_risk}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selectedRoute.warning && (
                <p className="mt-3 text-xs text-[var(--color-warn)]">
                  {selectedRoute.warning}
                </p>
              )}
            </section>
          )}
        </main>
      </div>

      <footer className="pb-4 text-center text-xs text-[var(--color-ink-muted)]">
        Risk thresholds match the Spotter AI assessment · Routing via HERE Truck
        / OSRM driving fallback · Weather via Open-Meteo · Maps via MapLibre
      </footer>
    </div>
  );
}
