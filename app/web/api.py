"""HTTP interface for route weather analysis.

One endpoint turns an uploaded GPX file into the forecast along the route. The
built React front end is served alongside it when it exists.

A departure time and average speed are optional. Without them the answer is a
weather map of the route that the rider reads themselves; with them it also
carries what the conditions are expected to be at each point on arrival.

In development, run the two separately so the front end keeps hot reloading;
Vite proxies /api through to here:

    uv run --extra web uvicorn app.web.api:app --reload
    npm --prefix frontend run dev

For a single-process deployment, build the front end first and this module
serves it:

    npm --prefix frontend run build
"""

__author__ = "mbbrueckner"
__version__ = "2.0.0"

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.analyzer import RouteAnalysis, analyze_route
from app.models import ClusteredRoute, ClusterWeatherSnapshot, SegmentCluster
from app.services.gpx_parser import get_clustered_route
from app.services.route_scorer import SegmentScore
from app.services.summary import RouteSummary, rain_tier
from app.services.weather_field import WeatherField, fetch_field, route_bounds
from app.web.rate_limit import Limit, SlidingWindow, client_key

def _fail(status: int, code: str, message: str) -> HTTPException:
    """Build an error the front end can translate.

    Args:
        status: HTTP status code.
        code: Stable identifier the client maps to a localised message.
        message: English fallback, for clients that do not know the code.

    Returns:
        The exception to raise.
    """
    return HTTPException(status, {"code": code, "message": message})


# Vercel rejects request bodies over 4.5 MB before they reach the function, so
# refusing a little earlier here turns a platform error into a clear message.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MIN_SPEED_KMH = 5.0
MAX_SPEED_KMH = 60.0

# Only used to decide how finely to chop a route for display when the rider
# has not said how fast they ride.
NOMINAL_SPEED_KMH = 20.0

# One analysis costs one to three upstream forecast requests. The per-client
# allowance is generous for a person and tight for a refresh loop; the global
# one is what the forecast quota actually depends on.
CLIENT_LIMIT = Limit(requests=20, per_seconds=600)
GLOBAL_LIMIT = Limit(requests=300, per_seconds=3600)

_per_client = SlidingWindow(CLIENT_LIMIT)
_overall = SlidingWindow(GLOBAL_LIMIT)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

app = FastAPI(title="Aeolus", description="Weather along your route")

# The weather field is a few hundred kilobytes of numbers and compresses well.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.post("/api/analyze")
async def analyze(
    request: Request,
    gpx: UploadFile = File(...),
    avg_speed_kmh: float | None = Form(None),
    start_time: str | None = Form(None),
) -> dict:
    """Analyze an uploaded GPX route against the forecast.

    Args:
        request: The incoming request, for rate limiting.
        gpx: The uploaded GPX file.
        avg_speed_kmh: Average riding speed. Given together with a departure
            time, the response also carries conditions at each point on
            arrival.
        start_time: Departure time in ISO 8601. A naive value is read as UTC.

    Returns:
        The route, the weather field covering it, and — when a ride was
        described — the per-cluster forecast and summary.

    Raises:
        HTTPException: If the upload is unusable or the inputs are out of range.
    """
    _enforce_limits(request)

    content = await _read_upload(gpx)
    departure = _parse_start_time(start_time)
    speed = _validate_speed(avg_speed_kmh)

    describes_a_ride = departure is not None and speed is not None
    reference = departure or datetime.now(timezone.utc)

    try:
        if describes_a_ride:
            # Parsing and the upstream forecast call both block. Off the event
            # loop they go, or one request would stall every other one.
            analysis = await run_in_threadpool(analyze_route, content, speed, departure)
            route, snapshots, scores, summary = (
                analysis.route,
                analysis.snapshots,
                analysis.scores,
                analysis.summary,
            )
        else:
            route = await run_in_threadpool(
                get_clustered_route, content, speed or NOMINAL_SPEED_KMH, reference
            )
            snapshots, scores, summary = None, None, None
    except HTTPException:
        raise
    except Exception as error:
        raise _fail(422, "unreadable_route", f"could not analyze this route: {error}")

    if not route.clusters:
        raise _fail(422, "empty_route", "the GPX file contains no usable track")

    payload = _to_payload(route, snapshots, scores, summary)
    payload["field"] = await run_in_threadpool(_fetch_field_for, route, reference)
    return payload


def _enforce_limits(request: Request) -> None:
    """Reject the request if either allowance is spent.

    Args:
        request: The incoming request.

    Raises:
        HTTPException: With 429 and a Retry-After header when over the limit.
    """
    peer = request.client.host if request.client else None
    for window, key in ((_overall, ""), (_per_client, client_key(request.headers, peer))):
        wait = window.retry_after(key)
        if wait is not None:
            raise HTTPException(
                429,
                {"code": "rate_limited", "message": "too many requests, try again shortly"},
                headers={"Retry-After": str(max(1, int(wait) + 1))},
            )


async def _read_upload(gpx: UploadFile) -> bytes:
    """Read and sanity-check the uploaded file.

    Args:
        gpx: The uploaded file.

    Returns:
        Its contents.

    Raises:
        HTTPException: If the file is empty or too large.
    """
    content = await gpx.read()
    if not content:
        raise _fail(422, "empty_upload", "the uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise _fail(413, "too_large", "the uploaded file is too large")
    return content


def _parse_start_time(start_time: str | None) -> datetime | None:
    """Parse an optional departure time.

    Args:
        start_time: ISO 8601 text, or None.

    Returns:
        A timezone-aware datetime, or None if none was given.

    Raises:
        HTTPException: If the text cannot be parsed.
    """
    if not start_time:
        return None
    try:
        parsed = datetime.fromisoformat(start_time)
    except ValueError:
        raise _fail(422, "bad_start_time", "start_time must be an ISO 8601 timestamp")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _validate_speed(avg_speed_kmh: float | None) -> float | None:
    """Check an optional average speed.

    Args:
        avg_speed_kmh: Speed in km/h, or None.

    Returns:
        The speed, or None if none was given.

    Raises:
        HTTPException: If the speed is outside the plausible range.
    """
    if avg_speed_kmh is None:
        return None
    if not MIN_SPEED_KMH <= avg_speed_kmh <= MAX_SPEED_KMH:
        raise _fail(
            422,
            "bad_speed",
            f"avg_speed_kmh must be between {MIN_SPEED_KMH} and {MAX_SPEED_KMH}",
        )
    return avg_speed_kmh


def _fetch_field_for(route: ClusteredRoute, reference: datetime) -> dict | None:
    """Fetch the weather field covering the route.

    A missing field only costs the map its overlay, so a failure here must not
    take the route down with it.

    Args:
        route: The clustered route.
        reference: A time on the day to cover.

    Returns:
        The field as plain types, or None if it could not be fetched.
    """
    points = [c.representative_point for c in route.clusters]
    arrivals = [p.timestamp for p in points if p.timestamp]
    last = max(arrivals) if arrivals else reference

    try:
        field = fetch_field(route_bounds(points), reference.date(), last.date())
    except Exception:
        return None

    return _field_payload(field)


def _field_payload(field: WeatherField) -> dict:
    """Round the field for transport.

    One decimal is well inside the forecast's own uncertainty and keeps the
    payload a fraction of the size.

    Args:
        field: The weather field.

    Returns:
        Nested lists of plain floats.
    """
    def rounded(values: np.ndarray, decimals: int = 1) -> list:
        return np.round(values, decimals).tolist()

    return {
        "latitudes": field.latitudes,
        "longitudes": field.longitudes,
        "slots": field.slots,
        "precipitation_mm_h": rounded(field.precipitation_mm_h, 2),
        "wind_u_m_s": rounded(field.wind_u_m_s),
        "wind_v_m_s": rounded(field.wind_v_m_s),
        "wind_gusts_m_s": rounded(field.wind_gusts_m_s),
        "precipitation_probability": rounded(field.precipitation_probability, 0),
    }


def _to_payload(
    route: ClusteredRoute,
    snapshots: list[ClusterWeatherSnapshot] | None,
    scores: list[SegmentScore] | None,
    summary: RouteSummary | None,
) -> dict:
    """Convert a route, and any ride analysis, into the JSON the front end reads.

    Args:
        route: The clustered route.
        snapshots: Weather per cluster, or None if no ride was described.
        scores: Score per cluster, or None.
        summary: Route-level facts, or None.

    Returns:
        Nested dicts of plain types.
    """
    covered_m = 0.0
    start_distances = []
    for cluster in route.clusters:
        start_distances.append(covered_m)
        covered_m += cluster.total_distance_m

    arrivals = list(zip(snapshots, scores)) if snapshots and scores else None

    return {
        "route": [[p.lat, p.lon] for p in route.track],
        "summary": _summary_payload(summary) if summary else None,
        "segments": [
            _segment_payload(
                route,
                cluster,
                start_km,
                arrivals[i] if arrivals else None,
            )
            for i, (cluster, start_km) in enumerate(
                zip(route.clusters, [d / 1000.0 for d in start_distances])
            )
        ],
    }


def _segment_payload(
    route: ClusteredRoute,
    cluster: SegmentCluster,
    start_km: float,
    arrival: tuple[ClusterWeatherSnapshot, SegmentScore] | None,
) -> dict:
    """Describe one stretch of the route.

    Geometry is always present. The weather fields are filled only when a
    departure time and speed were given, since without them there is no
    arrival time to look a forecast up for.

    Args:
        route: The clustered route, for the full-resolution geometry.
        cluster: The stretch to describe.
        start_km: Distance from the route's start to this stretch.
        arrival: Weather and score at the estimated arrival, or None.

    Returns:
        The stretch as plain types.
    """
    payload = {
        "coordinates": [[p.lat, p.lon] for p in route.points_for(cluster)],
        "point": [cluster.representative_point.lat, cluster.representative_point.lon],
        "distance_km": cluster.total_distance_m / 1000.0,
        "start_distance_km": start_km,
        "mid_distance_km": start_km + cluster.total_distance_m / 2000.0,
        "bearing_deg": cluster.mean_bearing,
        "entry_time": _isoformat(cluster.entry_time),
        "exit_time": _isoformat(cluster.exit_time),
        "time": None,
        "wind_speed_km_h": None,
        "wind_direction_deg": None,
        "wind_gusts_km_h": None,
        "precipitation_mm_h": None,
        "rain_tier": None,
        "alignment": None,
        "tailwind_km_h": None,
        "crosswind_km_h": None,
        "score": None,
        "unsafe": False,
    }

    if arrival is None:
        return payload

    snapshot, score = arrival
    payload.update(
        {
            "time": _isoformat(snapshot.timestamp),
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
    )
    return payload


def _summary_payload(summary: RouteSummary) -> dict:
    """Convert the route summary for transport.

    Args:
        summary: Route-level facts.

    Returns:
        The summary as plain types, with distances in kilometres.
    """
    return {
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
    }


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
