"""Tests for app/services/route_scorer.py"""

import math
import pytest
from datetime import datetime, timezone
from app.models import RoutePoint, Segment, SegmentCluster, ClusterWeatherSnapshot
from app.services.route_scorer import (
    DEFAULT_PARAMS,
    ScoringParams,
    WindAlignment,
    _deg_to_vector,
    _gust_score,
    _invert_wind_direction,
    _mm_15_to_mm_h,
    _rain_score,
    _wind_components,
    score_segment,
)


# --- Fixtures ---

def make_snapshot(
    wind_speed_km_h: float,
    wind_direction_deg: float,
    gust_speed_km_h: float,
    precipitation_mm_15: float,
    bearing_deg: float,
) -> ClusterWeatherSnapshot:
    """Build a minimal ClusterWeatherSnapshot for scoring tests."""
    p = RoutePoint(lat=48.0, lon=11.0)
    segment = Segment(start=p, end=p, bearing_deg=bearing_deg, distance_m=1000.0)
    cluster = SegmentCluster(
        segments=[segment],
        mean_bearing=bearing_deg,
        representative_point=p,
    )
    return ClusterWeatherSnapshot(
        cluster=cluster,
        timestamp=datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc),
        wind_speed_km_h=wind_speed_km_h,
        wind_direction_deg=wind_direction_deg,
        wind_gusts_km_h=gust_speed_km_h,
        precipitation_mm_h=precipitation_mm_15,
    )


def score_of(**kwargs) -> float:
    """Score value for a snapshot built from keyword arguments."""
    return score_segment(make_snapshot(**kwargs)).score


# ── _invert_wind_direction ────────────────────────────────────────

def test_invert_wind_direction_basic():
    assert _invert_wind_direction(0.0) == 180.0

def test_invert_wind_direction_wraps():
    assert _invert_wind_direction(270.0) == 90.0

def test_invert_wind_direction_full_circle():
    assert _invert_wind_direction(180.0) == 0.0

def test_invert_wind_direction_no_negative():
    """Result should always be in 0–360, never negative."""
    assert 0.0 <= _invert_wind_direction(0.0) < 360.0
    assert 0.0 <= _invert_wind_direction(359.0) < 360.0


# ── _deg_to_vector ────────────────────────────────────────────────

def test_deg_to_vector_north():
    x, y = _deg_to_vector(0.0)
    assert math.isclose(x, 0.0, abs_tol=1e-9)
    assert math.isclose(y, 1.0, abs_tol=1e-9)

def test_deg_to_vector_east():
    x, y = _deg_to_vector(90.0)
    assert math.isclose(x, 1.0, abs_tol=1e-9)
    assert math.isclose(y, 0.0, abs_tol=1e-9)

def test_deg_to_vector_south():
    x, y = _deg_to_vector(180.0)
    assert math.isclose(x, 0.0, abs_tol=1e-9)
    assert math.isclose(y, -1.0, abs_tol=1e-9)

def test_deg_to_vector_west():
    x, y = _deg_to_vector(270.0)
    assert math.isclose(x, -1.0, abs_tol=1e-9)
    assert math.isclose(y, 0.0, abs_tol=1e-9)

def test_deg_to_vector_unit_length():
    """All vectors must have length 1.0."""
    for deg in [0, 45, 90, 135, 180, 225, 270, 315]:
        x, y = _deg_to_vector(float(deg))
        assert math.isclose(x**2 + y**2, 1.0, abs_tol=1e-9)


# ── _mm_15_to_mm_h ────────────────────────────────────────────────

def test_mm_15_to_mm_h():
    assert _mm_15_to_mm_h(5.0) == 20.0

def test_mm_15_to_mm_h_zero():
    assert _mm_15_to_mm_h(0.0) == 0.0

def test_mm_15_to_mm_h_factor():
    """Conversion factor must always be exactly 4."""
    for val in [0.1, 1.0, 2.5, 10.0]:
        assert math.isclose(_mm_15_to_mm_h(val), val * 4.0)


# ── _wind_components ──────────────────────────────────────────────

def test_components_pure_tailwind():
    """Wind from west while riding east is a full tailwind."""
    tail, cross = _wind_components(20.0, 270.0, 90.0)
    assert math.isclose(tail, 20.0, abs_tol=1e-9)
    assert math.isclose(cross, 0.0, abs_tol=1e-9)

def test_components_pure_headwind():
    tail, cross = _wind_components(20.0, 90.0, 90.0)
    assert math.isclose(tail, -20.0, abs_tol=1e-9)
    assert math.isclose(cross, 0.0, abs_tol=1e-9)

def test_components_pure_crosswind():
    tail, cross = _wind_components(20.0, 0.0, 90.0)
    assert math.isclose(tail, 0.0, abs_tol=1e-9)
    assert math.isclose(cross, 20.0, abs_tol=1e-9)

def test_components_preserve_magnitude():
    """The two components must always recombine to the wind speed."""
    for direction in range(0, 360, 15):
        tail, cross = _wind_components(25.0, float(direction), 90.0)
        assert math.isclose(math.hypot(tail, cross), 25.0, abs_tol=1e-9)

def test_components_crosswind_never_negative():
    for direction in range(0, 360, 15):
        _, cross = _wind_components(25.0, float(direction), 90.0)
        assert cross >= 0.0


# ── Normalfälle ───────────────────────────────────────────────────

def test_calm_weather_scores_neutral():
    """No wind, no rain, no gusts → exactly neutral."""
    score = score_of(
        wind_speed_km_h=0.0,
        wind_direction_deg=270.0,
        gust_speed_km_h=0.0,
        precipitation_mm_15=0.0,
        bearing_deg=90.0,
    )
    assert math.isclose(score, 0.0, abs_tol=1e-9)

def test_light_wind_dry_day_is_not_penalised():
    """A calm dry day with a normal gust factor must not score negative.

    Regression test: the previous model penalised every segment where gusts
    exceeded the mean wind, which is almost always true, so ordinary good
    conditions were dragged below zero.
    """
    score = score_of(
        wind_speed_km_h=10.0,
        wind_direction_deg=0.0,
        gust_speed_km_h=14.0,
        precipitation_mm_15=0.0,
        bearing_deg=90.0,
    )
    assert score > -0.15

def test_perfect_tailwind_scores_positive():
    score = score_of(
        wind_speed_km_h=20.0,
        wind_direction_deg=270.0,
        gust_speed_km_h=26.0,
        precipitation_mm_15=0.0,
        bearing_deg=90.0,
    )
    assert score > 0.3

def test_perfect_headwind_scores_negative():
    score = score_of(
        wind_speed_km_h=20.0,
        wind_direction_deg=90.0,
        gust_speed_km_h=26.0,
        precipitation_mm_15=0.0,
        bearing_deg=90.0,
    )
    assert score < -0.3

def test_headwind_costs_more_than_tailwind_gives():
    """Asymmetry: you lose more into the wind than you gain with it."""
    tail = score_of(
        wind_speed_km_h=25.0, wind_direction_deg=270.0,
        gust_speed_km_h=25.0, precipitation_mm_15=0.0, bearing_deg=90.0,
    )
    head = score_of(
        wind_speed_km_h=25.0, wind_direction_deg=90.0,
        gust_speed_km_h=25.0, precipitation_mm_15=0.0, bearing_deg=90.0,
    )
    assert abs(head) > tail

def test_storm_with_tailwind_does_not_score_well():
    """Strong wind is unpleasant whichever way it blows."""
    score = score_of(
        wind_speed_km_h=45.0,
        wind_direction_deg=270.0,
        gust_speed_km_h=58.0,
        precipitation_mm_15=0.0,
        bearing_deg=90.0,
    )
    assert score < 0.3

def test_stronger_tailwind_eventually_scores_worse():
    """The benefit of a tailwind peaks and then reverses."""
    scores = [
        score_of(
            wind_speed_km_h=float(speed), wind_direction_deg=270.0,
            gust_speed_km_h=float(speed) * 1.3, precipitation_mm_15=0.0,
            bearing_deg=90.0,
        )
        for speed in (20, 30, 45, 65)
    ]
    assert scores[1] > scores[0]
    assert scores[3] < scores[2] < scores[1]

def test_light_wind_free_of_strength_penalty():
    """Below the allowance, only direction matters."""
    lenient = ScoringParams(wind_strength_weight=0.0)
    snapshot = make_snapshot(15.0, 270.0, 20.0, 0.0, 90.0)
    assert math.isclose(
        score_segment(snapshot).score,
        score_segment(snapshot, lenient).score,
        abs_tol=1e-9,
    )

def test_crosswind_scores_mildly_negative():
    score = score_of(
        wind_speed_km_h=20.0,
        wind_direction_deg=0.0,
        gust_speed_km_h=25.0,
        precipitation_mm_15=0.0,
        bearing_deg=90.0,
    )
    assert -0.3 < score < 0.0

def test_rain_and_headwind_both_penalise():
    headwind_only = score_of(
        wind_speed_km_h=10.0, wind_direction_deg=90.0,
        gust_speed_km_h=14.0, precipitation_mm_15=0.0, bearing_deg=90.0,
    )
    headwind_rain = score_of(
        wind_speed_km_h=10.0, wind_direction_deg=90.0,
        gust_speed_km_h=14.0, precipitation_mm_15=1.0, bearing_deg=90.0,
    )
    assert headwind_rain < headwind_only

def test_score_always_within_bounds():
    for wind_dir in range(0, 360, 30):
        for speed in [0.0, 10.0, 25.0, 49.0, 80.0]:
            for gust in [0.0, 20.0, 60.0, 120.0]:
                for rain in [0.0, 1.0, 12.0]:
                    score = score_of(
                        wind_speed_km_h=speed,
                        wind_direction_deg=float(wind_dir),
                        gust_speed_km_h=gust,
                        precipitation_mm_15=rain,
                        bearing_deg=90.0,
                    )
                    assert -1.0 <= score <= 1.0


# ── Gusts ─────────────────────────────────────────────────────────

def test_normal_gust_factor_is_free():
    """Gusts within the usual ratio above the mean wind cost nothing."""
    assert _gust_score(24.0, 20.0, DEFAULT_PARAMS) == 0.0

def test_gust_below_wind_speed_is_free():
    assert _gust_score(5.0, 20.0, DEFAULT_PARAMS) == 0.0

def test_squally_wind_is_penalised():
    """Gusts far above the mean wind are the dangerous case, even when light."""
    assert _gust_score(30.0, 5.0, DEFAULT_PARAMS) < -0.5

def test_gust_penalty_is_monotonic():
    previous = 0.0
    for gust in range(0, 120, 5):
        current = _gust_score(float(gust), 20.0, DEFAULT_PARAMS)
        assert current <= previous + 1e-12
        previous = current

def test_gust_penalty_bounded():
    assert -1.0 <= _gust_score(500.0, 0.0, DEFAULT_PARAMS) <= 0.0

def test_gust_allowance_scales_with_wind():
    """The same gust delta is ordinary in strong wind but squally in light wind."""
    in_strong_wind = _gust_score(45.0, 30.0, DEFAULT_PARAMS)
    in_light_wind = _gust_score(20.0, 5.0, DEFAULT_PARAMS)
    assert in_light_wind < in_strong_wind - 0.4


# ── Rain ──────────────────────────────────────────────────────────

def test_no_rain_no_penalty():
    assert _rain_score(0.0, DEFAULT_PARAMS) == 0.0

def test_rain_penalty_is_monotonic():
    previous = 0.0
    for rain in range(0, 40):
        current = _rain_score(float(rain), DEFAULT_PARAMS)
        assert current <= previous + 1e-12
        previous = current

def test_rain_penalty_saturates():
    """Once soaked, more rain barely matters."""
    heavy = _rain_score(15.0, DEFAULT_PARAMS)
    torrential = _rain_score(30.0, DEFAULT_PARAMS)
    assert abs(torrential - heavy) < 0.01

def test_rain_penalty_bounded():
    assert -1.0 <= _rain_score(1000.0, DEFAULT_PARAMS) <= 0.0


# ── Continuity ────────────────────────────────────────────────────

def test_score_continuous_in_wind_direction():
    """No cliff anywhere on the compass, including the old category borders."""
    previous = None
    for tenth_deg in range(0, 3600):
        score = score_of(
            wind_speed_km_h=30.0,
            wind_direction_deg=tenth_deg / 10.0,
            gust_speed_km_h=40.0,
            precipitation_mm_15=0.2,
            bearing_deg=90.0,
        )
        if previous is not None:
            assert abs(score - previous) < 0.01
        previous = score

def test_score_continuous_in_wind_speed():
    previous = None
    for tenth in range(0, 1000):
        score = score_of(
            wind_speed_km_h=tenth / 10.0,
            wind_direction_deg=120.0,
            gust_speed_km_h=tenth / 10.0 + 8.0,
            precipitation_mm_15=0.0,
            bearing_deg=90.0,
        )
        if previous is not None:
            assert abs(score - previous) < 0.01
        previous = score

def test_score_continuous_in_gusts():
    """Crossing the old hard-block threshold must not snap the score."""
    previous = None
    for tenth in range(0, 1000):
        score = score_of(
            wind_speed_km_h=20.0,
            wind_direction_deg=270.0,
            gust_speed_km_h=tenth / 10.0,
            precipitation_mm_15=0.0,
            bearing_deg=90.0,
        )
        if previous is not None:
            assert abs(score - previous) < 0.01
        previous = score

def test_score_continuous_in_precipitation():
    previous = None
    for step in range(0, 1000):
        score = score_of(
            wind_speed_km_h=15.0,
            wind_direction_deg=270.0,
            gust_speed_km_h=20.0,
            precipitation_mm_15=step / 200.0,
            bearing_deg=90.0,
        )
        if previous is not None:
            assert abs(score - previous) < 0.01
        previous = score


# ── Safety flag ───────────────────────────────────────────────────

def test_calm_conditions_are_safe():
    result = score_segment(make_snapshot(10.0, 270.0, 15.0, 0.0, 90.0))
    assert result.unsafe is False

def test_storm_gusts_flagged_unsafe():
    result = score_segment(make_snapshot(30.0, 270.0, 60.0, 0.0, 90.0))
    assert result.unsafe is True

def test_torrential_rain_flagged_unsafe():
    result = score_segment(make_snapshot(10.0, 270.0, 15.0, 6.0, 90.0))
    assert result.unsafe is True

def test_squalls_flagged_unsafe():
    result = score_segment(make_snapshot(10.0, 270.0, 40.0, 0.0, 90.0))
    assert result.unsafe is True

def test_unsafe_conditions_still_score_informatively():
    """The safety veto must not collapse the score to a constant.

    A storm with a tailwind and a storm with a headwind used to be
    indistinguishable at -1.0; they should still be told apart.
    """
    tailwind_storm = score_segment(make_snapshot(30.0, 270.0, 60.0, 0.0, 90.0))
    headwind_storm = score_segment(make_snapshot(30.0, 90.0, 60.0, 0.0, 90.0))
    assert tailwind_storm.unsafe and headwind_storm.unsafe
    assert tailwind_storm.score > headwind_storm.score

def test_extreme_conditions_score_near_minimum():
    score = score_of(
        wind_speed_km_h=60.0,
        wind_direction_deg=90.0,
        gust_speed_km_h=95.0,
        precipitation_mm_15=8.0,
        bearing_deg=90.0,
    )
    assert score < -0.95


# ── Components ────────────────────────────────────────────────────

def test_components_reported_on_result():
    result = score_segment(make_snapshot(20.0, 270.0, 25.0, 0.5, 90.0))
    assert math.isclose(result.tailwind_km_h, 20.0, abs_tol=1e-9)
    assert math.isclose(result.crosswind_km_h, 0.0, abs_tol=1e-9)
    assert math.isclose(result.precipitation_mm_h, 2.0, abs_tol=1e-9)

def test_alignment_tailwind():
    assert score_segment(make_snapshot(20.0, 270.0, 25.0, 0.0, 90.0)).alignment == WindAlignment.TAILWIND

def test_alignment_headwind():
    assert score_segment(make_snapshot(20.0, 90.0, 25.0, 0.0, 90.0)).alignment == WindAlignment.HEADWIND

def test_alignment_crosswind():
    assert score_segment(make_snapshot(20.0, 0.0, 25.0, 0.0, 90.0)).alignment == WindAlignment.CROSSWIND


# ── Parameterisation ──────────────────────────────────────────────

def test_params_are_overridable():
    """Coefficients must be injectable so they can be fitted later."""
    snapshot = make_snapshot(20.0, 90.0, 25.0, 0.0, 90.0)
    lenient = ScoringParams(headwind_scale_km_h=200.0)
    assert score_segment(snapshot, lenient).score > score_segment(snapshot).score

def test_weights_are_applied():
    snapshot = make_snapshot(10.0, 270.0, 15.0, 2.0, 90.0)
    ignore_rain = ScoringParams(rain_weight=0.0)
    assert score_segment(snapshot, ignore_rain).score > score_segment(snapshot).score
