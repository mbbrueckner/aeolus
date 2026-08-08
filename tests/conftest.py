"""Shared fixtures for the test suite."""

import gzip
import math
from datetime import datetime, timedelta, timezone

import pytest
from garmin_fit_sdk import Encoder, Profile

MESG_NUM = Profile["mesg_num"]
DEGREES_TO_SEMICIRCLES = 2**31 / 180.0


def build_fit(
    n: int = 600,
    interval_s: int = 1,
    with_power: bool = True,
    with_position: bool = True,
    with_altitude: bool = True,
    climb_m: float = 0.0,
    start: datetime | None = None,
) -> bytes:
    """Build a FIT file resembling a recorded ride.

    Args:
        n: Number of record messages.
        interval_s: Seconds between records.
        with_power: Whether to write a power field.
        with_position: Whether to write position fields.
        with_altitude: Whether to write an altitude field.
        climb_m: Total elevation gained across the ride, spread evenly.
        start: Time of the first record.

    Returns:
        Encoded FIT file bytes.
    """
    start = start or datetime(2026, 5, 12, 8, 30, tzinfo=timezone.utc)
    encoder = Encoder()
    encoder.write_mesg({
        "mesg_num": MESG_NUM["FILE_ID"],
        "type": "activity",
        "manufacturer": "garmin",
        "time_created": start,
    })

    latitude, longitude, distance = 48.14, 11.58, 0.0
    for i in range(n):
        speed = 8.0 + 1.5 * math.sin(i / 60.0)
        distance += speed * interval_s
        latitude += 1e-4 * interval_s
        longitude += 5e-5 * interval_s

        record = {
            "mesg_num": MESG_NUM["RECORD"],
            "timestamp": start + timedelta(seconds=i * interval_s),
            "distance": distance,
            "enhanced_speed": speed,
            "cadence": 85,
            "temperature": 14,
        }
        if with_position:
            record["position_lat"] = int(latitude * DEGREES_TO_SEMICIRCLES)
            record["position_long"] = int(longitude * DEGREES_TO_SEMICIRCLES)
        if with_altitude:
            record["enhanced_altitude"] = 500.0 + climb_m * i / max(n - 1, 1)
        if with_power:
            record["power"] = int(200 + 30 * math.sin(i / 45.0))

        encoder.write_mesg(record)

    return encoder.close()


@pytest.fixture
def fit_file(tmp_path):
    """Write a synthetic FIT file and return its path.

    Returns:
        A factory taking the same arguments as :func:`build_fit` plus
        ``compress``, and returning the path it wrote to.
    """
    counter = {"n": 0}

    def _write(compress: bool = False, **kwargs):
        counter["n"] += 1
        suffix = ".fit.gz" if compress else ".fit"
        path = tmp_path / f"ride{counter['n']}{suffix}"
        data = build_fit(**kwargs)
        path.write_bytes(gzip.compress(data) if compress else data)
        return path

    return _write
