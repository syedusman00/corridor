# Corridor — Weather-Aware Truck Routing

React + Django application that recommends the **safest truck route** using live routing, weather forecasts at mile checkpoints, and the Spotter AI assessment risk/load rules.

Built for the **Spotter AI Full Stack Developer** assessment.

## Features

- Origin, destination, departure datetime, and load weight (lbs) inputs
- Up to **3 alternative routes** via **HERE Routing API (truck mode)**, with **OSRM** fallback if no HERE key is set
- Weather checkpoints every **10 / 25 / 50 miles**, timed to the truck’s estimated arrival
- **Open-Meteo** hourly forecasts (wind, rain, snow)
- Exact assessment risk thresholds: Low → Moderate → High → Severe → No Travel, plus load-based wind rules
- Safest-route recommendation (fewest Severe miles → fewest High miles → lowest average risk → shortest time). Routes with **No Travel** are never recommended as safe
- Interactive **MapLibre** map: routes, colored checkpoints, popups, corridor **weather-risk heatmap** with **0–48h** slider
- Loading states, API error handling, responsive SaaS-style UI
- Backend unit tests for risk and geometry logic

## Stack

| Layer | Tech |
|--------|------|
| Frontend | React, TypeScript, Tailwind CSS v4, MapLibre GL JS, Vite |
| Backend | Django REST Framework |
| Routing | HERE Truck Routing (primary) / OSRM (fallback) |
| Weather | Open-Meteo |
| Maps | MapLibre + CARTO Positron basemap |
| Deploy | Vercel (frontend) · Render (backend) |

## Project layout

```
backend/                 Django API
  routing/               Geocode, routes, weather, risk engine
  routing/tests/         Unit tests
frontend/                React SPA
render.yaml              Render blueprint
frontend/vercel.json     SPA rewrites
```

## Risk rules (from assessment)

| Condition | Low | Moderate | High | Severe | No Travel |
|-----------|-----|----------|------|--------|-----------|
| Wind (mph) | &lt;25 | 25–34 | 35–44 | 45–54 | ≥55 |
| Rain (in/hr) | &lt;0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | &gt;1.00 |
| Snow (in/hr) | &lt;0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | &gt;3.0 |

**Load rules**

- ≥55 mph → No Travel (any load)
- 45–54 mph + &gt;30,000 lb → No Travel
- 35–44 mph + &gt;40,000 lb → Severe

Overall checkpoint risk = max(wind after load rules, rain, snow).

## Quick start (local)

### 1. Backend

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or cp on Unix — edit HERE_API_KEY if you have one
python manage.py migrate
python manage.py runserver
```

API: `http://127.0.0.1:8000/api/health/`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: `http://localhost:5173` (Vite proxies `/api` → Django).

### 3. Optional HERE API key

1. Create a free key at [platform.here.com](https://platform.here.com/)
2. Set `HERE_API_KEY=...` in `backend/.env`
3. Restart Django

Without a key, the API automatically uses **OSRM driving** routes so the app stays demoable. Weather, risk, heatmap, and recommendation logic still use real Open-Meteo data.

**Why Chicago→Denver sometimes showed only 2 routes:** public OSRM often returns at most two native alternatives on that corridor. The backend now requests HERE `alternatives=2` (up to **3 truck routes**) when a key is set, and for OSRM it supplements with additional **real via-point OSRM queries** until three distinct corridors are available (still live routing — not fabricated geometries).

## API

### `POST /api/analyze/`

```json
{
  "origin": "Chicago, IL",
  "destination": "Denver, CO",
  "departure": "2026-10-22T12:00:00-05:00",
  "load_lbs": 35000,
  "interval_miles": 25
}
```

Returns geocoded endpoints, up to 3 routes with geometries/checkpoints/risk summaries, a recommendation, and a 0–48h corridor heatmap grid.

### Other

- `GET /api/health/`
- `GET /api/geocode/?q=Chicago`

## Tests

```bash
cd backend
python manage.py test routing
```

Coverage includes risk thresholds, load rules, Unknown weather (failed/out-of-range forecasts never become Low), origin No Travel aggregation, recommendation exclusions, heatmap departure baseline, truck gross-weight calculation, and route deduplication.

```bash
cd frontend
npm run build
npm test
```

## Deploy (Vercel + Render)

Full step-by-step guide (GitHub → Render → Vercel, CORS wiring, smoke tests):

**→ [DEPLOY.md](./DEPLOY.md)**

Summary:

| Host | Root | Key env |
|------|------|---------|
| Render | `backend` | `DJANGO_SECRET_KEY`, `DEBUG=False`, `CORS_ALLOWED_ORIGINS` = Vercel URL, optional `HERE_API_KEY` |
| Vercel | `frontend` | `VITE_API_URL` = Render URL (no trailing slash) |

Never commit `backend/.env` / `frontend/.env`. Do not treat deploy as successful until `/api/health/` and the Vercel site both work publicly.

## Loom walkthrough tips (5–10 min)

1. Show trip form + analyze Chicago → Denver with a heavy load
2. Compare route cards (Severe/High miles, recommendation reason)
3. Click checkpoints on the map and read ETA/weather/risk
4. Scrub the 0–48h heatmap slider
5. Briefly open `routing/risk.py` and mention tests

## License

Assessment / portfolio use.
