"""Tests for app/web/api.py"""

import io
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.analyzer import RouteAnalysis
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


def analysis_of(snapshots) -> RouteAnalysis:
    """Score snapshots and wrap them the way analyze_route would."""
    scores = [score_segment(s) for s in snapshots]
    return RouteAnalysis(snapshots=snapshots, scores=scores, summary=summarise(snapshots, scores))


def post(analysis: RouteAnalysis | None = None, **overrides):
    """Call the endpoint with a stubbed analysis and sensible defaults."""
    data = {
        "avg_speed_kmh": "22",
        "start_time": "2026-08-12T14:00",
        **overrides,
    }
    files = {"gpx": ("route.gpx", io.BytesIO(data.pop("gpx_bytes", GPX)), "application/gpx+xml")}

    if analysis is None:
        return client.post("/api/analyze", data=data, files=files)
    with patch("app.web.api.analyze_route", return_value=analysis):
        return client.post("/api/analyze", data=data, files=files)


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
