# Activity Data Service

A Garmin Connect dashboard that fetches wellness and activity data and displays it as an interactive web application. Built with Dash/Plotly, deployable on Render.

## Features

- **Data Fetching** — pulls daily wellness data from Garmin Connect (heart rate, stress, body battery, steps, respiration, SpO2, sleep) plus activity details and GPX tracks
- **Interactive Dashboard** — Plotly-based charts for full-day wellness metrics and per-activity elevation/HR/cadence profiles
- **GPS Map** — route visualization with hover-linked position marker synced to the elevation profile (works on mobile via tap)
- **Light / Dark Theme** — toggle with localStorage persistence, matching the [jakobreinhardt.eu](https://jakobreinhardt.eu) design system

## Quick Start

```bash
# Clone and set up
git clone https://github.com/jakobreinhardt/activity_data_service.git
cd activity_data_service
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Garmin credentials and target date

# Fetch data
python fetch_garmin_data.py 2026-05-04

# Run dashboard
python dashboard.py
# → http://127.0.0.1:8050
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `APP_ENV` | `sandbox` or `production` | `sandbox` |
| `GARMIN_EMAIL` | Garmin Connect email | — |
| `GARMIN_PASSWORD` | Garmin Connect password | — |
| `DASHBOARD_DATE` | Date to display (YYYY-MM-DD) | `2026-05-04` |
| `TZ_OFFSET` | Timezone offset in hours from UTC | `2` |
| `PORT` | Dashboard port | `8050` |

## Project Structure

```
activity_data_service/
├── fetch_garmin_data.py   # Garmin Connect data fetcher
├── dashboard.py           # Dash web application
├── assets/
│   ├── theme.css          # Light/dark theme styles
│   └── theme.js           # Theme toggle logic
├── garmin_data/            # Fetched JSON + GPX files
├── render.yaml             # Render deployment config
├── requirements.txt
├── .env.example
└── .env                    # Local credentials (gitignored)
```

## Demo

An exemplary deployed version can be accessed here: [activity-data-service.onrender.com](https://activity-data-service.onrender.com/)

## Deployment

The app is configured for [Render](https://render.com) via `render.yaml`. Gunicorn serves the Dash app in production:

```
gunicorn dashboard:server
```

Set the environment variables in the Render dashboard. The `garmin_data/` directory must be present in the repo for the dashboard to display data.
