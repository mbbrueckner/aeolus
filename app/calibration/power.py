"""Cycling power balance, used to recover experienced wind from recorded rides.

At any instant the power reaching the wheel is spent on rolling resistance,
climbing, pushing air aside, and changing kinetic energy:

    P = v · (Crr·m·g·cosθ + m·g·sinθ + ½·ρ·CdA·w·|w| + m·a)

where ``v`` is ground speed and ``w = v + headwind`` is the speed of the air
flowing past the rider. Everything except ``CdA``, ``Crr`` and the headwind is
either measured by the head unit or derived from the weather.

That gives two things this project needs:

- On rides with little wind, ``w ≈ v``, so the equation is linear in ``Crr``
  and ``CdA`` and both fall out of an ordinary least-squares fit.
- With those known, the same equation can be solved for ``w`` on any ride,
  which turns a power meter into a wind sensor and makes it possible to check
  the forecast against what the rider actually felt.
"""

__author__ = "mbbrueckner"
__version__ = "1.0.0"

import math
from dataclasses import dataclass

import numpy as np

GRAVITY_M_S2 = 9.80665
DRY_AIR_GAS_CONSTANT = 287.058
SEA_LEVEL_DENSITY_KG_M3 = 1.225


@dataclass(frozen=True)
class RiderParams:
    """Properties of the rider that the power model needs.

    Attributes:
        total_mass_kg: Rider plus bike, kit and bottles.
        drivetrain_efficiency: Fraction of measured power that reaches the
            wheel. Applies to crank- and pedal-based meters, which measure
            upstream of the chain; use 1.0 for a hub-based meter.
    """

    total_mass_kg: float
    drivetrain_efficiency: float = 0.976


@dataclass(frozen=True)
class Aerodynamics:
    """Resistance coefficients of a rider on a particular bike and position.

    Attributes:
        cda_m2: Effective frontal area, drag coefficient times area.
        crr: Coefficient of rolling resistance.
    """

    cda_m2: float
    crr: float


def air_density_kg_m3(temperature_c: float, pressure_hpa: float) -> float:
    """Compute air density from temperature and pressure.

    Uses the dry-air ideal gas law. Ignoring humidity overstates density by
    well under a percent at cycling temperatures.

    Args:
        temperature_c: Air temperature in degrees Celsius.
        pressure_hpa: Air pressure at the rider's altitude in hectopascals.

    Returns:
        Air density in kg/m³.
    """
    return (pressure_hpa * 100.0) / (DRY_AIR_GAS_CONSTANT * (temperature_c + 273.15))


def expected_power_w(
    rider: RiderParams,
    aero: Aerodynamics,
    speed_m_s: float,
    gradient: float,
    headwind_m_s: float = 0.0,
    acceleration_m_s2: float = 0.0,
    air_density: float = SEA_LEVEL_DENSITY_KG_M3,
) -> float:
    """Predict the power a rider must produce under given conditions.

    Args:
        rider: Rider mass and drivetrain efficiency.
        aero: Resistance coefficients.
        speed_m_s: Ground speed in m/s.
        gradient: Slope as rise over run, positive uphill.
        headwind_m_s: Air speed along the direction of travel; positive is a
            headwind, negative a tailwind.
        acceleration_m_s2: Rate of change of ground speed.
        air_density: Air density in kg/m³.

    Returns:
        Power in watts as a power meter would read it, that is including
        drivetrain losses.
    """
    sin_theta, cos_theta = _slope_components(gradient)
    air_speed = speed_m_s + headwind_m_s

    rolling = aero.crr * rider.total_mass_kg * GRAVITY_M_S2 * cos_theta
    climbing = rider.total_mass_kg * GRAVITY_M_S2 * sin_theta
    drag = 0.5 * air_density * aero.cda_m2 * air_speed * abs(air_speed)
    inertia = rider.total_mass_kg * acceleration_m_s2

    wheel_power = speed_m_s * (rolling + climbing + drag + inertia)
    return wheel_power / rider.drivetrain_efficiency


def solve_headwind_m_s(
    measured_power_w: float,
    rider: RiderParams,
    aero: Aerodynamics,
    speed_m_s: float,
    gradient: float,
    acceleration_m_s2: float = 0.0,
    air_density: float = SEA_LEVEL_DENSITY_KG_M3,
) -> float:
    """Recover the headwind the rider was working against.

    Inverts :func:`expected_power_w` for the wind term. Meaningful only while
    pedalling: when coasting, measured power is zero and says nothing about
    the air, so those samples must be filtered out beforehand.

    Args:
        measured_power_w: Power meter reading in watts.
        rider: Rider mass and drivetrain efficiency.
        aero: Resistance coefficients.
        speed_m_s: Ground speed in m/s.
        gradient: Slope as rise over run, positive uphill.
        acceleration_m_s2: Rate of change of ground speed.
        air_density: Air density in kg/m³.

    Returns:
        Headwind in m/s, positive against the rider. Returns NaN if the rider
        is too slow for the drag term to carry any information.

    Raises:
        ValueError: If CdA is not positive.
    """
    if aero.cda_m2 <= 0.0:
        raise ValueError("cda_m2 must be positive to solve for wind")
    if speed_m_s <= 0.5:
        return math.nan

    sin_theta, cos_theta = _slope_components(gradient)

    wheel_power = measured_power_w * rider.drivetrain_efficiency
    rolling = aero.crr * rider.total_mass_kg * GRAVITY_M_S2 * cos_theta
    climbing = rider.total_mass_kg * GRAVITY_M_S2 * sin_theta
    inertia = rider.total_mass_kg * acceleration_m_s2

    drag_force = wheel_power / speed_m_s - rolling - climbing - inertia
    air_speed_squared = 2.0 * drag_force / (air_density * aero.cda_m2)

    air_speed = math.copysign(math.sqrt(abs(air_speed_squared)), air_speed_squared)
    return air_speed - speed_m_s


def fit_aerodynamics(
    rider: RiderParams,
    measured_power_w: np.ndarray,
    speed_m_s: np.ndarray,
    gradient: np.ndarray,
    headwind_m_s: np.ndarray | None = None,
    acceleration_m_s2: np.ndarray | None = None,
    air_density: np.ndarray | float = SEA_LEVEL_DENSITY_KG_M3,
) -> Aerodynamics:
    """Fit CdA and Crr to recorded samples by least squares.

    Dividing the power balance by ground speed makes it linear in the two
    coefficients, so no iterative solver is needed. Pass ``headwind_m_s`` when
    it is known; leaving it out assumes still air, which is only safe on rides
    picked for being calm.

    Args:
        rider: Rider mass and drivetrain efficiency.
        measured_power_w: Power meter readings in watts.
        speed_m_s: Ground speeds in m/s. Samples at or below 0.5 m/s are
            dropped, since the drag term vanishes with them.
        gradient: Slopes as rise over run, positive uphill.
        headwind_m_s: Known headwinds in m/s, or None for still air.
        acceleration_m_s2: Rates of change of ground speed, or None for steady
            state.
        air_density: Air density in kg/m³, per sample or as one value.

    Returns:
        The fitted coefficients.

    Raises:
        ValueError: If fewer than two usable samples remain.
    """
    speed = np.asarray(speed_m_s, dtype=float)
    power = np.asarray(measured_power_w, dtype=float)
    slope = np.asarray(gradient, dtype=float)
    wind = np.zeros_like(speed) if headwind_m_s is None else np.asarray(headwind_m_s, dtype=float)
    accel = np.zeros_like(speed) if acceleration_m_s2 is None else np.asarray(acceleration_m_s2, dtype=float)
    density = np.broadcast_to(np.asarray(air_density, dtype=float), speed.shape)

    usable = speed > 0.5
    if np.count_nonzero(usable) < 2:
        raise ValueError("need at least two samples above 0.5 m/s to fit")

    speed, power, slope = speed[usable], power[usable], slope[usable]
    wind, accel, density = wind[usable], accel[usable], density[usable]

    sin_theta, cos_theta = _slope_components(slope)
    air_speed = speed + wind
    weight = rider.total_mass_kg * GRAVITY_M_S2

    design = np.column_stack([
        weight * cos_theta,
        0.5 * density * air_speed * np.abs(air_speed),
    ])
    target = (
        power * rider.drivetrain_efficiency / speed
        - weight * sin_theta
        - rider.total_mass_kg * accel
    )

    (crr, cda), *_ = np.linalg.lstsq(design, target, rcond=None)
    return Aerodynamics(cda_m2=float(cda), crr=float(crr))


def _slope_components(gradient):
    """Convert a rise-over-run gradient to its sine and cosine.

    Args:
        gradient: Slope as rise over run, scalar or array.

    Returns:
        Tuple of (sin, cos) of the slope angle.
    """
    hypotenuse = np.sqrt(1.0 + np.asarray(gradient, dtype=float) ** 2)
    return gradient / hypotenuse, 1.0 / hypotenuse
