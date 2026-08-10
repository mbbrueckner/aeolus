"""HTTP interface for route weather analysis.

One endpoint turns an uploaded GPX file into the forecast along the route. The
built React front end is served alongside it when it exists.

In development, run the two separately so the front end keeps hot reloading;
Vite proxies /api through to here:

    uv run --extra web uvicorn app.web.api:app --reload
    npm --prefix frontend run dev

For a single-process deployment, build the front end first and this module
serves it:

    npm --prefix frontend run build
"""

__author__ = "mbbrueckner"
__version__ = "1.0.0"

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from app.analyzer import RouteAnalysis, analyze_route
from app.services.summary import rain_tier

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MIN_SPEED_KMH = 5.0
MAX_SPEED_KMH = 60.0

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

app = FastAPI(title="Aeolus", description="Weather along your route")


@app.post("/api/analyze")
async def analyze(
    gpx: UploadFile = File(...),
    avg_speed_kmh: float = Form(20.0),
    start_time: str = Form(...),
) -> dict:
    """Analyze an uploaded GPX route against the forecast.

    Args:
        gpx: The uploaded GPX file.
        avg_speed_kmh: Average riding speed, used to estimate arrival times.
        start_time: Departure time in ISO 8601. A naive value is read as UTC.

    Returns:
        The route, its per-cluster forecast, and the summary.

    Raises:
        HTTPException: If the upload is too large, the speed is out of range,
            the time cannot be parsed, or the GPX holds no usable track.
    """
    if not MIN_SPEED_KMH <= avg_speed_kmh <= MAX_SPEED_KMH:
        raise HTTPException(
            422, f"avg_speed_kmh must be between {MIN_SPEED_KMH} and {MAX_SPEED_KMH}"
        )

    content = await gpx.read()
    if not content:
        raise HTTPException(422, "the uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "the uploaded file is too large")

    try:
        departure = datetime.fromisoformat(start_time)
    except ValueError:
        raise HTTPException(422, "start_time must be an ISO 8601 timestamp")
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)

    try:
        analysis = analyze_route(content, avg_speed_kmh, departure)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(422, f"could not analyze this route: {error}")

    if not analysis.snapshots:
        raise HTTPException(422, "the GPX file contains no usable track")

    return _to_payload(analysis)


def _to_payload(analysis: RouteAnalysis) -> dict:
    """Convert an analysis into the JSON the front end consumes.

    Args:
        analysis: The scored route.

    Returns:
        Nested dicts of plain types.
    """
    summary = analysis.summary

    return {
        "summary": {
            "total_distance_km": summary.total_distance_m / 1000.0,
            "headwind_km": summary.headwind_distance_m / 1000.0,
            "tailwind_km": summary.tailwind_distance_m / 1000.0,
            "crosswind_km": summary.crosswind_distance_m / 1000.0,
            "rain_km": summary.rain_distance_m / 1000.0,
            "light_rain_km": summary.light_rain_distance_m / 1000.0,
            "moderate_rain_km": summary.moderate_rain_distance_m / 1000.0,
            "heavy_rain_km": summary.heavy_rain_distance_m / 1000.0,
            "rain_start_km": (
                summary.rain_start_m / 1000.0 if summary.rain_start_m is not None else None
            ),
            "rain_start_time": _isoformat(summary.rain_start_time),
            "max_precipitation_mm_h": summary.max_precipitation_mm_h,
            "unsafe_km": summary.unsafe_distance_m / 1000.0,
            "headwind_share": summary.headwind_share,
            "tailwind_share": summary.tailwind_share,
            "rain_share": summary.rain_share,
            "mean_wind_km_h": summary.mean_wind_km_h,
            "max_gust_km_h": summary.max_gust_km_h,
            "score": summary.score,
            "arrival": _isoformat(analysis.snapshots[-1].timestamp),
        },
        "segments": [
            {
                "coordinates": _coordinates(snapshot),
                "point": [
                    snapshot.cluster.representative_point.lat,
                    snapshot.cluster.representative_point.lon,
                ],
                "time": _isoformat(snapshot.timestamp),
                "distance_km": snapshot.cluster.total_distance_m / 1000.0,
                "bearing_deg": snapshot.cluster.mean_bearing,
                "wind_speed_km_h": snapshot.wind_speed_km_h,
                "wind_direction_deg": snapshot.wind_direction_deg,
                "wind_gusts_km_h": snapshot.wind_gusts_km_h,
                "precipitation_mm_h": score.precipitation_mm_h,
                "rain_tier": rain_tier(score.precipitation_mm_h),
                "alignment": score.alignment.value,
                "tailwind_km_h": score.tailwind_km_h,
                "crosswind_km_h": score.crosswind_km_h,
                "score": score.score,
                "unsafe": score.unsafe,
            }
            for snapshot, score in zip(analysis.snapshots, analysis.scores)
        ],
    }


def _coordinates(snapshot) -> list[list[float]]:
    """Extract a cluster's polyline.

    Args:
        snapshot: The cluster's weather snapshot.

    Returns:
        Latitude and longitude pairs from the cluster's first point onwards.
    """
    segments = snapshot.cluster.segments
    if not segments:
        return []
    return [[segments[0].start.lat, segments[0].start.lon]] + [
        [segment.end.lat, segment.end.lon] for segment in segments
    ]


def _isoformat(moment: datetime | None) -> str | None:
    """Render a timestamp for the front end.

    Args:
        moment: The timestamp, or None.

    Returns:
        ISO 8601 text, or None.
    """
    return moment.isoformat() if moment else None


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
