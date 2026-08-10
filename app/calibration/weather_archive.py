"""Historical weather lookup for recorded rides.

Uses Open-Meteo's Historical Forecast API, which stitches together the opening
hours of successive model runs. That tracks what the weather actually did far
better than the ERA5 reanalysis behind the plain historical endpoint, whose
~25 km grid is too coarse to say anything useful about wind on a bike.

Responses are cached on disk, since the same ride gets re-joined every time the
calibration is re-run and the archive never changes.
"""

__author__ = "mbbrueckner"
__version__ = "1.0.0"

import hashlib
import json
import pickle
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import openmeteo_requests

ARCHIVE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
SLOT_SECONDS = 900

VARIABLES = [
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation",
    "temperature_2m",
    "surface_pressure",
]


@dataclass(frozen=True)
class ArchiveWeather:
    """Weather for a set of locations over a range of 15-minute slots.

    Attributes:
        slots: Unix timestamps of each slot's start, one per column.
        wind_speed_m_s: Wind speed, shaped (locations, slots).
        wind_direction_deg: Meteorological wind origin direction.
        wind_gusts_m_s: Gust speed.
        precipitation_mm: Precipitation accumulated over the slot.
        temperature_c: Air temperature.
        pressure_hpa: Surface pressure at the location's altitude.
    """

    slots: np.ndarray
    wind_speed_m_s: np.ndarray
    wind_direction_deg: np.ndarray
    wind_gusts_m_s: np.ndarray
    precipitation_mm: np.ndarray
    temperature_c: np.ndarray
    pressure_hpa: np.ndarray

    def at(self, location: int, timestamps: np.ndarray) -> dict[str, np.ndarray]:
        """Look up weather for one location at arbitrary times.

        Args:
            location: Index of the location, matching the order requested.
            timestamps: Unix timestamps to look up.

        Returns:
            Dict of variable name to values, one per requested timestamp, with
            NaN where the time falls outside the fetched range.
        """
        wanted = np.floor(np.asarray(timestamps, dtype=float) / SLOT_SECONDS) * SLOT_SECONDS
        column = np.searchsorted(self.slots, wanted)
        inside = (column < len(self.slots)) & (column >= 0)
        column = np.clip(column, 0, len(self.slots) - 1)

        def pick(values: np.ndarray) -> np.ndarray:
            picked = values[location, column].astype(float)
            return np.where(inside, picked, np.nan)

        return {
            "wind_speed_m_s": pick(self.wind_speed_m_s),
            "wind_direction_deg": pick(self.wind_direction_deg),
            "wind_gusts_m_s": pick(self.wind_gusts_m_s),
            "precipitation_mm": pick(self.precipitation_mm),
            "temperature_c": pick(self.temperature_c),
            "pressure_hpa": pick(self.pressure_hpa),
        }


def fetch_archive(
    locations: list[tuple[float, float]],
    start: date,
    end: date,
    cache_dir: Path | str = ".weather_cache",
    client: openmeteo_requests.Client | None = None,
) -> ArchiveWeather:
    """Fetch archived weather for several locations over a date range.

    Args:
        locations: (latitude, longitude) pairs in decimal degrees.
        start: First date to cover, in UTC.
        end: Last date to cover, in UTC.
        cache_dir: Directory holding cached responses.
        client: Open-Meteo client, for injecting a stub in tests.

    Returns:
        The weather for every location and slot.

    Raises:
        ValueError: If no locations are given.
    """
    if not locations:
        raise ValueError("need at least one location")

    cache_path = Path(cache_dir) / f"{_cache_key(locations, start, end)}.pickle"
    if cache_path.exists():
        with cache_path.open("rb") as handle:
            return pickle.load(handle)

    params = {
        "latitude": [lat for lat, _ in locations],
        "longitude": [lon for _, lon in locations],
        "minutely_15": VARIABLES,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
        "models": "best_match",
    }

    responses = (client or openmeteo_requests.Client()).weather_api(ARCHIVE_URL, params=params)
    weather = _to_archive(responses)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(weather, handle)

    return weather


def slot_of(timestamp: datetime) -> int:
    """Round a time down to the start of its 15-minute slot.

    Args:
        timestamp: Time to round, timezone-aware.

    Returns:
        Unix timestamp of the slot's start.
    """
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return int(timestamp.timestamp()) // SLOT_SECONDS * SLOT_SECONDS


def _to_archive(responses: list) -> ArchiveWeather:
    """Convert Open-Meteo responses into stacked arrays.

    Args:
        responses: One response per requested location, in request order.

    Returns:
        The weather with one row per location.
    """
    columns: list[list[np.ndarray]] = [[] for _ in VARIABLES]
    slots = None

    for response in responses:
        minutely = response.Minutely15()
        if slots is None:
            slots = np.arange(minutely.Time(), minutely.TimeEnd(), minutely.Interval())
        for index in range(len(VARIABLES)):
            columns[index].append(minutely.Variables(index).ValuesAsNumpy())

    stacked = [np.vstack(column) for column in columns]
    width = min(stacked[0].shape[1], len(slots))

    return ArchiveWeather(
        slots=np.asarray(slots[:width]),
        wind_speed_m_s=stacked[0][:, :width],
        wind_direction_deg=stacked[1][:, :width],
        wind_gusts_m_s=stacked[2][:, :width],
        precipitation_mm=stacked[3][:, :width],
        temperature_c=stacked[4][:, :width],
        pressure_hpa=stacked[5][:, :width],
    )


def _cache_key(locations: list[tuple[float, float]], start: date, end: date) -> str:
    """Build a stable filename for a request.

    Coordinates are rounded to about 100 m, which is far finer than the weather
    model's grid and keeps near-identical requests sharing a cache entry.

    Args:
        locations: Requested coordinates.
        start: First date.
        end: Last date.

    Returns:
        Hex digest identifying the request.
    """
    payload = json.dumps(
        {
            "locations": [[round(lat, 3), round(lon, 3)] for lat, lon in locations],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "variables": VARIABLES,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]
