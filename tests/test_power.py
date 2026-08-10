"""Tests for app/calibration/power.py"""

import math
import numpy as np
import pytest

from app.calibration.power import (
    SEA_LEVEL_DENSITY_KG_M3,
    Aerodynamics,
    RiderParams,
    air_density_kg_m3,
    expected_power_w,
    fit_aerodynamics,
    solve_headwind_m_s,
)

RIDER = RiderParams(total_mass_kg=82.0)
AERO = Aerodynamics(cda_m2=0.32, crr=0.004)


def synthetic_ride(
    n: int = 2000,
    aero: Aerodynamics = AERO,
    headwind_m_s: np.ndarray | float = 0.0,
    seed: int = 0,
):
    """Generate a ride whose true coefficients are known.

    Args:
        n: Number of samples.
        aero: Coefficients the rider is riding with.
        headwind_m_s: Headwind per sample, or one value for all.
        seed: Seed for the random generator.

    Returns:
        Tuple of (power, speed, gradient, headwind, acceleration) arrays.
    """
    rng = np.random.default_rng(seed)
    speed = rng.uniform(4.0, 13.0, n)
    gradient = rng.uniform(-0.06, 0.06, n)
    accel = rng.uniform(-0.3, 0.3, n)
    wind = np.broadcast_to(np.asarray(headwind_m_s, dtype=float), speed.shape)

    power = np.array([
        expected_power_w(RIDER, aero, s, g, w, a)
        for s, g, w, a in zip(speed, gradient, wind, accel)
    ])
    return power, speed, gradient, wind, accel


# ── air_density_kg_m3 ─────────────────────────────────────────────

def test_density_at_standard_conditions():
    """ICAO standard sea level is 15 °C, 1013.25 hPa, 1.225 kg/m³."""
    assert math.isclose(air_density_kg_m3(15.0, 1013.25), 1.225, abs_tol=0.002)

def test_density_falls_with_altitude():
    """Thinner air at 2000 m, roughly 800 hPa."""
    assert air_density_kg_m3(5.0, 800.0) < air_density_kg_m3(5.0, 1013.25)

def test_density_falls_with_heat():
    assert air_density_kg_m3(35.0, 1013.25) < air_density_kg_m3(0.0, 1013.25)


# ── expected_power_w ──────────────────────────────────────────────

def test_power_at_typical_endurance_pace():
    """30 km/h on the flat in still air should land in a plausible range."""
    power = expected_power_w(RIDER, AERO, speed_m_s=30 / 3.6, gradient=0.0)
    assert 120.0 < power < 180.0

def test_climbing_costs_more_than_flat():
    flat = expected_power_w(RIDER, AERO, 5.0, 0.0)
    climb = expected_power_w(RIDER, AERO, 5.0, 0.06)
    assert climb > flat

def test_headwind_costs_more_than_still_air():
    still = expected_power_w(RIDER, AERO, 8.0, 0.0)
    into_wind = expected_power_w(RIDER, AERO, 8.0, 0.0, headwind_m_s=5.0)
    assert into_wind > still

def test_tailwind_costs_less_than_still_air():
    still = expected_power_w(RIDER, AERO, 8.0, 0.0)
    pushed = expected_power_w(RIDER, AERO, 8.0, 0.0, headwind_m_s=-5.0)
    assert pushed < still

def test_drag_reverses_when_tailwind_exceeds_speed():
    """Being blown along should help, not hurt, however strong the wind."""
    mild = expected_power_w(RIDER, AERO, 5.0, 0.0, headwind_m_s=-6.0)
    strong = expected_power_w(RIDER, AERO, 5.0, 0.0, headwind_m_s=-12.0)
    assert strong < mild

def test_power_scales_with_air_density():
    thin = expected_power_w(RIDER, AERO, 10.0, 0.0, air_density=0.9)
    thick = expected_power_w(RIDER, AERO, 10.0, 0.0, air_density=1.3)
    assert thick > thin

def test_descending_can_require_negative_power():
    """A steep enough descent needs braking, not pedalling."""
    assert expected_power_w(RIDER, AERO, 8.0, gradient=-0.10) < 0.0


# ── solve_headwind_m_s ────────────────────────────────────────────

@pytest.mark.parametrize("headwind", [-8.0, -3.0, 0.0, 2.5, 7.0, 14.0])
def test_headwind_round_trips(headwind):
    """Predicting power then inverting it must return the original wind."""
    power = expected_power_w(RIDER, AERO, 8.0, 0.02, headwind, 0.1)
    recovered = solve_headwind_m_s(power, RIDER, AERO, 8.0, 0.02, 0.1)
    assert math.isclose(recovered, headwind, abs_tol=1e-6)

@pytest.mark.parametrize("gradient", [-0.08, 0.0, 0.05, 0.12])
def test_headwind_round_trips_on_any_gradient(gradient):
    power = expected_power_w(RIDER, AERO, 6.0, gradient, 4.0)
    recovered = solve_headwind_m_s(power, RIDER, AERO, 6.0, gradient)
    assert math.isclose(recovered, 4.0, abs_tol=1e-6)

def test_round_trip_respects_air_density():
    power = expected_power_w(RIDER, AERO, 9.0, 0.0, 3.0, air_density=1.05)
    recovered = solve_headwind_m_s(power, RIDER, AERO, 9.0, 0.0, air_density=1.05)
    assert math.isclose(recovered, 3.0, abs_tol=1e-6)

def test_standstill_yields_no_answer():
    """Below walking pace the drag term carries no information."""
    assert math.isnan(solve_headwind_m_s(100.0, RIDER, AERO, 0.2, 0.0))

def test_zero_cda_is_rejected():
    with pytest.raises(ValueError):
        solve_headwind_m_s(100.0, RIDER, Aerodynamics(cda_m2=0.0, crr=0.004), 8.0, 0.0)


# ── fit_aerodynamics ──────────────────────────────────────────────

def test_fit_recovers_coefficients_in_still_air():
    power, speed, gradient, _, accel = synthetic_ride()
    fitted = fit_aerodynamics(RIDER, power, speed, gradient, acceleration_m_s2=accel)

    assert math.isclose(fitted.cda_m2, AERO.cda_m2, rel_tol=1e-6)
    assert math.isclose(fitted.crr, AERO.crr, rel_tol=1e-6)

def test_fit_recovers_coefficients_with_known_wind():
    power, speed, gradient, wind, accel = synthetic_ride(headwind_m_s=4.5)
    fitted = fit_aerodynamics(RIDER, power, speed, gradient, wind, accel)

    assert math.isclose(fitted.cda_m2, AERO.cda_m2, rel_tol=1e-6)
    assert math.isclose(fitted.crr, AERO.crr, rel_tol=1e-6)

def test_fit_recovers_coefficients_under_varying_wind():
    rng = np.random.default_rng(7)
    wind = rng.uniform(-6.0, 6.0, 2000)
    power, speed, gradient, wind, accel = synthetic_ride(headwind_m_s=wind, seed=3)
    fitted = fit_aerodynamics(RIDER, power, speed, gradient, wind, accel)

    assert math.isclose(fitted.cda_m2, AERO.cda_m2, rel_tol=1e-6)
    assert math.isclose(fitted.crr, AERO.crr, rel_tol=1e-6)

def test_fit_tolerates_power_meter_noise():
    """Real readings wobble; the fit must not chase the noise."""
    power, speed, gradient, _, accel = synthetic_ride(n=5000)
    noisy = power + np.random.default_rng(1).normal(0.0, 8.0, power.shape)
    fitted = fit_aerodynamics(RIDER, noisy, speed, gradient, acceleration_m_s2=accel)

    assert math.isclose(fitted.cda_m2, AERO.cda_m2, rel_tol=0.05)
    assert math.isclose(fitted.crr, AERO.crr, rel_tol=0.20)

def test_fit_recovers_a_different_rider():
    """Nothing may be baked in around one set of coefficients."""
    aero = Aerodynamics(cda_m2=0.24, crr=0.0065)
    power, speed, gradient, _, accel = synthetic_ride(aero=aero, seed=5)
    fitted = fit_aerodynamics(RIDER, power, speed, gradient, acceleration_m_s2=accel)

    assert math.isclose(fitted.cda_m2, aero.cda_m2, rel_tol=1e-6)
    assert math.isclose(fitted.crr, aero.crr, rel_tol=1e-6)

def test_fit_accepts_per_sample_air_density():
    rng = np.random.default_rng(11)
    density = rng.uniform(1.05, 1.25, 2000)
    speed = rng.uniform(4.0, 13.0, 2000)
    gradient = rng.uniform(-0.05, 0.05, 2000)
    power = np.array([
        expected_power_w(RIDER, AERO, s, g, air_density=d)
        for s, g, d in zip(speed, gradient, density)
    ])
    fitted = fit_aerodynamics(RIDER, power, speed, gradient, air_density=density)

    assert math.isclose(fitted.cda_m2, AERO.cda_m2, rel_tol=1e-6)
    assert math.isclose(fitted.crr, AERO.crr, rel_tol=1e-6)

def test_fit_drops_standstill_samples():
    """Stops must not drag the fit, and must not make it fail either."""
    power, speed, gradient, _, accel = synthetic_ride()
    speed[:200] = 0.0
    power[:200] = 0.0
    accel[:200] = 0.0
    fitted = fit_aerodynamics(RIDER, power, speed, gradient, acceleration_m_s2=accel)

    assert math.isclose(fitted.cda_m2, AERO.cda_m2, rel_tol=1e-6)

def test_fit_needs_enough_samples():
    with pytest.raises(ValueError):
        fit_aerodynamics(RIDER, np.array([150.0]), np.array([0.1]), np.array([0.0]))


# ── End to end ────────────────────────────────────────────────────

def test_fitted_coefficients_recover_the_wind():
    """The whole point: fit on a calm ride, then measure wind on a windy one."""
    calm_power, calm_speed, calm_gradient, _, calm_accel = synthetic_ride(seed=2)
    fitted = fit_aerodynamics(
        RIDER, calm_power, calm_speed, calm_gradient, acceleration_m_s2=calm_accel
    )

    true_wind = 5.5
    power = expected_power_w(RIDER, AERO, 7.5, 0.01, true_wind)
    recovered = solve_headwind_m_s(power, RIDER, fitted, 7.5, 0.01)

    assert math.isclose(recovered, true_wind, abs_tol=0.05)


# ── fit_aerodynamics with a fixed Crr ─────────────────────────────

def test_fixed_crr_is_returned_unchanged():
    power, speed, gradient, _, accel = synthetic_ride()
    fitted = fit_aerodynamics(RIDER, power, speed, gradient,
                              acceleration_m_s2=accel, fixed_crr=0.004)
    assert fitted.crr == 0.004

def test_fixed_crr_recovers_cda_when_crr_is_right():
    power, speed, gradient, _, accel = synthetic_ride()
    fitted = fit_aerodynamics(RIDER, power, speed, gradient,
                              acceleration_m_s2=accel, fixed_crr=AERO.crr)
    assert math.isclose(fitted.cda_m2, AERO.cda_m2, rel_tol=1e-6)

def test_wrong_fixed_crr_biases_cda():
    """Holding Crr too high must push the drag term down, not silently pass."""
    power, speed, gradient, _, accel = synthetic_ride()
    fitted = fit_aerodynamics(RIDER, power, speed, gradient,
                              acceleration_m_s2=accel, fixed_crr=AERO.crr * 3)
    assert fitted.cda_m2 < AERO.cda_m2

def test_fixed_crr_detects_a_lower_drag_ride():
    """Drafting shows up as reduced CdA, which is how group rides are spotted."""
    drafted = Aerodynamics(cda_m2=AERO.cda_m2 * 0.7, crr=AERO.crr)
    power, speed, gradient, _, accel = synthetic_ride(aero=drafted, seed=9)
    fitted = fit_aerodynamics(RIDER, power, speed, gradient,
                              acceleration_m_s2=accel, fixed_crr=AERO.crr)
    assert math.isclose(fitted.cda_m2, drafted.cda_m2, rel_tol=1e-6)

def test_fixed_crr_is_stable_on_a_short_steady_ride():
    """The case where fitting both coefficients goes degenerate."""
    rng = np.random.default_rng(4)
    speed = rng.uniform(7.8, 8.2, 300)
    gradient = rng.uniform(-0.002, 0.002, 300)
    power = np.array([expected_power_w(RIDER, AERO, s, g) for s, g in zip(speed, gradient)])

    loose = fit_aerodynamics(RIDER, power, speed, gradient)
    tight = fit_aerodynamics(RIDER, power, speed, gradient, fixed_crr=AERO.crr)

    assert math.isclose(tight.cda_m2, AERO.cda_m2, rel_tol=0.02)
    assert abs(tight.cda_m2 - AERO.cda_m2) < abs(loose.cda_m2 - AERO.cda_m2)
