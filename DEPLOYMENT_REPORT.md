# Corridor — Deployment Verification Report

**Date:** 2026-10-23  
**GitHub:** https://github.com/syedusman00/corridor  
**Branch deployed (config):** `render-vercel-deploy-prep`  
**Status:** **Not live yet** — Render and Vercel require your account login. Public URLs have **not** been tested.

---

## Pre-deploy verification (completed)

| Check | Result |
|--------|--------|
| Backend tests (`python manage.py test routing`) | **37 passed** |
| Frontend production build (`npm run build`) | **OK** |
| Secrets on GitHub (`backend/.env`) | **Absent** (404) |
| Repo visibility | **Public** (for assessment + host GitHub sync) |
| OSRM labeled non-truck-restricted | **Yes** (UI + API health note) |
| Config push | `render.yaml` pinned to repo + branch (`0c80a0a`) |

---

## Live URLs

| Service | URL | Verified |
|---------|-----|----------|
| Frontend (Vercel) | *pending your deploy* | No |
| Backend API (Render) | *pending your deploy* | No |

**Do not treat this assessment deploy as successful until both URLs respond** (health + analyze + UI).

---

## What was prepared in the repo

- Django production: `DEBUG=False` hardening, SSL/HSTS, CORS + `*.vercel.app` regex, CSRF trusted origins, WhiteNoise, Gunicorn (`timeout=120`)
- `render.yaml` — free plan, `rootDir: backend`, health `/api/health/`, `branch: render-vercel-deploy-prep`
- `frontend/vercel.json` — Vite SPA rewrites
- `VITE_API_URL` documented (set in Vercel dashboard to Render URL)
- `HERE_API_KEY` / `DJANGO_SECRET_KEY` only via host dashboards — never committed

---

## Manual actions required (exact steps)

### A. Render — backend (free, no card for free web service)

1. Open https://dashboard.render.com/ and **Sign in with GitHub** (`syedusman00`).
2. **New → Blueprint** (or **Web Service**).
3. Connect **`syedusman00/corridor`**.
4. **Branch:** `render-vercel-deploy-prep` (must match).
5. Apply blueprint → creates **`corridor-api`**.
6. Env (dashboard): leave `HERE_API_KEY` empty unless you have a valid HERE key; `DJANGO_SECRET_KEY` is auto-generated.
7. Wait until deploy is **Live**. Copy URL, e.g. `https://corridor-api-xxxx.onrender.com`.
8. Smoke test:
   ```bash
   curl https://<YOUR-RENDER>.onrender.com/api/health/
   ```
   Expect `"status":"ok"`. First hit after idle may take ~1 minute (free spin-up).

### B. Vercel — frontend (Hobby)

1. Open https://vercel.com/new — **Continue with GitHub**.
2. Import **`syedusman00/corridor`**.
3. Settings:
   - **Root Directory:** `frontend`
   - Framework: Vite  
   - Build: `npm run build` · Output: `dist`
4. **Environment Variable** (Production + Preview):
   - `VITE_API_URL` = `https://<YOUR-RENDER>.onrender.com` (**no trailing slash**)
5. Deploy. Copy URL, e.g. `https://corridor-xxxx.vercel.app`.
6. Optional: set Render `CORS_ALLOWED_ORIGINS` to that Vercel URL (regex already allows `*.vercel.app`).
7. If you set `VITE_API_URL` after the first build → **Redeploy** with cache cleared.

### C. End-to-end verification checklist

- [ ] `GET /api/health/` → ok  
- [ ] Vercel UI loads; status shows API online  
- [ ] Network tab: `/api/analyze/` hits **Render**, not localhost  
- [ ] Chicago → Denver: routes, map, checkpoints, recommendation, heatmap 0–48h  
- [ ] If no HERE key: UI shows **OSRM driving (not truck-restricted)**

---

## Remaining issues

1. **Agent cannot complete host login** — Render redirected to GitHub OAuth; Vercel CLI is logged out; no `VERCEL_TOKEN` / `RENDER_API_KEY` in the environment.
2. **Free Render cold starts** — ~30–60s after idle; analyze can take longer on free CPU.
3. **HERE truck routing** — without a valid `HERE_API_KEY` on Render, production uses OSRM fallback (correctly labeled).
4. After you deploy, reply with both public URLs so they can be verified in-browser.

---

## Quick reference

| Item | Value |
|------|--------|
| GitHub | https://github.com/syedusman00/corridor |
| Branch | `render-vercel-deploy-prep` |
| Full guide | [DEPLOY.md](./DEPLOY.md) |
