"""Route scoring based on weather conditions.

Each cluster is scored by decomposing the wind into a tail/head component and a
crosswind component, then subtracting penalties for gustiness and rain.

The score is continuous in every input: a small change in wind, gusts or rain
can only cause a small change in score. Penalties saturate through ``tanh``
instead of tripping over thresholds, which keeps the function differentiable
and therefore fittable to recorded rides later on.

Conditions that make a ride inadvisable are reported separately via
``SegmentScore.unsafe`` rather than by forcing the score to its minimum, so a
safety veto no longer destroys the information about how the ride would
otherwise have been.

Every tunable number lives in :class:`ScoringParams`. The defaults are informed
guesses, not calibrated values.
"""

__author__ = "mbbrueckner"
__version__ = "2.0.0"

import math
from dataclasses import dataclass
from enum import Enum

from app.models import ClusterWeatherSnapshot


class WindAlignment(Enum):
    """Dominant wind direction relative to travel, for display purposes."""

    HEADWIND = "headwind"
    CROSSWIND = "crosswind"
    TAILWIND = "tailwind"


@dataclass(frozen=True)
class ScoringParams:
    """Tunable coefficients of the scoring model.

    The ``*_scale_*`` values are the input at which the corresponding penalty
    reaches ``tanh(1) ≈ 0.76`` of its maximum, so they set both the slope near
    zero and the point of diminishing returns.

    Attributes:
        headwind_scale_km_h: Headwind component at which the wind term nears its
            minimum. Smaller than the tailwind scale because a headwind costs
            more than the same tailwind gives back.
        tailwind_scale_km_h: Tailwind component at which the wind term nears its
            maximum.
        crosswind_scale_km_h: Crosswind component at which its penalty saturates.
        crosswind_weight: How much a saturated crosswind penalty counts against
            the wind term.
        wind_strength_free_km_h: Wind speed below which direction is the only
            thing that matters.
        wind_strength_scale_km_h: Wind speed above that allowance at which the
            strength penalty saturates.
        wind_strength_weight: How much strong wind counts against the wind term
            regardless of direction. Keeps a storm from scoring well just
            because it happens to blow from behind.
        gust_factor_free: Gust-to-wind ratio treated as normal and unpenalised.
        gust_delta_free_km_h: Additional gust allowance on top of that ratio,
            which keeps light-wind conditions from being penalised for the
            proportionally large gust factors they naturally show.
        gust_excess_scale_km_h: Gust speed above the free allowance at which the
            gustiness penalty saturates.
        rain_scale_mm_h: Rain rate at which the precipitation penalty saturates.
        wind_weight: Weight of the wind term in the total score.
        gust_weight: Weight of the gust penalty in the total score.
        rain_weight: Weight of the rain penalty in the total score.
        unsafe_wind_km_h: Sustained wind above which a ride is flagged unsafe.
        unsafe_gust_km_h: Gust speed above which a ride is flagged unsafe.
        unsafe_gust_delta_km_h: Gust-minus-wind above which the wind is
            considered too squally to handle.
        unsafe_precipitation_mm_h: Rain rate above which a ride is flagged unsafe.
    """

    headwind_scale_km_h: float = 30.0
    tailwind_scale_km_h: float = 42.0
    crosswind_scale_km_h: float = 45.0
    crosswind_weight: float = 0.35
    wind_strength_free_km_h: float = 28.0
    wind_strength_scale_km_h: float = 22.0
    wind_strength_weight: float = 0.85

    gust_factor_free: float = 1.3
    gust_delta_free_km_h: float = 5.0
    gust_excess_scale_km_h: float = 14.0

    rain_scale_mm_h: float = 3.0

    wind_weight: float = 1.0
    gust_weight: float = 0.7
    rain_weight: float = 0.6

    unsafe_wind_km_h: float = 50.0
    unsafe_gust_km_h: float = 55.0
    unsafe_gust_delta_km_h: float = 25.0
    unsafe_precipitation_mm_h: float = 20.0


DEFAULT_PARAMS = ScoringParams()


@dataclass(frozen=True)
class SegmentScore:
    """Score of a single cluster together with its constituent terms.

    Attributes:
        score: Combined score from -1.0 (bad) to +1.0 (ideal).
        wind: Wind term from -1.0 to +1.0, before weighting.
        gust: Gust penalty from -1.0 to 0.0, before weighting.
        rain: Precipitation penalty from -1.0 to 0.0, before weighting.
        unsafe: Whether conditions exceed a safety threshold. Independent of
            the score, which stays informative even when this is set.
        tailwind_km_h: Wind component along the direction of travel; positive
            is a tailwind, negative a headwind.
        crosswind_km_h: Wind component perpendicular to travel, always positive.
        precipitation_mm_h: Rain rate the score was computed from.
    """

    score: float
    wind: float
    gust: float
    rain: float
    unsafe: bool
    tailwind_km_h: float
    crosswind_km_h: float
    precipitation_mm_h: float

    @property
    def alignment(self) -> WindAlignment:
        """Dominant wind direction relative to travel."""
        if abs(self.tailwind_km_h) < self.crosswind_km_h:
            return WindAlignment.CROSSWIND
        return WindAlignment.TAILWIND if self.tailwind_km_h > 0.0 else WindAlignment.HEADWIND


def score_segment(
    weather_snapshot: ClusterWeatherSnapshot,
    params: ScoringParams = DEFAULT_PARAMS,
) -> SegmentScore:
    """Score a route segment based on its weather conditions.

    Args:
        weather_snapshot: Weather conditions for the segment.
        params: Coefficients of the scoring model.

    Returns:
        The combined score along with the terms it was built from.
    """
    wind_speed_km_h = weather_snapshot.wind_speed_km_h
    gust_speed_km_h = weather_snapshot.wind_gusts_km_h
    precipitation_mm_h = _mm_15_to_mm_h(weather_snapshot.precipitation_mm_h)

    tailwind_km_h, crosswind_km_h = _wind_components(
        wind_speed_km_h,
        weather_snapshot.wind_direction_deg,
        weather_snapshot.cluster.mean_bearing,
    )

    wind = _wind_score(tailwind_km_h, crosswind_km_h, params)
    gust = _gust_score(gust_speed_km_h, wind_speed_km_h, params)
    rain = _rain_score(precipitation_mm_h, params)

    score = (
        wind * params.wind_weight
        + gust * params.gust_weight
        + rain * params.rain_weight
    )

    return SegmentScore(
        score=_clamp(score),
        wind=wind,
        gust=gust,
        rain=rain,
        unsafe=_is_unsafe(wind_speed_km_h, gust_speed_km_h, precipitation_mm_h, params),
        tailwind_km_h=tailwind_km_h,
        crosswind_km_h=crosswind_km_h,
        precipitation_mm_h=precipitation_mm_h,
    )


def _wind_components(
    wind_speed_km_h: float,
    wind_direction_deg: float,
    bearing_deg: float,
) -> tuple[float, float]:
    """Split the wind vector into along-track and across-track components.

    Args:
        wind_speed_km_h: Wind speed in km/h.
        wind_direction_deg: Meteorological wind origin direction in degrees.
        bearing_deg: Direction of travel in degrees.

    Returns:
        Tuple of (tailwind, crosswind) in km/h. Tailwind is signed, positive
        when the wind pushes along the direction of travel; crosswind is the
        absolute perpendicular component.
    """
    bx, by = _deg_to_vector(bearing_deg)
    wx, wy = _deg_to_vector(_invert_wind_direction(wind_direction_deg))

    tailwind = wind_speed_km_h * (bx * wx + by * wy)
    crosswind = wind_speed_km_h * abs(bx * wy - by * wx)
    return tailwind, crosswind


def _wind_score(tailwind_km_h: float, crosswind_km_h: float, params: ScoringParams) -> float:
    """Score the wind from its along- and across-track components.

    Args:
        tailwind_km_h: Signed along-track component in km/h.
        crosswind_km_h: Absolute across-track component in km/h.
        params: Coefficients of the scoring model.

    Returns:
        Wind term from -1.0 to +1.0.
    """
    scale = params.tailwind_scale_km_h if tailwind_km_h >= 0.0 else params.headwind_scale_km_h
    along = math.tanh(tailwind_km_h / scale)
    across = math.tanh(crosswind_km_h / params.crosswind_scale_km_h)

    speed = math.hypot(tailwind_km_h, crosswind_km_h)
    strength_excess = max(0.0, speed - params.wind_strength_free_km_h)
    strength = math.tanh(strength_excess / params.wind_strength_scale_km_h)

    return _clamp(
        along
        - across * params.crosswind_weight
        - strength * params.wind_strength_weight
    )


def _gust_score(gust_speed_km_h: float, wind_speed_km_h: float, params: ScoringParams) -> float:
    """Penalise gusts that exceed what the sustained wind already implies.

    Args:
        gust_speed_km_h: Gust speed in km/h.
        wind_speed_km_h: Sustained wind speed in km/h.
        params: Coefficients of the scoring model.

    Returns:
        Gust penalty from -1.0 to 0.0.
    """
    expected = wind_speed_km_h * params.gust_factor_free + params.gust_delta_free_km_h
    excess = max(0.0, gust_speed_km_h - expected)

    return -math.tanh(excess / params.gust_excess_scale_km_h)


def _rain_score(precipitation_mm_h: float, params: ScoringParams) -> float:
    """Penalise precipitation, with diminishing returns once already soaked.

    Args:
        precipitation_mm_h: Rain rate in mm/h.
        params: Coefficients of the scoring model.

    Returns:
        Precipitation penalty from -1.0 to 0.0.
    """
    return -math.tanh(max(0.0, precipitation_mm_h) / params.rain_scale_mm_h)


def _is_unsafe(
    wind_speed_km_h: float,
    gust_speed_km_h: float,
    precipitation_mm_h: float,
    params: ScoringParams,
) -> bool:
    """Check whether conditions warrant advising against the ride.

    Args:
        wind_speed_km_h: Sustained wind speed in km/h.
        gust_speed_km_h: Gust speed in km/h.
        precipitation_mm_h: Rain rate in mm/h.
        params: Coefficients of the scoring model.

    Returns:
        True if any safety threshold is exceeded.
    """
    return (
        wind_speed_km_h > params.unsafe_wind_km_h
        or gust_speed_km_h > params.unsafe_gust_km_h
        or gust_speed_km_h - wind_speed_km_h > params.unsafe_gust_delta_km_h
        or precipitation_mm_h > params.unsafe_precipitation_mm_h
    )


def _clamp(value: float) -> float:
    """Clamp a value to the -1.0 to +1.0 score range.

    Args:
        value: Value to clamp.

    Returns:
        The value limited to -1.0 to +1.0.
    """
    return max(-1.0, min(1.0, value))


def _mm_15_to_mm_h(mm_15: float) -> float:
    """Convert precipitation from mm per 15 minutes to mm per hour.

    Args:
        mm_15: Precipitation in mm over 15 minutes.

    Returns:
        Precipitation in mm/h.
    """
    return mm_15 * 4.0


def _deg_to_vector(deg: float) -> tuple[float, float]:
    """Convert a bearing in degrees to a unit vector.

    Args:
        deg: Bearing in degrees, clockwise from north.

    Returns:
        Unit vector as (x, y) tuple.
    """
    rad = math.radians(deg)
    return math.sin(rad), math.cos(rad)


def _invert_wind_direction(deg: float) -> float:
    """Convert a meteorological wind direction to the direction the wind is blowing towards.

    Args:
        deg: Wind origin direction in degrees (where the wind comes from).

    Returns:
        Wind flow direction in degrees (where the wind is going).
    """
    return (deg + 180) % 360
