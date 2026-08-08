"""Loading recorded rides from FIT files into arrays the power model can use.

Head units record unevenly: Garmin's smart recording stretches the interval
when little changes, positions drop out under trees, and barometric altitude
carries enough noise that a per-sample gradient is meaningless. This module
normalises all of that into plain arrays, and derives the gradient and
acceleration over distance windows wide enough to be stable.
"""

__author__ = "mbbrueckner"
__version__ = "1.0.0"

import gzip
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from garmin_fit_sdk import Decoder, Stream

SEMICIRCLE_TO_DEGREES = 180.0 / 2**31
GRADIENT_WINDOW_M = 60.0
SPEED_WINDOW_S = 5.0
MAX_PLAUSIBLE_GRADIENT = 0.30


@dataclass(frozen=True)
class RideSamples:
    """One recorded ride as parallel arrays, one entry per record message.

    Attributes:
        timestamps: Sample times as timezone-aware datetimes.
        latitude_deg: Latitudes in decimal degrees, NaN where unavailable.
        longitude_deg: Longitudes in decimal degrees, NaN where unavailable.
        altitude_m: Elevation in metres, NaN where unavailable.
        speed_m_s: Ground speed in m/s.
        power_w: Power meter readings in watts, NaN where unavailable.
        cadence_rpm: Pedalling cadence, NaN where unavailable.
        temperature_c: Air temperature in degrees Celsius, NaN where unavailable.
        distance_m: Cumulative distance in metres.
    """

    timestamps: np.ndarray
    latitude_deg: np.ndarray
    longitude_deg: np.ndarray
    altitude_m: np.ndarray
    speed_m_s: np.ndarray
    power_w: np.ndarray
    cadence_rpm: np.ndarray
    temperature_c: np.ndarray
    distance_m: np.ndarray

    def __len__(self) -> int:
        return len(self.timestamps)

    @property
    def duration_s(self) -> float:
        """Elapsed time from first to last sample in seconds."""
        if len(self) < 2:
            return 0.0
        return (self.timestamps[-1] - self.timestamps[0]).total_seconds()

    @property
    def median_interval_s(self) -> float:
        """Median gap between samples, which reveals smart recording."""
        if len(self) < 2:
            return math.nan
        gaps = np.array([
            (b - a).total_seconds() for a, b in zip(self.timestamps, self.timestamps[1:])
        ])
        positive = gaps[gaps > 0]
        return float(np.median(positive)) if positive.size else math.nan

    def has(self, field: str, minimum_coverage: float = 0.8) -> bool:
        """Check whether a field is populated for most of the ride.

        Args:
            field: Name of one of the array attributes.
            minimum_coverage: Fraction of samples that must carry a value.

        Returns:
            True if the field is present often enough to rely on.
        """
        values = getattr(self, field)
        if len(values) == 0:
            return False
        return float(np.mean(~np.isnan(values))) >= minimum_coverage


def load_ride(path: Path | str) -> RideSamples | None:
    """Read a FIT file, gzipped or not, into arrays.

    Args:
        path: Path to a .fit or .fit.gz file.

    Returns:
        The ride's samples, or None if the file cannot be decoded or holds no
        record messages.
    """
    path = Path(path)
    try:
        if path.suffix.lower() == ".gz":
            stream = Stream.from_byte_array(gzip.decompress(path.read_bytes()))
        else:
            stream = Stream.from_file(str(path))
        messages, _ = Decoder(stream).read()
    except Exception:
        return None

    records = [r for r in messages.get("record_mesgs", []) if r.get("timestamp") is not None]
    if not records:
        return None

    return RideSamples(
        timestamps=np.array([r["timestamp"] for r in records], dtype=object),
        latitude_deg=_semicircles(records, "position_lat"),
        longitude_deg=_semicircles(records, "position_long"),
        altitude_m=_column(records, "enhanced_altitude", "altitude"),
        speed_m_s=_column(records, "enhanced_speed", "speed"),
        power_w=_column(records, "power"),
        cadence_rpm=_column(records, "cadence"),
        temperature_c=_column(records, "temperature"),
        distance_m=_column(records, "distance"),
    )


def gradient(samples: RideSamples, window_m: float = GRADIENT_WINDOW_M) -> np.ndarray:
    """Compute slope as rise over run, smoothed over a distance window.

    A barometric altimeter is precise to a few tenths of a metre, which over
    one second of riding is the same order as the real elevation change. Taken
    per sample the gradient would be mostly noise, so altitude is averaged over
    a window before differencing.

    Args:
        samples: The ride.
        window_m: Width of the smoothing window in metres.

    Returns:
        Gradient per sample, clipped to plausible road slopes. NaN where
        altitude or distance is missing.
    """
    altitude = _fill_gaps(samples.altitude_m)
    distance = _fill_gaps(samples.distance_m)
    if np.all(np.isnan(altitude)) or np.all(np.isnan(distance)):
        return np.full(len(samples), np.nan)

    span_m = max(np.nanmedian(np.abs(np.diff(distance))), 1e-6)
    width = max(3, int(round(window_m / span_m)))

    smoothed = _moving_average(altitude, width)
    rise = np.gradient(smoothed)
    run = np.gradient(distance)

    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.where(np.abs(run) > 1e-3, rise / run, np.nan)

    return np.clip(slope, -MAX_PLAUSIBLE_GRADIENT, MAX_PLAUSIBLE_GRADIENT)


def acceleration(samples: RideSamples, window_s: float = SPEED_WINDOW_S) -> np.ndarray:
    """Compute rate of change of ground speed, smoothed over time.

    Args:
        samples: The ride.
        window_s: Width of the smoothing window in seconds.

    Returns:
        Acceleration per sample in m/s². NaN where speed is missing.
    """
    speed = _fill_gaps(samples.speed_m_s)
    if np.all(np.isnan(speed)):
        return np.full(len(samples), np.nan)

    elapsed = np.array([
        (t - samples.timestamps[0]).total_seconds() for t in samples.timestamps
    ])
    interval = max(samples.median_interval_s, 1e-6)
    width = max(3, int(round(window_s / interval)))

    smoothed = _moving_average(speed, width)
    time_step = np.gradient(elapsed)

    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(time_step) > 1e-6, np.gradient(smoothed) / time_step, np.nan)


def pedalling_mask(
    samples: RideSamples,
    minimum_speed_m_s: float = 3.0,
    minimum_power_w: float = 20.0,
) -> np.ndarray:
    """Select samples where the power reading says something about the air.

    Coasting and stops carry no information: the rider is not pushing against
    drag, so the power balance cannot be inverted for wind. Everything the
    power model needs must also be present.

    Args:
        samples: The ride.
        minimum_speed_m_s: Speed below which drag is too small to resolve.
        minimum_power_w: Power below which the rider is treated as coasting.

    Returns:
        Boolean mask over the samples.
    """
    slope = gradient(samples)
    accel = acceleration(samples)

    usable = (
        (samples.speed_m_s >= minimum_speed_m_s)
        & (samples.power_w >= minimum_power_w)
        & ~np.isnan(samples.latitude_deg)
        & ~np.isnan(samples.longitude_deg)
        & ~np.isnan(slope)
        & ~np.isnan(accel)
    )
    return np.nan_to_num(usable, nan=False).astype(bool)


def _column(records: list[dict], *names: str) -> np.ndarray:
    """Extract a numeric field, taking the first name that carries values.

    Args:
        records: Decoded record messages.
        *names: Field names in order of preference.

    Returns:
        Float array with NaN where the field is absent.
    """
    best = np.full(len(records), np.nan)
    best_count = 0

    for name in names:
        values = np.array(
            [r.get(name) if isinstance(r.get(name), (int, float)) else np.nan for r in records],
            dtype=float,
        )
        count = int(np.count_nonzero(~np.isnan(values)))
        if count > best_count:
            best, best_count = values, count

    return best


def _semicircles(records: list[dict], name: str) -> np.ndarray:
    """Extract a position field and convert it from semicircles to degrees.

    Args:
        records: Decoded record messages.
        name: Field name.

    Returns:
        Degrees, with NaN where the position is absent.
    """
    return _column(records, name) * SEMICIRCLE_TO_DEGREES


def _fill_gaps(values: np.ndarray) -> np.ndarray:
    """Interpolate over interior NaNs so differencing does not spread them.

    Args:
        values: Array that may contain NaNs.

    Returns:
        Array with interior NaNs linearly interpolated. Leading and trailing
        NaNs are left in place.
    """
    present = ~np.isnan(values)
    if not present.any() or present.all():
        return values.copy()

    index = np.arange(len(values))
    filled = values.copy()
    first, last = index[present][0], index[present][-1]
    interior = slice(first, last + 1)

    filled[interior] = np.interp(index[interior], index[present], values[present])
    return filled


def _moving_average(values: np.ndarray, width: int) -> np.ndarray:
    """Smooth an array with a centred moving average.

    Args:
        values: Array to smooth, without interior NaNs.
        width: Window width in samples.

    Returns:
        Smoothed array of the same length, with edges handled by reflection.
    """
    if width <= 1 or len(values) < 3:
        return values.copy()

    width = min(width, len(values))
    pad = width // 2
    padded = np.pad(values, pad, mode="reflect")
    kernel = np.ones(width) / width
    return np.convolve(padded, kernel, mode="same")[pad : pad + len(values)]
