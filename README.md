# Aeolus

A Python library that analyzes GPS routes against weather forecasts to score riding conditions. Given a GPX file, an average speed, and a departure time, Aeolus fetches 15-minute weather data along your route and returns a distance-weighted score from **-1.0** (dangerous) to **+1.0** (ideal).

## How It Works

1. **Parse** — Load a GPX file and simplify the track using the Ramer-Douglas-Peucker algorithm
2. **Cluster** — Group segments by bearing and estimated travel time into ~15-minute blocks
3. **Fetch** — Retrieve 15-minute resolution forecasts from [Open-Meteo](https://open-meteo.com/) for each cluster's representative point
4. **Score** — Evaluate wind alignment, gust intensity, and precipitation for each cluster
5. **Aggregate** — Combine scores weighted by segment distance into a single route score

### Scoring

Each cluster is scored on a scale of **-1.0 to +1.0** using three weighted factors:

| Factor | Weight | Details |
|--------|--------|---------|
| Wind alignment & speed | 50% | Tailwind = positive, head-/crosswind = negative |
| Gusts | 30% | Penalized proportionally; > 20 km/h → hard block |
| Precipitation | 20% | Linear penalty; > 20 mm/h → hard block |

**Hard blocks** (score = -1.0) are triggered by:
- Gusts above 20 km/h
- Gust delta (gust − speed) above 10 km/h
- Precipitation above 20 mm/h
- Wind speed exceeding category threshold (50–60 km/h depending on direction)

**Score interpretation:**

| Score | Condition |
|-------|-----------|
| 0.5 – 1.0 | Good — tailwind, dry |
| 0.0 – 0.5 | Acceptable — light cross or headwind |
| −0.5 – 0.0 | Difficult — stronger headwind or rain |
| −1.0 – −0.5 | Bad — strong gusts or heavy rain |

---

## Project Structure

```
aeolus/
├── app/
│   ├── models.py          # Data classes (RoutePoint, Segment, Cluster, ...)
│   ├── analyzer.py        # High-level pipeline orchestration
│   └── services/
│       ├── gpx_parser.py  # GPX parsing, segmentation, clustering
│       ├── weather.py     # Open-Meteo API integration
│       └── route_scorer.py# Weather scoring logic
├── notebooks/
│   └── demo.ipynb         # Interactive demo (current primary interface)
├── tests/                 # Pytest test suite
├── data/
│   └── sample.gpx         # Example GPX file
├── pyproject.toml         # Project metadata and dependencies
└── uv.lock                # Pinned dependency versions
```

---

## Installation

### Prerequisites

- [uv](https://docs.astral.sh/uv/)

uv manages the Python toolchain itself, so no pre-installed interpreter is required.

### Setup

```bash
git clone <repo-url>
cd aeolus

uv sync --all-extras
```

This creates `.venv/` from `uv.lock` and installs all dependencies, including Jupyter, ipywidgets, and folium for the demo notebook. Drop `--all-extras` to install only the core library.

---

## Usage

> **Note:** The demo notebook is the primary way to use Aeolus right now. A full web frontend is planned for the future.

### Python API

```python
from datetime import datetime, timezone
from app.analyzer import analyze_route

with open("data/sample.gpx", "rb") as f:
    gpx_bytes = f.read()

score = analyze_route(
    gpx_file=gpx_bytes,
    avg_speed_kmh=20.0,
    start_time=datetime(2025, 6, 15, 9, 0, tzinfo=timezone.utc),
)

print(f"Route score: {score:.2f}")  # e.g. "Route score: 0.34"
```

---

## Demo Notebook

The demo notebook (`notebooks/demo.ipynb`) provides an interactive UI to upload a GPX file, set your speed and departure time, and visualize results on an interactive map — no code required.

### Running the Notebook

```bash
uv run jupyter notebook notebooks/demo.ipynb
```

Or launch with Voila for a clean app-like interface:

```bash
uv run voila notebooks/demo.ipynb
```

### Step-by-Step Guide

1. **Open the notebook** using one of the commands above
2. **Run all cells** — in Jupyter: `Kernel → Restart & Run All`; in Voila this happens automatically
3. **Upload a GPX file** using the file upload widget (a `sample.gpx` is included in `data/` to try first)
4. **Set your average speed** using the slider (1–60 km/h)
5. **Set your planned departure time** using the date/time picker (defaults to now)
6. **Click "Analyze Route"** to fetch weather and compute the score
7. **Read the results:**
   - The overall score is shown at the top
   - The interactive map shows your route colored from red (bad) to green (good)
   - Wind arrows at each cluster point indicate direction and speed
   - Arrow color indicates rain (blue = rain, gray = dry)
   - Click any arrow for a popup with wind speed, gusts, and precipitation details

### Tips

- Use a GPX file exported from Komoot, Strava, Garmin Connect, or any standard GPS tool
- The departure time must be within Open-Meteo's forecast window (roughly the next 7–16 days)
- Speed is used to estimate arrival times along the route — gradient adjustments are applied automatically
- For best results, use a route that is realistic in length for the given speed

---

## Running Tests

```bash
uv run pytest
```

The test suite covers GPX parsing, weather API integration, and scoring logic.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `gpxpy` | GPX file parsing |
| `numpy` | Numerical operations |
| `openmeteo-requests` | Open-Meteo API client |
| `jupyter` / `ipywidgets` | Interactive notebook UI |
| `folium` | Interactive maps |
| `voila` | Notebook-as-app server |

Weather data is fetched from [Open-Meteo](https://open-meteo.com/) — free, no API key required.

---

## Roadmap

- **Frontend (planned):** A complete web frontend is in development. The demo notebook is the current primary interface until the frontend is ready.
- Route optimization



