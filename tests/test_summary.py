"""Tests for app/services/summary.py"""

import math
import pytest
from datetime import datetime, timezone

from app.models import ClusterWeatherSnapshot, RoutePoint, Segment, SegmentCluster
from app.services.route_scorer import score_segment
from app.services.summary import NOTABLE_WIND_KM_H, summarise


def make_snapshot(
    wind_speed_km_h: float = 0.0,
    wind_direction_deg: float = 270.0,
    gust_speed_km_h: float = 0.0,
    precipitation_mm_15: float = 0.0,
    bearing_deg: float = 90.0,
    distance_m: float = 1000.0,
) -> ClusterWeatherSnapshot:
    """Build a snapshot for one cluster of a given length."""
    point = RoutePoint(lat=48.0, lon=11.0)
    segment = Segment(start=point, end=point, bearing_deg=bearing_deg, distance_m=distance_m)
    cluster = SegmentCluster(
        segments=[segment], mean_bearing=bearing_deg, representative_point=point
    )
    return ClusterWeatherSnapshot(
        cluster=cluster,
        timestamp=datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc),
        wind_speed_km_h=wind_speed_km_h,
        wind_direction_deg=wind_direction_deg,
        wind_gusts_km_h=gust_speed_km_h,
        precipitation_mm_h=precipitation_mm_15,
    )


def summarise_all(snapshots):
    """Score every snapshot and summarise the result."""
    return summarise(snapshots, [score_segment(s) for s in snapshots])


# ── Empty and trivial routes ──────────────────────────────────────

def test_empty_route_is_all_zero():
    result = summarise([], [])
    assert result.total_distance_m == 0.0
    assert result.score == 0.0

def test_empty_route_shares_do_not_divide_by_zero():
    result = summarise([], [])
    assert result.headwind_share == 0.0
    assert result.rain_share == 0.0

def test_total_distance_adds_up():
    result = summarise_all([make_snapshot(distance_m=d) for d in (1000.0, 2500.0, 500.0)])
    assert result.total_distance_m == 4000.0


# ── Wind direction attribution ────────────────────────────────────

def test_headwind_stretch_is_counted():
    """Riding east into a wind from the east."""
    result = summarise_all([make_snapshot(20.0, 90.0, 25.0, bearing_deg=90.0)])
    assert result.headwind_distance_m == 1000.0
    assert result.tailwind_distance_m == 0.0

def test_tailwind_stretch_is_counted():
    result = summarise_all([make_snapshot(20.0, 270.0, 25.0, bearing_deg=90.0)])
    assert result.tailwind_distance_m == 1000.0
    assert result.headwind_distance_m == 0.0

def test_crosswind_stretch_is_counted():
    result = summarise_all([make_snapshot(20.0, 0.0, 25.0, bearing_deg=90.0)])
    assert result.crosswind_distance_m == 1000.0

def test_light_wind_counts_as_none_of_them():
    """Below the notable threshold nothing should be claimed."""
    result = summarise_all([make_snapshot(NOTABLE_WIND_KM_H - 2.0, 90.0, bearing_deg=90.0)])
    assert result.headwind_distance_m == 0.0
    assert result.crosswind_distance_m == 0.0

def test_wind_categories_never_exceed_the_route():
    snapshots = [
        make_snapshot(20.0, 90.0, 25.0, bearing_deg=90.0),
        make_snapshot(20.0, 270.0, 25.0, bearing_deg=90.0),
        make_snapshot(20.0, 0.0, 25.0, bearing_deg=90.0),
        make_snapshot(2.0, 0.0, 3.0, bearing_deg=90.0),
    ]
    result = summarise_all(snapshots)
    counted = (
        result.headwind_distance_m + result.tailwind_distance_m + result.crosswind_distance_m
    )
    assert counted <= result.total_distance_m

def test_out_and_back_splits_head_and_tailwind():
    """The case the product exists for: wind on the way out, help coming back."""
    result = summarise_all([
        make_snapshot(22.0, 90.0, 28.0, bearing_deg=90.0, distance_m=5000.0),
        make_snapshot(22.0, 90.0, 28.0, bearing_deg=270.0, distance_m=5000.0),
    ])
    assert result.headwind_distance_m == 5000.0
    assert result.tailwind_distance_m == 5000.0


# ── Rain ──────────────────────────────────────────────────────────

def test_rain_stretch_is_counted():
    result = summarise_all([make_snapshot(precipitation_mm_15=0.5)])
    assert result.rain_distance_m == 1000.0

def test_dry_stretch_is_not_counted():
    result = summarise_all([make_snapshot(precipitation_mm_15=0.0)])
    assert result.rain_distance_m == 0.0

def test_rain_share_is_a_fraction():
    result = summarise_all([
        make_snapshot(precipitation_mm_15=0.5, distance_m=3000.0),
        make_snapshot(precipitation_mm_15=0.0, distance_m=1000.0),
    ])
    assert math.isclose(result.rain_share, 0.75)


# ── Safety and aggregates ─────────────────────────────────────────

def test_unsafe_stretch_is_counted():
    result = summarise_all([make_snapshot(30.0, 270.0, 60.0, bearing_deg=90.0)])
    assert result.unsafe_distance_m == 1000.0

def test_max_gust_is_the_worst_anywhere():
    result = summarise_all([
        make_snapshot(10.0, 270.0, 15.0),
        make_snapshot(10.0, 270.0, 41.0),
        make_snapshot(10.0, 270.0, 22.0),
    ])
    assert result.max_gust_km_h == 41.0

def test_mean_wind_is_distance_weighted():
    """A long calm stretch must outweigh a short windy one."""
    result = summarise_all([
        make_snapshot(30.0, 270.0, 35.0, distance_m=1000.0),
        make_snapshot(10.0, 270.0, 15.0, distance_m=9000.0),
    ])
    assert math.isclose(result.mean_wind_km_h, 12.0)

def test_score_is_distance_weighted():
    short_bad = make_snapshot(25.0, 90.0, 30.0, bearing_deg=90.0, distance_m=100.0)
    long_good = make_snapshot(25.0, 270.0, 30.0, bearing_deg=90.0, distance_m=9900.0)
    result = summarise_all([short_bad, long_good])

    assert result.score > 0.0
