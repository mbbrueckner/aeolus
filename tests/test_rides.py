"""Tests for app/calibration/rides.py"""

import math
import numpy as np
import pytest

from app.calibration.rides import (
    RideSamples,
    acceleration,
    gradient,
    load_ride,
    pedalling_mask,
)


# ── load_ride ─────────────────────────────────────────────────────

def test_loads_plain_fit(fit_file):
    samples = load_ride(fit_file(n=300))
    assert samples is not None
    assert len(samples) == 300

def test_loads_gzipped_fit(fit_file):
    samples = load_ride(fit_file(n=300, compress=True))
    assert samples is not None
    assert len(samples) == 300

def test_gzipped_and_plain_agree(fit_file):
    plain = load_ride(fit_file(n=200))
    zipped = load_ride(fit_file(n=200, compress=True))
    assert np.allclose(plain.speed_m_s, zipped.speed_m_s)
    assert np.allclose(plain.latitude_deg, zipped.latitude_deg)

def test_missing_file_returns_none(tmp_path):
    assert load_ride(tmp_path / "nope.fit") is None

def test_garbage_file_returns_none(tmp_path):
    path = tmp_path / "broken.fit"
    path.write_bytes(b"this is not a FIT file")
    assert load_ride(path) is None

def test_positions_land_in_degrees(fit_file):
    """Semicircles must be converted, not passed through."""
    samples = load_ride(fit_file(n=100))
    assert 47.0 < samples.latitude_deg[0] < 49.0
    assert 11.0 < samples.longitude_deg[0] < 12.0

def test_absent_power_becomes_nan(fit_file):
    samples = load_ride(fit_file(n=100, with_power=False))
    assert np.all(np.isnan(samples.power_w))
    assert not samples.has("power_w")

def test_present_power_is_reported(fit_file):
    samples = load_ride(fit_file(n=100))
    assert samples.has("power_w")

def test_absent_position_becomes_nan(fit_file):
    samples = load_ride(fit_file(n=100, with_position=False))
    assert np.all(np.isnan(samples.latitude_deg))


# ── Metadata ──────────────────────────────────────────────────────

def test_duration_matches_recording(fit_file):
    samples = load_ride(fit_file(n=120, interval_s=1))
    assert math.isclose(samples.duration_s, 119.0)

def test_median_interval_detects_one_hz(fit_file):
    assert load_ride(fit_file(n=100, interval_s=1)).median_interval_s == 1.0

def test_median_interval_detects_smart_recording(fit_file):
    assert load_ride(fit_file(n=100, interval_s=4)).median_interval_s == 4.0


# ── gradient ──────────────────────────────────────────────────────

def test_flat_ride_has_no_gradient(fit_file):
    samples = load_ride(fit_file(n=600, climb_m=0.0))
    assert np.nanmax(np.abs(gradient(samples))) < 1e-3

def test_steady_climb_is_recovered(fit_file):
    """600 samples at ~8 m/s covering 240 m of climb is roughly 5 %."""
    samples = load_ride(fit_file(n=600, climb_m=240.0))
    slope = gradient(samples)
    expected = 240.0 / (samples.distance_m[-1] - samples.distance_m[0])

    assert math.isclose(float(np.nanmedian(slope)), expected, rel_tol=0.1)

def test_descent_is_negative(fit_file):
    samples = load_ride(fit_file(n=600, climb_m=-150.0))
    assert np.nanmedian(gradient(samples)) < 0.0

def test_gradient_is_clipped_to_plausible_slopes(fit_file):
    samples = load_ride(fit_file(n=600, climb_m=5000.0))
    assert np.nanmax(np.abs(gradient(samples))) <= 0.30

def test_gradient_survives_altimeter_noise(fit_file):
    """Smoothing must keep barometric jitter from swamping a real slope."""
    samples = load_ride(fit_file(n=900, climb_m=180.0))
    noise = np.random.default_rng(0).normal(0.0, 0.3, len(samples))
    noisy = RideSamples(
        timestamps=samples.timestamps,
        latitude_deg=samples.latitude_deg,
        longitude_deg=samples.longitude_deg,
        altitude_m=samples.altitude_m + noise,
        speed_m_s=samples.speed_m_s,
        power_w=samples.power_w,
        cadence_rpm=samples.cadence_rpm,
        temperature_c=samples.temperature_c,
        distance_m=samples.distance_m,
    )
    clean = float(np.nanmedian(gradient(samples)))
    rough = float(np.nanmedian(gradient(noisy)))

    assert math.isclose(rough, clean, abs_tol=0.005)

def test_gradient_without_altitude_is_nan(fit_file):
    samples = load_ride(fit_file(n=200, with_altitude=False))
    assert np.all(np.isnan(gradient(samples)))


# ── acceleration ──────────────────────────────────────────────────

def test_acceleration_is_small_on_steady_ride(fit_file):
    samples = load_ride(fit_file(n=600))
    assert np.nanmax(np.abs(acceleration(samples))) < 0.2

def test_acceleration_integrates_back_to_speed_change(fit_file):
    samples = load_ride(fit_file(n=600))
    accel = acceleration(samples)
    recovered = samples.speed_m_s[0] + np.nancumsum(accel)
    drift = abs(recovered[-1] - samples.speed_m_s[-1])

    assert drift < 0.5


# ── pedalling_mask ────────────────────────────────────────────────

def test_pedalling_mask_keeps_a_normal_ride(fit_file):
    samples = load_ride(fit_file(n=600))
    assert np.mean(pedalling_mask(samples)) > 0.9

def test_pedalling_mask_drops_coasting(fit_file):
    samples = load_ride(fit_file(n=600))
    samples.power_w[100:200] = 0.0
    assert not pedalling_mask(samples)[100:200].any()

def test_pedalling_mask_drops_standstill(fit_file):
    samples = load_ride(fit_file(n=600))
    samples.speed_m_s[300:400] = 0.0
    assert not pedalling_mask(samples)[300:400].any()

def test_pedalling_mask_drops_missing_position(fit_file):
    samples = load_ride(fit_file(n=400, with_position=False))
    assert not pedalling_mask(samples).any()

def test_pedalling_mask_without_power_is_empty(fit_file):
    samples = load_ride(fit_file(n=400, with_power=False))
    assert not pedalling_mask(samples).any()

def test_pedalling_mask_returns_bool_array(fit_file):
    mask = pedalling_mask(load_ride(fit_file(n=200)))
    assert mask.dtype == bool
