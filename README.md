# Aeolus

Weather along a cycling route, at the times you will actually be there.

Upload a GPX file and you get a map of your route with the forecast laid over it —
rain as a field, wind as arrows, the route itself coloured by where the wind will
hit you. A slider plays the whole day in quarter-hour steps. Give it a departure
time and average speed as well, and it also marks where you would be at any
moment and what you should expect on arrival.

A weather app tells you "18 km/h from the south-west". It does not tell you that
the first 20 km of *your* loop will be a grind and the way back will fly.

**Try it: [aeolus.mbrueckner.dev](https://aeolus.mbrueckner.dev)**

---

## What is checked, and what is not

The forecast was validated against 60 recorded rides with a power meter, using
the bike itself as a wind sensor: with the rider's drag coefficients known, the
power balance can be solved for the air speed actually experienced.

**Supported by that data**

- **Where** along a route the wind hits — median correlation of 0.62 per ride
- The route's kilometres of head-, cross- and tailwind that follow from it
- Ranking conditions **within a day**: correlation of −0.58 against the extra
  power actually measured, with the best and worst thirds forty watts apart

**Not supported**

- Absolute felt wind speed. A rider experiences roughly a third of the 10 m
  forecast value, and how much depends on hedges, dips and buildings that no
  weather model resolves.
- Comparisons **between days**. Drafting and headwind look identical to a power
  meter, so this could not be measured either way — it is unknown, not refuted.
- Gusts and rain as *judgements*. Their forecasts are shown as they are; how bad
  they feel has never been checked against anything.

This is why the interface leads with distances rather than a verdict: "18 km of
headwind" is something you can confirm after the ride. A combined score exists
in `app/services/route_scorer.py` and is deliberately not displayed — the
reasoning is written up in that module.

---

## Quick start

The quickest way needs nothing but Docker:

```bash
docker compose up
```

Or run it from source:

```bash
uv sync --all-extras
npm --prefix frontend install
npm --prefix frontend run build
uv run --extra server uvicorn app.web.api:app
```

Either way, open <http://localhost:8000>. No configuration is required —
Open-Meteo needs no API key, and nothing is stored. A sample route is not included, since GPS
traces are personal data — export one from Komoot, Strava or Garmin Connect.

### Development

Run the two halves separately so the front end keeps hot reloading. Vite proxies
`/api` through to the backend.

```bash
uv run --extra server uvicorn app.web.api:app --reload
npm --prefix frontend run dev
```

### Tests

```bash
uv run pytest
npm --prefix frontend run test
```

---

## How it works

1. **Parse** — read the GPX track at full resolution
2. **Cluster** — group it into stretches of similar bearing, roughly a quarter
   hour of riding each, so each stretch gets its own forecast
3. **Fetch** — pull a grid of 15-minute forecasts covering the route's
   surroundings for the whole day, in one or two requests
4. **Project** — resolve the wind onto each stretch's direction of travel, which
   is what turns "from the south-west" into "a headwind here, a tailwind there"

Distances are measured along the recorded track rather than the simplified one
used for clustering; cutting the corners off a winding route loses a few percent.

---

## Project structure

```
aeolus/
├── app/
│   ├── models.py            # RoutePoint, Segment, SegmentCluster, ClusteredRoute
│   ├── analyzer.py          # Pipeline: parse, cluster, fetch, score
│   ├── services/
│   │   ├── gpx_parser.py    # Parsing, simplification, clustering
│   │   ├── weather.py       # Forecast per cluster, at its arrival time
│   │   ├── weather_field.py # Forecast grid covering the route, for the overlay
│   │   ├── route_scorer.py  # Scoring model (kept, not displayed)
│   │   └── summary.py       # Route-level facts a rider can check afterwards
│   ├── calibration/         # Research track, see below
│   └── web/api.py           # HTTP interface
├── frontend/                # React, Vite, Tailwind, DaisyUI, Leaflet
├── scripts/inspect_fit.py   # What a Garmin FIT file actually contains
└── tests/
```

---

## Calibration

`app/calibration/` is the machinery behind the numbers in the first section. It
is not part of the web service and is not needed to run it.

- `power.py` — the cycling power balance. Dividing it by ground speed makes it
  linear in CdA and Crr, so both fall out of a least-squares fit; the same
  equation then inverts for air speed, which is what turns a power meter into a
  wind sensor.
- `rides.py` — reads FIT files into arrays, smoothing gradient and acceleration
  over windows wide enough to survive barometric noise.
- `weather_archive.py` — Open-Meteo's Historical Forecast archive, cached on
  disk. Not the ERA5 endpoint, whose ~25 km grid is too coarse for wind on a
  bike.

Radar tiles cannot help here: they reach an hour or two ahead at most, because
radar measures rain rather than predicting it.

---

## Roadmap

- **Departure and direction advice** — "ride it the other way round" and "start
  two hours later" need only the relative wind along a route, which is the part
  that is actually supported by the data. This is the next thing to build.
- **Calibrating the subjective half** — how much gusts and rain *bother* a rider
  cannot be measured in watts. Pairwise comparisons would settle it, and only a
  handful of parameters remain open now that the physics is handled.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `gpxpy` | GPX parsing |
| `numpy` | Numerical work |
| `openmeteo-requests` | Open-Meteo API client |
| `fastapi` / `uvicorn` | HTTP service (`web` extra) |
| `garmin-fit-sdk` | Reading FIT files (`analysis` extra) |
| `react` / `leaflet` / `tailwindcss` | Front end |

Weather data from [Open-Meteo](https://open-meteo.com/), map tiles from
OpenStreetMap.
