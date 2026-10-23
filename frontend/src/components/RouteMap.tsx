import { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map, Marker } from "maplibre-gl";
// Vite-friendly worker URL — avoids blank canvas when the default worker fails
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { AnalyzeResponse, RiskLevel, RouteResult } from "../types";
import { RISK_COLORS, ROUTE_COLORS } from "../lib/risk";
import { RiskBadge } from "./RiskBadge";

maplibregl.setWorkerUrl(maplibreWorkerUrl);

/** OpenFreeMap Positron — reliable vector tiles without API key */
const STYLE = "https://tiles.openfreemap.org/styles/positron";
const HEATMAP_SOURCE = "heatmap-src";
const HEATMAP_LAYER = "heatmap-layer";

interface Props {
  data: AnalyzeResponse | null;
  selectedRouteId: string | null;
  heatmapHour: number;
  showHeatmap: boolean;
}

export function RouteMap({
  data,
  selectedRouteId,
  heatmapHour,
  showHeatmap,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const fittedKeyRef = useRef<string | null>(null);
  const heatmapReadyRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [-98.5, 39.8],
      zoom: 3.6,
      attributionControl: { compact: true },
    });
    map.addControl(
      new maplibregl.NavigationControl({ visualizePitch: false }),
      "top-right",
    );
    mapRef.current = map;

    const resize = () => {
      map.resize();
    };
    map.on("load", resize);
    // Container may get real size after flex layout — observe it
    const ro = new ResizeObserver(() => {
      resize();
    });
    ro.observe(containerRef.current);
    // Extra pass after paint
    requestAnimationFrame(resize);
    setTimeout(resize, 100);
    setTimeout(resize, 400);

    return () => {
      ro.disconnect();
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
      heatmapReadyRef.current = false;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;

    const apply = () => {
      map.resize();
      clearRouteLayers(map);
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      const bounds = new maplibregl.LngLatBounds();

      const ordered = [...data.routes].sort((a, b) => {
        if (a.id === selectedRouteId) return 1;
        if (b.id === selectedRouteId) return -1;
        return 0;
      });

      ordered.forEach((route) => {
        const idx = data.routes.findIndex((r) => r.id === route.id);
        const color = ROUTE_COLORS[idx % ROUTE_COLORS.length];
        const isSelected = route.id === selectedRouteId;
        const sourceId = `route-src-${route.id}`;
        const layerId = `route-layer-${route.id}`;

        if (!route.geometry?.length) return;

        map.addSource(sourceId, {
          type: "geojson",
          data: {
            type: "Feature",
            properties: { id: route.id },
            geometry: {
              type: "LineString",
              coordinates: route.geometry,
            },
          },
        });

        map.addLayer({
          id: `${layerId}-casing`,
          type: "line",
          source: sourceId,
          paint: {
            "line-color": "#ffffff",
            "line-width": isSelected ? 10 : 6,
            "line-opacity": 0.95,
          },
          layout: { "line-join": "round", "line-cap": "round" },
        });

        map.addLayer({
          id: layerId,
          type: "line",
          source: sourceId,
          paint: {
            "line-color": color,
            "line-width": isSelected ? 5 : 3,
            "line-opacity": isSelected ? 1 : 0.55,
          },
          layout: { "line-join": "round", "line-cap": "round" },
        });

        route.geometry.forEach(([lon, lat]) => bounds.extend([lon, lat]));

        if (isSelected) {
          route.checkpoints.forEach((cp) => {
            const el = document.createElement("button");
            el.type = "button";
            el.className = "checkpoint-marker";
            const colorRisk =
              RISK_COLORS[cp.overall_risk] ?? RISK_COLORS.Unknown;
            el.style.cssText = `
              width: 14px; height: 14px; border-radius: 999px;
              background: ${colorRisk};
              border: 2px solid white;
              box-shadow: 0 2px 8px rgba(15,28,46,.35);
              cursor: pointer; padding: 0;
            `;

            const popupNode = document.createElement("div");
            const root = createRoot(popupNode);
            root.render(<CheckpointPopup route={route} checkpoint={cp} />);

            const popup = new maplibregl.Popup({
              offset: 12,
              maxWidth: "280px",
              closeButton: true,
            }).setDOMContent(popupNode);

            const marker = new maplibregl.Marker({ element: el })
              .setLngLat([cp.lon, cp.lat])
              .setPopup(popup)
              .addTo(map);
            markersRef.current.push(marker);
          });
        }
      });

      if (data.origin) {
        markersRef.current.push(
          makeLabelMarker(map, data.origin.lon, data.origin.lat, "A", "#0d7a6f"),
        );
        bounds.extend([data.origin.lon, data.origin.lat]);
      }
      if (data.destination) {
        markersRef.current.push(
          makeLabelMarker(
            map,
            data.destination.lon,
            data.destination.lat,
            "B",
            "#0f1c2e",
          ),
        );
        bounds.extend([data.destination.lon, data.destination.lat]);
      }

      const fitKey = [
        data.origin?.lat,
        data.origin?.lon,
        data.destination?.lat,
        data.destination?.lon,
        data.departure,
        data.load_lbs,
        ...data.routes.map(
          (r) => `${r.id}:${r.distance_miles}:${r.geometry?.length ?? 0}`,
        ),
      ].join("|");

      if (!bounds.isEmpty() && fittedKeyRef.current !== fitKey) {
        map.fitBounds(bounds, { padding: 56, duration: 700, maxZoom: 7.5 });
        fittedKeyRef.current = fitKey;
      }

      syncHeatmap(map, data, heatmapHour, showHeatmap, heatmapReadyRef);
    };

    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, selectedRouteId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data?.heatmap) return;
    const update = () =>
      syncHeatmap(map, data, heatmapHour, showHeatmap, heatmapReadyRef);
    if (map.isStyleLoaded()) update();
    else map.once("load", update);
  }, [data, heatmapHour, showHeatmap]);

  return (
    <div className="route-map-shell relative h-full w-full overflow-hidden rounded-2xl border border-[var(--color-line)] bg-[#dce6f0]">
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />
      {!data && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
          <div className="panel max-w-sm rounded-2xl px-5 py-4 text-center shadow-lg">
            <p className="font-display text-lg font-semibold">Route map</p>
            <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
              Enter a trip to plot routes, weather checkpoints, and the corridor
              risk heatmap.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function heatmapFeatureCollection(data: AnalyzeResponse, heatmapHour: number) {
  const features = data.heatmap.points.map((pt, i) => {
    const cell = data.heatmap.grid[i]?.[heatmapHour];
    const risk: RiskLevel = cell?.overall_risk ?? "Unknown";
    return {
      type: "Feature" as const,
      properties: {
        score: cell?.risk_score ?? -1,
        risk,
        color: RISK_COLORS[risk] ?? RISK_COLORS.Unknown,
      },
      geometry: {
        type: "Point" as const,
        coordinates: [pt.lon, pt.lat] as [number, number],
      },
    };
  });
  return { type: "FeatureCollection" as const, features };
}

function syncHeatmap(
  map: Map,
  data: AnalyzeResponse,
  heatmapHour: number,
  showHeatmap: boolean,
  readyRef: { current: boolean },
) {
  if (!showHeatmap || !data.heatmap?.points?.length) {
    if (map.getLayer(HEATMAP_LAYER)) map.removeLayer(HEATMAP_LAYER);
    if (map.getSource(HEATMAP_SOURCE)) map.removeSource(HEATMAP_SOURCE);
    readyRef.current = false;
    return;
  }

  const fc = heatmapFeatureCollection(data, heatmapHour);
  const existing = map.getSource(HEATMAP_SOURCE) as GeoJSONSource | undefined;

  if (existing) {
    existing.setData(fc);
  } else {
    map.addSource(HEATMAP_SOURCE, { type: "geojson", data: fc });
  }

  if (!map.getLayer(HEATMAP_LAYER)) {
    const beforeId =
      map.getStyle().layers?.find((l) => l.id.startsWith("route-layer-"))
        ?.id || undefined;
    map.addLayer(
      {
        id: HEATMAP_LAYER,
        type: "circle",
        source: HEATMAP_SOURCE,
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            3,
            16,
            8,
            32,
            12,
            48,
          ],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.4,
          "circle-blur": 0.7,
        },
      },
      beforeId,
    );
  }
  readyRef.current = true;
}

function clearRouteLayers(map: Map) {
  const style = map.getStyle();
  if (!style?.layers) return;
  for (const layer of [...style.layers]) {
    if (layer.id.startsWith("route-layer-")) {
      if (map.getLayer(layer.id)) map.removeLayer(layer.id);
    }
  }
  for (const id of Object.keys(style.sources || {})) {
    if (id.startsWith("route-src-") && map.getSource(id)) {
      map.removeSource(id);
    }
  }
}

function makeLabelMarker(
  map: Map,
  lon: number,
  lat: number,
  label: string,
  color: string,
): Marker {
  const el = document.createElement("div");
  el.style.cssText = `
    width: 28px; height: 28px; border-radius: 999px;
    background: ${color}; color: white; font-weight: 700;
    font-size: 12px; display: grid; place-items: center;
    border: 2px solid white; box-shadow: 0 4px 14px rgba(15,28,46,.3);
  `;
  el.textContent = label;
  return new maplibregl.Marker({ element: el }).setLngLat([lon, lat]).addTo(map);
}

function CheckpointPopup({
  route,
  checkpoint,
}: {
  route: RouteResult;
  checkpoint: RouteResult["checkpoints"][number];
}) {
  const eta = new Date(checkpoint.eta);
  const wx = checkpoint.weather;
  return (
    <div className="min-w-[220px] p-3 text-[var(--color-ink)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <strong className="text-sm">
          Mile {checkpoint.distance_miles.toFixed(0)}
        </strong>
        <RiskBadge level={checkpoint.overall_risk} size="sm" />
      </div>
      {checkpoint.overall_risk === "Unknown" && (
        <p className="mb-2 text-xs text-[var(--color-ink-muted)]">
          {checkpoint.weather_error ||
            wx.weather_error ||
            "Weather unavailable for this ETA"}
        </p>
      )}
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-[var(--color-ink-muted)]">
        <div>
          ETA
          <div className="font-medium text-[var(--color-ink)]">
            {eta.toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })}
          </div>
        </div>
        <div>
          Wind
          <div className="font-medium text-[var(--color-ink)]">
            {wx.wind_mph == null ? "—" : `${wx.wind_mph.toFixed(0)} mph`}
          </div>
        </div>
        <div>
          Rain
          <div className="font-medium text-[var(--color-ink)]">
            {wx.rain_in_hr == null ? "—" : wx.rain_in_hr.toFixed(2)}
          </div>
        </div>
        <div>
          Snow
          <div className="font-medium text-[var(--color-ink)]">
            {wx.snow_in_hr == null ? "—" : wx.snow_in_hr.toFixed(2)}
          </div>
        </div>
      </dl>
      <p className="mt-2 text-[11px] text-[var(--color-ink-muted)]">
        {route.id.replace("route-", "Route ")} · {route.provider.toUpperCase()}{" "}
        · W {checkpoint.wind_risk} · R {checkpoint.rain_risk} · S{" "}
        {checkpoint.snow_risk}
      </p>
    </div>
  );
}
