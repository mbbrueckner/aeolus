"""Data models for GPS route points, segments, and segment clusters.

This module defines the core data structures used to represent GPS route points, segments between points, and clusters of segments with similar bearings. These models are used throughout the application for processing GPX files, clustering route segments, and associating weather data with specific locations along a route.
"""

__author__ = "mbbrueckner"
__version__ = "1.0.0"

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class RoutePoint:
    """A single point along a GPS route.

    Attributes:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        elevation_m: Elevation above sea level in meters, if available.
        timestamp: UTC timestamp of the recorded point, if available.
        track_index: Position of this point in the unsimplified track, if it
            came from one. Simplification keeps only a fraction of the points,
            so this is what maps a cluster back to the full-resolution geometry
            for drawing.
    """

    lat: float
    lon: float
    elevation_m: float | None = None
    timestamp: datetime | None = None
    track_index: int | None = None


@dataclass
class Segment:
    """A route segment between two consecutive RoutePoints.

    Attributes:
        start: Starting point of the segment.
        end: Ending point of the segment.
        bearing_deg: Initial bearing from start to end in degrees (0–360).
        distance_m: Great-circle distance from start to end in meters.
    """

    start: RoutePoint
    end: RoutePoint
    bearing_deg: float
    distance_m: float


@dataclass
class SegmentCluster:
    """A Cluster of consecutive Segments with similar bearing, representing a straight portion of the route.

    Attributes:
        segments: List of Segments in the cluster.
        mean_bearing: Average bearing of the segments in degrees (0–360).
        representative_point: A representative RoutePoint for the cluster (geographic midpoint of the middle segment).
        entry_time: When the rider is expected to reach the start of this
            cluster. The representative point's timestamp sits half a cluster
            later, so it cannot anchor the ends of the route.
        exit_time: When the rider is expected to leave this cluster.
    """
    segments: list[Segment]
    mean_bearing: float
    representative_point: RoutePoint
    entry_time: datetime | None = None
    exit_time: datetime | None = None

    @property
    def total_distance_m(self) -> float:
        """Total length of all segments in the cluster in meters."""
        return sum(s.distance_m for s in self.segments)


@dataclass
class ClusteredRoute:
    """A complete route represented as a list of SegmentClusters.

    Attributes:
        clusters: List of SegmentClusters that make up the route.
        track: The full-resolution track the clusters were derived from.
            Clustering runs on a simplified copy, which is fine for sampling
            weather but too coarse to draw.
    """
    clusters: list[SegmentCluster]
    track: list[RoutePoint] = field(default_factory=list)

    def points_for(self, cluster: SegmentCluster) -> list[RoutePoint]:
        """Return a cluster's geometry at full resolution.

        Args:
            cluster: One of this route's clusters.

        Returns:
            The original track points spanning the cluster, or the cluster's
            own simplified points if the track is unavailable.
        """
        start = cluster.segments[0].start.track_index if cluster.segments else None
        end = cluster.segments[-1].end.track_index if cluster.segments else None

        if not self.track or start is None or end is None:
            return [cluster.segments[0].start] + [s.end for s in cluster.segments]

        return self.track[start : end + 1]

    @property
    def total_distance_m(self) -> float:
        """Total length of all clusters in the route in meters."""
        return sum(c.total_distance_m for c in self.clusters)

    @property
    def representative_points(self) -> list[RoutePoint]:
        """List of representative RoutePoints, one per cluster."""
        return [c.representative_point for c in self.clusters]

@dataclass
class ClusterWeatherSnapshot:
    """Weather conditions observed at a specific cluster's representative point and time.

    Attributes:
        cluster: The SegmentCluster this snapshot belongs to.
        timestamp: UTC datetime when the rider is expected to reach this cluster.
        wind_speed_km_h: Average wind speed in km/h at 10 m height.
        wind_direction_deg: Meteorological wind origin direction in degrees (0–360, 0 = from north).
        wind_gusts_km_h: Wind gust speed in km/h.
        precipitation_mm_h: Precipitation accumulated over the 15-minute interval in mm
            (equivalent to mm/15 min; multiply by 4 to get mm/h).
    """
    cluster: SegmentCluster
    timestamp: datetime
    wind_speed_km_h: float
    wind_direction_deg: float
    wind_gusts_km_h: float
    precipitation_mm_h: float


