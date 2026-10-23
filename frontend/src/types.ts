export type RiskLevel =
  | "Low"
  | "Moderate"
  | "High"
  | "Severe"
  | "No Travel"
  | "Unknown";

export interface Place {
  label: string;
  lat: number;
  lon: number;
  source?: string;
}

export interface CheckpointWeather {
  time: string;
  temperature_c: number | null;
  wind_mph: number | null;
  rain_in_hr: number | null;
  snow_in_hr: number | null;
  weather_code: number | null;
  weather_valid?: boolean;
  weather_error?: string | null;
}

export interface Checkpoint {
  index: number;
  lat: number;
  lon: number;
  distance_miles: number;
  fraction: number;
  eta: string;
  weather: CheckpointWeather;
  wind_risk: RiskLevel;
  rain_risk: RiskLevel;
  snow_risk: RiskLevel;
  overall_risk: RiskLevel;
  risk_score: number;
  weather_valid?: boolean;
  weather_error?: string | null;
}

export interface RouteResult {
  id: string;
  provider: string;
  transport_mode: string;
  distance_meters: number;
  duration_seconds: number;
  distance_miles: number;
  duration_hours: number;
  geometry: [number, number][];
  summary: string;
  warning?: string;
  checkpoints: Checkpoint[];
  checkpoint_count: number;
  has_no_travel: boolean;
  weather_incomplete?: boolean;
  severe_miles: number;
  high_miles: number;
  moderate_miles: number;
  low_miles: number;
  no_travel_miles?: number;
  unknown_miles?: number;
  average_risk: number;
  max_risk: RiskLevel;
  total_miles: number;
  eta_destination: string;
}

export interface Recommendation {
  route_id: string;
  reason: string;
}

export interface HeatmapPoint {
  lat: number;
  lon: number;
  index: number;
  distance_miles?: number;
}

export interface HeatmapCell {
  hour_offset: number;
  time?: string;
  wind_mph: number | null;
  rain_in_hr: number | null;
  snow_in_hr: number | null;
  overall_risk: RiskLevel;
  risk_score: number;
  weather_valid?: boolean;
}

export interface Heatmap {
  points: HeatmapPoint[];
  hours: number[];
  grid: HeatmapCell[][];
  base_time?: string | null;
}

export interface AnalyzeResponse {
  origin: Place;
  destination: Place;
  departure: string;
  load_lbs: number;
  interval_miles: number;
  routes: RouteResult[];
  recommendation: Recommendation | null;
  heatmap: Heatmap;
  routing_provider: string | null;
}

export interface AnalyzeRequest {
  origin: string;
  destination: string;
  departure: string;
  load_lbs: number;
  interval_miles: 10 | 25 | 50;
}
