"""Tests for app/web/api.py"""

import io
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.analyzer import RouteAnalysis
from app.models import ClusteredRoute, ClusterWeatherSnapshot, RoutePoint, Segment, SegmentCluster
from app.services.route_scorer import score_segment
from app.services.summary import summarise
from app.web.api import app
from test_summary import make_snapshot

client = TestClient(app)

GPX = b"""<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
<trkpt lat="48.10" lon="11.50"><ele>500</ele></trkpt>
<trkpt lat="48.20" lon="11.60"><ele>510</ele></trkpt>
</trkseg></trk></gpx>"""


def analysis_of(snapshots, track=None) -> RouteAnalysis:
    """Score snapshots and wrap them the way analyze_route would."""
    scores = [score_segment(s) for s in snapshots]
    route = ClusteredRoute(
        clusters=[s.cluster for s in snapshots],
        track=track or [],
    )
    return RouteAnalysis(
        route=route,
        snapshots=snapshots,
        scores=scores,
        summary=summarise(snapshots, scores),
    )


def post(analysis: RouteAnalysis | None = None, field=None, **overrides):
    """Call the endpoint with a stubbed analysis and sensible defaults.

    The weather field is stubbed too, so the suite never touches the network.
    """
    data = {
        "avg_speed_kmh": "22",
        "start_time": "2026-08-12T14:00",
        **overrides,
    }
    files = {"gpx": ("route.gpx", io.BytesIO(data.pop("gpx_bytes", GPX)), "application/gpx+xml")}

    with patch("app.web.api.fetch_field", side_effect=field or _no_field):
        if analysis is None:
            return client.post("/api/analyze", data=data, files=files)
        with patch("app.web.api.analyze_route", return_value=analysis):
            return client.post("/api/analyze", data=data, files=files)


def _no_field(*args, **kwargs):
    """Stand in for an unreachable forecast field."""
    raise RuntimeError("field unavailable")


# ── Input validation ──────────────────────────────────────────────

def test_speed_below_range_is_rejected():
    assert post(avg_speed_kmh="2").status_code == 422

def test_speed_above_range_is_rejected():
    assert post(avg_speed_kmh="200").status_code == 422

def test_unparseable_time_is_rejected():
    response = post(start_time="letzten Dienstag")
    assert response.status_code == 422
    assert "ISO 8601" in response.json()["detail"]

def test_empty_upload_is_rejected():
    response = post(gpx_bytes=b"")
    assert response.status_code == 422

def test_garbage_gpx_is_rejected_with_a_message():
    response = post(gpx_bytes=b"this is not gpx")
    assert response.status_code == 422
    assert response.json()["detail"]

def test_route_without_clusters_is_rejected():
    response = post(analysis_of([]))
    assert response.status_code == 422


# ── Payload shape ─────────────────────────────────────────────────

def test_successful_analysis_returns_segments():
    response = post(analysis_of([make_snapshot(20.0, 90.0, 25.0, bearing_deg=90.0)]))
    assert response.status_code == 200
    assert len(response.json()["segments"]) == 1

def test_segment_carries_what_the_map_needs():
    response = post(analysis_of([make_snapshot(20.0, 90.0, 25.0, bearing_deg=90.0)]))
    segment = response.json()["segments"][0]

    for field in ("coordinates", "point", "time", "wind_speed_km_h", "alignment", "unsafe"):
        assert field in segment, field

def test_distances_are_reported_in_kilometres():
    response = post(analysis_of([make_snapshot(distance_m=2500.0)]))
    assert response.json()["summary"]["total_distance_km"] == 2.5

def test_headwind_and_tailwind_are_distinguished():
    response = post(analysis_of([
        make_snapshot(22.0, 90.0, 28.0, bearing_deg=90.0, distance_m=4000.0),
        make_snapshot(22.0, 90.0, 28.0, bearing_deg=270.0, distance_m=6000.0),
    ]))
    summary = response.json()["summary"]

    assert summary["headwind_km"] == 4.0
    assert summary["tailwind_km"] == 6.0


# ── Rain ──────────────────────────────────────────────────────────

def test_dry_route_reports_no_rain():
    response = post(analysis_of([make_snapshot()]))
    summary = response.json()["summary"]

    assert summary["rain_km"] == 0.0
    assert summary["rain_start_km"] is None
    assert summary["rain_start_time"] is None

def test_segment_carries_its_rain_tier():
    response = post(analysis_of([make_snapshot(precipitation_mm_15=1.0)]))
    assert response.json()["segments"][0]["rain_tier"] == "moderate"

def test_dry_segment_has_no_tier():
    response = post(analysis_of([make_snapshot(precipitation_mm_15=0.0)]))
    assert response.json()["segments"][0]["rain_tier"] is None

def test_rain_tiers_are_reported_separately():
    response = post(analysis_of([
        make_snapshot(precipitation_mm_15=0.2, distance_m=1000.0),
        make_snapshot(precipitation_mm_15=1.0, distance_m=2000.0),
        make_snapshot(precipitation_mm_15=4.0, distance_m=3000.0),
    ]))
    summary = response.json()["summary"]

    assert summary["light_rain_km"] == 1.0
    assert summary["moderate_rain_km"] == 2.0
    assert summary["heavy_rain_km"] == 3.0
    assert summary["rain_km"] == 6.0

def test_rain_onset_is_reported_in_kilometres_and_time():
    response = post(analysis_of([
        make_snapshot(distance_m=3000.0),
        make_snapshot(precipitation_mm_15=1.0, distance_m=2000.0),
    ]))
    summary = response.json()["summary"]

    assert summary["rain_start_km"] == 3.0
    assert summary["rain_start_time"] is not None

def test_peak_precipitation_is_reported():
    response = post(analysis_of([
        make_snapshot(precipitation_mm_15=0.5),
        make_snapshot(precipitation_mm_15=3.0),
    ]))
    assert response.json()["summary"]["max_precipitation_mm_h"] == 12.0


# ── Weather field ─────────────────────────────────────────────────

def stub_field(*_args, **_kwargs):
    """A tiny two-by-two field with one slot."""
    import numpy as np
    from app.services.weather_field import WeatherField

    ones = np.ones((2, 2, 1))
    return WeatherField(
        latitudes=[48.0, 48.2],
        longitudes=[11.0, 11.3],
        slots=[1_770_000_000],
        precipitation_mm_h=ones * 1.234,
        wind_u_m_s=ones * 3.456,
        wind_v_m_s=ones * -1.5,
        wind_gusts_m_s=ones * 7.0,
        precipitation_probability=ones * 55.0,
    )


def test_field_is_included_when_available():
    response = post(analysis_of([make_snapshot()]), field=stub_field)
    field = response.json()["field"]

    assert field["latitudes"] == [48.0, 48.2]
    assert field["slots"] == [1_770_000_000]

def test_field_arrays_are_shaped_rows_columns_slots():
    response = post(analysis_of([make_snapshot()]), field=stub_field)
    grid = response.json()["field"]["precipitation_mm_h"]

    assert len(grid) == 2
    assert len(grid[0]) == 2
    assert len(grid[0][0]) == 1

def test_field_values_are_rounded_for_transport():
    response = post(analysis_of([make_snapshot()]), field=stub_field)
    field = response.json()["field"]

    assert field["precipitation_mm_h"][0][0][0] == 1.23
    assert field["wind_u_m_s"][0][0][0] == 3.5

def test_route_still_analyses_when_the_field_fails():
    """Losing the overlay must not cost the whole answer."""
    response = post(analysis_of([make_snapshot()]))

    assert response.status_code == 200
    assert response.json()["field"] is None
    assert response.json()["segments"]


# ── Route geometry ────────────────────────────────────────────────

def test_route_polyline_is_returned():
    track = [RoutePoint(lat=48.0 + i * 0.01, lon=11.0, track_index=i) for i in range(5)]
    response = post(analysis_of([make_snapshot()], track=track), field=stub_field)

    assert response.json()["route"] == [[p.lat, p.lon] for p in track]

def test_segments_carry_their_position_along_the_route():
    response = post(analysis_of([
        make_snapshot(distance_m=2000.0),
        make_snapshot(distance_m=4000.0),
    ]), field=stub_field)
    segments = response.json()["segments"]

    assert segments[0]["start_distance_km"] == 0.0
    assert segments[0]["mid_distance_km"] == 1.0
    assert segments[1]["start_distance_km"] == 2.0
    assert segments[1]["mid_distance_km"] == 4.0


# ── Full-resolution geometry ──────────────────────────────────────

def detailed_route(corner_points: int = 40):
    """A cluster whose two endpoints hide many points in between.

    Simplification keeps only the ends of a straight-ish run, so drawing from
    the simplified track cuts every corner the rider actually rode.
    """
    track = [
        RoutePoint(lat=48.0 + i * 0.001, lon=11.0 + (i % 2) * 0.002, track_index=i)
        for i in range(corner_points)
    ]
    segment = Segment(start=track[0], end=track[-1], bearing_deg=45.0, distance_m=5000.0)
    cluster = SegmentCluster(
        segments=[segment], mean_bearing=45.0, representative_point=track[len(track) // 2]
    )
    snapshot = ClusterWeatherSnapshot(
        cluster=cluster,
        timestamp=datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc),
        wind_speed_km_h=20.0,
        wind_direction_deg=90.0,
        wind_gusts_km_h=25.0,
        precipitation_mm_h=0.0,
    )
    return track, snapshot


def test_route_is_drawn_at_full_resolution():
    track, snapshot = detailed_route(40)
    response = post(analysis_of([snapshot], track=track), field=stub_field)

    assert len(response.json()["route"]) == 40

def test_segment_geometry_follows_the_recorded_track():
    """The bug: a cluster was drawn as a straight line between its endpoints."""
    track, snapshot = detailed_route(40)
    response = post(analysis_of([snapshot], track=track), field=stub_field)
    coordinates = response.json()["segments"][0]["coordinates"]

    assert len(coordinates) == 40
    assert coordinates[0] == [track[0].lat, track[0].lon]
    assert coordinates[-1] == [track[-1].lat, track[-1].lon]

def test_geometry_falls_back_when_no_track_is_available():
    track, snapshot = detailed_route(40)
    response = post(analysis_of([snapshot]), field=stub_field)

    assert len(response.json()["segments"][0]["coordinates"]) == 2


# ── Optional ride details ─────────────────────────────────────────

def post_without_ride(**overrides):
    """Upload a route without saying when or how fast it will be ridden."""
    data = {**overrides}
    files = {"gpx": ("route.gpx", io.BytesIO(GPX), "application/gpx+xml")}
    with patch("app.web.api.fetch_field", side_effect=stub_field):
        return client.post("/api/analyze", data=data, files=files)


def test_route_alone_is_enough():
    response = post_without_ride()
    assert response.status_code == 200
    assert response.json()["segments"]

def test_route_alone_still_carries_the_field():
    assert post_without_ride().json()["field"] is not None

def test_route_alone_has_no_summary():
    assert post_without_ride().json()["summary"] is None

def test_route_alone_has_geometry_but_no_arrival_weather():
    segment = post_without_ride().json()["segments"][0]

    assert segment["coordinates"]
    assert segment["bearing_deg"] is not None
    assert segment["time"] is None
    assert segment["wind_speed_km_h"] is None

def test_a_time_without_a_speed_is_still_route_only():
    """Both are needed to place the rider, so one alone changes nothing."""
    assert post_without_ride(start_time="2026-08-12T14:00").json()["summary"] is None

def test_a_speed_without_a_time_is_still_route_only():
    assert post_without_ride(avg_speed_kmh="22").json()["summary"] is None

def test_an_implausible_speed_is_rejected_even_without_a_time():
    assert post_without_ride(avg_speed_kmh="99").status_code == 422
