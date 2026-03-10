# 💧 Aquifer Intelligence Platform

A full-stack SaaS application for real-time groundwater monitoring and AI-powered forecasting.

---

## 🏗 Project Structure

```
aquifer/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # SQLite setup + seed data
│   ├── requirements.txt     # Python dependencies
│   └── routers/
│       ├── auth.py          # Login / Register / JWT
│       ├── aquifers.py      # Aquifer data + map endpoints
│       ├── wells.py         # Well monitoring endpoints
│       ├── alerts.py        # Alert management
│       ├── forecasting.py   # AI forecasting engine
│       ├── dashboard.py     # Overview & stats
│       └── regulatory.py    # Compliance & permits
├── frontend/
│   └── index.html           # Full SPA (HTML/CSS/JS)
├── start_backend.sh         # One-click backend start
└── README.md
```

---

## 🚀 Quick Start

### Step 1: Configure real‑world data keys

The system pulls live data from three providers:

* **USGS** — no key required, but network access to `waterservices.usgs.gov` is needed.
* **NOAA Climate Data Online** — set `NOAA_API_KEY` in `.env` or environment.
* **NASA GRACE / GRACE‑FO** — set `NASA_EARTHDATA_TOKEN` in `.env` (EarthData login required).

You can create a `.env` file in `backend/` with values like:

```
NOAA_API_KEY=your_noaa_key_here
NASA_EARTHDATA_TOKEN=your_earthdata_token_here
SYNC_INTERVAL_MINUTES=15    # optional
```

### Step 2: Start the Backend

```bash
# Option A: Use the startup script (handles deps automatically)
chmod +x start_backend.sh
./start_backend.sh

# Option B: Manual
cd backend
pip install -r requirements.txt
python main.py
```
```

Backend runs at: **http://localhost:8000**
API Docs (Swagger): **http://localhost:8000/docs**

### Step 2: Open the Frontend

Simply open `frontend/index.html` in your browser.

> **Note:** No build step needed! It's pure HTML/CSS/JS.

### Step 3: Login

| Email | Password | Role |
|-------|----------|------|
| admin@aquifer.io | admin123 | Admin |
| analyst@aquifer.io | admin123 | Analyst |

---

## ✨ Features

| Feature | Status |
|---------|--------|
| 🔐 JWT Authentication | ✅ Complete |
| 🌍 Aquifer Stress Map | ✅ Complete (Leaflet.js) |
| 📊 Interactive Dashboard | ✅ Complete (Chart.js) |
| 🔵 Well Monitoring | ✅ Complete |
| 🚨 Alert System | ✅ Complete |
| 📈 AI Demand Forecasting | ✅ Complete |
| 🕰 Historical Analysis | ✅ Complete |
| 📑 Regulatory Dashboard | ✅ Complete |

---

## 🌐 API Endpoints

### Auth
- `POST /api/auth/login` — Login with email/password
- `POST /api/auth/register` — Register new user

### Aquifers
- `GET /api/aquifers/` — List all aquifers
- `GET /api/aquifers/map` — Map summary data (used by UI lists)
- `GET /api/aquifers/geojson` — GeoJSON FeatureCollection with stress values and radius (meters)
- `GET /api/aquifers/stats` — Summary statistics
- `GET /api/aquifers/{id}/history` — Historical readings

### Wells
- `GET /api/wells/` — List wells
- `GET /api/wells/map` — Well locations for map
- `GET /api/wells/stats` — Well statistics

### Alerts
- `GET /api/alerts/` — List active alerts
- `GET /api/alerts/summary` — Alert counts by severity
- `PUT /api/alerts/{id}/acknowledge` — Acknowledge alert
- `PUT /api/alerts/{id}/resolve` — Resolve alert

### Forecasting (AI)
- `GET /api/forecasting/aquifer/{id}` — Water level forecast
- `GET /api/forecasting/demand/{id}` — Demand forecast
- `GET /api/forecasting/scarcity-risk` — Risk index all aquifers
- `GET /api/forecasting/summary` — 30d/90d forecast summary

### Dashboard
- `GET /api/dashboard/overview` — Full system overview
- `GET /api/dashboard/trends` — Time series trends
- `GET /api/dashboard/regional-summary` — Per-state summary

### Regulatory
- `GET /api/regulatory/compliance` — Compliance status
- `GET /api/regulatory/recommendations` — Policy recommendations
- `GET /api/regulatory/permits` — Permit summary

---

## 🔧 Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5 + CSS3 + Vanilla JS |
| Maps | Leaflet.js (free, no API key) |
| Charts | Chart.js |
| Backend | Python + FastAPI |
| Database | SQLite (zero-config) |
| Auth | JWT (PyJWT) |
| AI Model | Custom forecasting engine |

---

## 📦 Free Tier Deployment

### Frontend → Netlify (Free)
1. Drag `frontend/` folder to netlify.com/drop
2. Done! Live URL instantly

### Backend → Render (Free)
1. Push to GitHub
2. Connect to render.com
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python main.py`

### Backend → Railway (Free)
1. `railway login`
2. `railway init && railway up`

---

## 🔮 Upgrade Path (Production)

To upgrade from demo to production:

1. **Real Data**: Integrate USGS Water Services API (free)
   - `https://waterservices.usgs.gov/nwis/iv/`
2. **Satellite Data**: NASA GRACE API (free)
   - `https://grace.jpl.nasa.gov/`
3. **ML Model**: Replace forecasting engine with Prophet/scikit-learn
4. **Database**: Migrate SQLite → PostgreSQL
5. **Auth**: Add OAuth2 (Google/GitHub login)

---

## 📊 Seed Data

The app comes pre-loaded with:
- **10 real US aquifers** (Ogallala, Central Valley, Edwards, etc.)
- **50 monitoring wells** with 90 days of readings
- **7 active alerts** across severity levels
- **1800 forecast data points**
- **2 demo users**

---

*Built with FastAPI + SQLite + Leaflet.js + Chart.js*
*Aquifer Intelligence Platform v1.0.0*
