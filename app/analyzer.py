""" Route analysis by weather conditions.

This module orchestrates the analysis of a GPX file: parsing and clustering the
track, fetching a forecast for each cluster's estimated arrival time, scoring
the conditions, and aggregating the result into route-level facts.
"""

__author__ = "mbbrueckner"
__version__ = "2.0.0"

from dataclasses import dataclass
from datetime import datetime

from app.models import ClusterWeatherSnapshot
from app.services.gpx_parser import get_clustered_route
from app.services.route_scorer import ScoringParams, SegmentScore, score_segment
from app.services.summary import RouteSummary, summarise
from app.services.weather import get_weather_for_route


@dataclass(frozen=True)
class RouteAnalysis:
    """A scored route together with the weather it was scored from.

    Attributes:
        snapshots: Weather per cluster, in route order.
        scores: Score per cluster, matching the snapshots.
        summary: Route-level facts aggregated from the clusters.
    """

    snapshots: list[ClusterWeatherSnapshot]
    scores: list[SegmentScore]
    summary: RouteSummary

    @property
    def score(self) -> float:
        """Distance-weighted overall score, from -1.0 to +1.0."""
        return self.summary.score


def analyze_route(
    gpx_file: bytes,
    avg_speed_kmh: float,
    start_time: datetime,
    params: ScoringParams | None = None,
) -> RouteAnalysis:
    """Analyze a GPX route against the forecast for its estimated arrival times.

    Args:
        gpx_file: The GPX file content as bytes.
        avg_speed_kmh: The average speed in km/h to use for clustering.
        start_time: The departure time, used to estimate arrival times.
        params: Coefficients of the scoring model, or None for the defaults.

    Returns:
        The scored route.
    """
    route_clusters = get_clustered_route(gpx_file, avg_speed_kmh, start_time)
    snapshots = get_weather_for_route(route_clusters)
    scores = [
        score_segment(snapshot, params) if params else score_segment(snapshot)
        for snapshot in snapshots
    ]

    return RouteAnalysis(
        snapshots=snapshots,
        scores=scores,
        summary=summarise(snapshots, scores),
    )
