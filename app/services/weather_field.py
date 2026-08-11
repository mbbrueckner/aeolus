"""A grid of forecast weather covering a route, over a whole day.

Radar tile services only reach an hour or two ahead, because radar measures
rain rather than predicting it. Planning tomorrow's ride needs a forecast, so
the field is assembled from Open-Meteo point data on a grid instead: one
request returns every grid point for every quarter hour of the day.

Resolution is capped near the underlying model's own grid, around 2 km over
Central Europe. Asking for anything finer only interpolates and adds no
information.
"""

__author__ = "mbbrueckner"
__version__ = "1.0.0"

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import openmeteo_requests

from app.models import RoutePoint

FIELD_URL = "https://api.open-meteo.com/v1/forecast"
SLOT_SECONDS = 900

MODEL_RESOLUTION_KM = 2.0
MAX_GRID_SIDE = 14
MIN_GRID_SIDE = 3

# The field is drawn as a map overlay, so it has to reach past the edges of the
# view. A margin that merely clears the route leaves a small rectangle floating
# on a large map.
MIN_MARGIN_KM = 10.0
MARGIN_FRACTION = 0.7

# Coordinates travel in the query string, and Open-Meteo answers a long enough
# one with 414 rather than truncating it.
MAX_POINTS_PER_REQUEST = 100

FIELD_VARIABLES = [
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation_probability",
]


@dataclass(frozen=True)
class WeatherField:
    """Forecast weather on a latitude/longitude grid over time.

    The wind is carried as vector components rather than speed and bearing,
    because averaging or interpolating an angle across the wrap at 360 degrees
    produces nonsense.

    Attributes:
        latitudes: Grid latitudes, ascending, one per row.
        longitudes: Grid longitudes, ascending, one per column.
        slots: Unix timestamp of each quarter-hour slot.
        precipitation_mm_h: Rain rate, shaped (rows, columns, slots).
        wind_u_m_s: Eastward wind component, same shape.
        wind_v_m_s: Northward wind component, same shape.
        wind_gusts_m_s: Gust speed, same shape.
        precipitation_probability: Chance of rain in percent, same shape. It
            is what carries the growing uncertainty of a forecast further out,
            which the rain rate alone hides.
    """

    latitudes: list[float]
    longitudes: list[float]
    slots: list[int]
    precipitation_mm_h: np.ndarray
    wind_u_m_s: np.ndarray
    wind_v_m_s: np.ndarray
    wind_gusts_m_s: np.ndarray
    precipitation_probability: np.ndarray

    @property
    def shape(self) -> tuple[int, int, int]:
        """Grid rows, grid columns and number of slots."""
        return self.precipitation_mm_h.shape


def route_bounds(points: list[RoutePoint]) -> tuple[float, float, float, float]:
    """Compute a padded bounding box around a route.

    Args:
        points: Points along the route.

    Returns:
        Tuple of (south, north, west, east) in degrees.

    Raises:
        ValueError: If no points are given.
    """
    if not points:
        raise ValueError("need at least one point to build a bounding box")

    latitudes = [p.lat for p in points]
    longitudes = [p.lon for p in points]
    mean_lat = sum(latitudes) / len(latitudes)
    lon_per_km = 111.32 * max(math.cos(math.radians(mean_lat)), 0.01)

    extent_km = max(
        (max(latitudes) - min(latitudes)) * 111.32,
        (max(longitudes) - min(longitudes)) * lon_per_km,
    )
    margin_km = max(MIN_MARGIN_KM, extent_km * MARGIN_FRACTION)

    lat_margin = margin_km / 111.32
    lon_margin = margin_km / lon_per_km

    return (
        min(latitudes) - lat_margin,
        max(latitudes) + lat_margin,
        min(longitudes) - lon_margin,
        max(longitudes) + lon_margin,
    )


def grid_for_bounds(
    bounds: tuple[float, float, float, float],
) -> tuple[list[float], list[float]]:
    """Lay a grid over a bounding box at roughly the model's own resolution.

    Args:
        bounds: Tuple of (south, north, west, east) in degrees.

    Returns:
        Tuple of (latitudes, longitudes) defining the grid.
    """
    south, north, west, east = bounds
    mean_lat = (south + north) / 2.0

    height_km = (north - south) * 111.32
    width_km = (east - west) * 111.32 * math.cos(math.radians(mean_lat))

    rows = _side_count(height_km)
    columns = _side_count(width_km)

    return (
        np.linspace(south, north, rows).tolist(),
        np.linspace(west, east, columns).tolist(),
    )


def fetch_field(
    bounds: tuple[float, float, float, float],
    day: date,
    end_day: date | None = None,
    client: openmeteo_requests.Client | None = None,
) -> WeatherField:
    """Fetch forecast weather across a bounding box over one or more days.

    Args:
        bounds: Tuple of (south, north, west, east) in degrees.
        day: First day to cover, in UTC.
        end_day: Last day to cover, or None to cover only the first. A ride
            starting late in the evening runs into the next day.
        client: Open-Meteo client, for injecting a stub in tests.

    Returns:
        The weather field.
    """
    latitudes, longitudes = grid_for_bounds(bounds)
    points = [(lat, lon) for lat in latitudes for lon in longitudes]
    api = client or openmeteo_requests.Client()

    responses = []
    for start in range(0, len(points), MAX_POINTS_PER_REQUEST):
        chunk = points[start : start + MAX_POINTS_PER_REQUEST]
        responses.extend(
            api.weather_api(
                FIELD_URL,
                params={
                    "latitude": [lat for lat, _ in chunk],
                    "longitude": [lon for _, lon in chunk],
                    "minutely_15": FIELD_VARIABLES,
                    "start_date": day.isoformat(),
                    "end_date": (end_day or day).isoformat(),
                    "wind_speed_unit": "ms",
                    "precipitation_unit": "mm",
                    "models": "best_match",
                },
            )
        )

    return _to_field(responses, latitudes, longitudes)


def _to_field(
    responses: list,
    latitudes: list[float],
    longitudes: list[float],
) -> WeatherField:
    """Stack per-point responses into grid-shaped arrays.

    Args:
        responses: One response per grid point, in row-major order.
        latitudes: Grid latitudes.
        longitudes: Grid longitudes.

    Returns:
        The weather field.
    """
    minutely = responses[0].Minutely15()
    slots = list(range(minutely.Time(), minutely.TimeEnd(), minutely.Interval()))

    stacked = [
        np.vstack([r.Minutely15().Variables(i).ValuesAsNumpy() for r in responses])
        for i in range(len(FIELD_VARIABLES))
    ]
    width = min(stacked[0].shape[1], len(slots))
    rows, columns = len(latitudes), len(longitudes)

    def reshape(values: np.ndarray) -> np.ndarray:
        return values[:, :width].reshape(rows, columns, width)

    speed = reshape(stacked[1])
    blowing_towards = np.radians((reshape(stacked[2]) + 180.0) % 360.0)

    return WeatherField(
        latitudes=latitudes,
        longitudes=longitudes,
        slots=slots[:width],
        # Open-Meteo reports precipitation accumulated over each 15-minute slot.
        precipitation_mm_h=reshape(stacked[0]) * 4.0,
        wind_u_m_s=speed * np.sin(blowing_towards),
        wind_v_m_s=speed * np.cos(blowing_towards),
        wind_gusts_m_s=reshape(stacked[3]),
        precipitation_probability=reshape(stacked[4]),
    )


def _side_count(extent_km: float) -> int:
    """Choose how many grid points span a given distance.

    Args:
        extent_km: Length of the side in kilometres.

    Returns:
        Number of points, between the configured minimum and maximum.
    """
    wanted = int(math.ceil(extent_km / MODEL_RESOLUTION_KM)) + 1
    return max(MIN_GRID_SIDE, min(MAX_GRID_SIDE, wanted))
