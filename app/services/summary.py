"""Turning a scored route into statements a rider can check afterwards.

The calibration work showed that forecast wind predicts *where* along a route
the wind will hit, but not reliably how strong it will feel in absolute terms.
So the summary deals in distances and directions, which are supported, and
avoids claiming a felt wind speed, which is not.

Every figure here is something the rider can confirm or refute after the ride,
which is what makes it useful feedback rather than an opaque verdict.
"""

__author__ = "mbbrueckner"
__version__ = "1.0.0"

from dataclasses import dataclass
from datetime import datetime

from app.models import ClusterWeatherSnapshot
from app.services.route_scorer import SegmentScore, WindAlignment

NOTABLE_WIND_KM_H = 12.0
NOTABLE_RAIN_MM_H = 0.4
MODERATE_RAIN_MM_H = 2.5
HEAVY_RAIN_MM_H = 10.0


def rain_tier(precipitation_mm_h: float) -> str | None:
    """Classify a rain rate into a band a rider can picture.

    Args:
        precipitation_mm_h: Rain rate in mm/h.

    Returns:
        One of "light", "moderate" or "heavy", or None when it is dry enough
        not to be worth mentioning.
    """
    if precipitation_mm_h >= HEAVY_RAIN_MM_H:
        return "heavy"
    if precipitation_mm_h >= MODERATE_RAIN_MM_H:
        return "moderate"
    if precipitation_mm_h >= NOTABLE_RAIN_MM_H:
        return "light"
    return None


@dataclass(frozen=True)
class RouteSummary:
    """Distance-based facts about a scored route.

    Attributes:
        total_distance_m: Length of the whole route.
        headwind_distance_m: Distance ridden into a notable headwind.
        tailwind_distance_m: Distance ridden with a notable tailwind.
        crosswind_distance_m: Distance with a notable crosswind.
        rain_distance_m: Distance with notable precipitation, of any intensity.
        light_rain_distance_m: Distance with drizzle.
        moderate_rain_distance_m: Distance with steady rain.
        heavy_rain_distance_m: Distance with downpours.
        rain_start_m: Distance from the start at which rain first appears, or
            None if the route stays dry.
        rain_start_time: When the rider reaches that point, or None.
        max_precipitation_mm_h: Heaviest rain forecast anywhere on the route.
        unsafe_distance_m: Distance where conditions trip a safety threshold.
        mean_wind_km_h: Distance-weighted mean forecast wind speed.
        max_gust_km_h: Strongest gust forecast anywhere on the route.
        score: Distance-weighted overall score, from -1.0 to +1.0.
    """

    total_distance_m: float
    headwind_distance_m: float
    tailwind_distance_m: float
    crosswind_distance_m: float
    rain_distance_m: float
    light_rain_distance_m: float
    moderate_rain_distance_m: float
    heavy_rain_distance_m: float
    rain_start_m: float | None
    rain_start_time: datetime | None
    max_precipitation_mm_h: float
    unsafe_distance_m: float
    mean_wind_km_h: float
    max_gust_km_h: float
    score: float

    @property
    def headwind_share(self) -> float:
        """Fraction of the route ridden into a notable headwind."""
        return self._share(self.headwind_distance_m)

    @property
    def tailwind_share(self) -> float:
        """Fraction of the route ridden with a notable tailwind."""
        return self._share(self.tailwind_distance_m)

    @property
    def rain_share(self) -> float:
        """Fraction of the route with notable precipitation."""
        return self._share(self.rain_distance_m)

    def _share(self, distance_m: float) -> float:
        """Express a distance as a fraction of the route.

        Args:
            distance_m: Distance to express.

        Returns:
            Fraction from 0.0 to 1.0, or 0.0 for an empty route.
        """
        return distance_m / self.total_distance_m if self.total_distance_m else 0.0


def summarise(
    snapshots: list[ClusterWeatherSnapshot],
    scores: list[SegmentScore],
    notable_wind_km_h: float = NOTABLE_WIND_KM_H,
    notable_rain_mm_h: float = NOTABLE_RAIN_MM_H,
) -> RouteSummary:
    """Aggregate scored clusters into checkable route-level facts.

    Args:
        snapshots: Weather per cluster, in route order.
        scores: Scores per cluster, matching the snapshots.
        notable_wind_km_h: Wind component above which a stretch counts as
            head-, tail- or crosswind rather than as calm.
        notable_rain_mm_h: Rain rate above which a stretch counts as wet.

    Returns:
        The summary. All distances are zero for an empty route.
    """
    if not snapshots:
        return RouteSummary(
            total_distance_m=0.0,
            headwind_distance_m=0.0,
            tailwind_distance_m=0.0,
            crosswind_distance_m=0.0,
            rain_distance_m=0.0,
            light_rain_distance_m=0.0,
            moderate_rain_distance_m=0.0,
            heavy_rain_distance_m=0.0,
            rain_start_m=None,
            rain_start_time=None,
            max_precipitation_mm_h=0.0,
            unsafe_distance_m=0.0,
            mean_wind_km_h=0.0,
            max_gust_km_h=0.0,
            score=0.0,
        )

    total = sum(s.cluster.total_distance_m for s in snapshots)
    headwind = tailwind = crosswind = rain = unsafe = 0.0
    by_tier = {"light": 0.0, "moderate": 0.0, "heavy": 0.0}
    weighted_wind = weighted_score = 0.0
    max_gust = max_rain = 0.0
    covered = 0.0
    rain_start_m: float | None = None
    rain_start_time = None

    for snapshot, score in zip(snapshots, scores):
        distance = snapshot.cluster.total_distance_m

        if abs(score.tailwind_km_h) >= notable_wind_km_h or score.crosswind_km_h >= notable_wind_km_h:
            if score.alignment is WindAlignment.HEADWIND:
                headwind += distance
            elif score.alignment is WindAlignment.TAILWIND:
                tailwind += distance
            else:
                crosswind += distance

        if score.precipitation_mm_h >= notable_rain_mm_h:
            rain += distance
            tier = rain_tier(score.precipitation_mm_h)
            if tier:
                by_tier[tier] += distance
            if rain_start_m is None:
                rain_start_m = covered
                rain_start_time = snapshot.timestamp

        if score.unsafe:
            unsafe += distance

        weighted_wind += snapshot.wind_speed_km_h * distance
        weighted_score += score.score * distance
        max_gust = max(max_gust, snapshot.wind_gusts_km_h)
        max_rain = max(max_rain, score.precipitation_mm_h)
        covered += distance

    return RouteSummary(
        total_distance_m=total,
        headwind_distance_m=headwind,
        tailwind_distance_m=tailwind,
        crosswind_distance_m=crosswind,
        rain_distance_m=rain,
        light_rain_distance_m=by_tier["light"],
        moderate_rain_distance_m=by_tier["moderate"],
        heavy_rain_distance_m=by_tier["heavy"],
        rain_start_m=rain_start_m,
        rain_start_time=rain_start_time,
        max_precipitation_mm_h=max_rain,
        unsafe_distance_m=unsafe,
        mean_wind_km_h=weighted_wind / total if total else 0.0,
        max_gust_km_h=max_gust,
        score=weighted_score / total if total else 0.0,
    )
