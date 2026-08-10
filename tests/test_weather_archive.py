"""Tests for app/calibration/weather_archive.py"""

import numpy as np
import pytest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from app.calibration.weather_archive import (
    SLOT_SECONDS,
    VARIABLES,
    ArchiveWeather,
    fetch_archive,
    slot_of,
)

START_UNIX = 1_749_000_000 // SLOT_SECONDS * SLOT_SECONDS
N_SLOTS = 96


def make_archive(n_locations: int = 2) -> ArchiveWeather:
    """Build an ArchiveWeather with recognisable values per location and slot."""
    slots = np.arange(START_UNIX, START_UNIX + N_SLOTS * SLOT_SECONDS, SLOT_SECONDS)
    ramp = np.arange(N_SLOTS, dtype=float)
    grid = np.vstack([ramp + 100 * i for i in range(n_locations)])
    return ArchiveWeather(
        slots=slots,
        wind_speed_m_s=grid,
        wind_direction_deg=grid + 1,
        wind_gusts_m_s=grid + 2,
        precipitation_mm=grid + 3,
        temperature_c=grid + 4,
        pressure_hpa=grid + 5,
    )


def fake_client(n_locations: int = 2):
    """Build a stub Open-Meteo client returning deterministic responses."""
    responses = []
    for i in range(n_locations):
        minutely = MagicMock()
        minutely.Time.return_value = START_UNIX
        minutely.TimeEnd.return_value = START_UNIX + N_SLOTS * SLOT_SECONDS
        minutely.Interval.return_value = SLOT_SECONDS
        minutely.Variables.side_effect = lambda v, base=i: MagicMock(
            ValuesAsNumpy=MagicMock(
                return_value=np.arange(N_SLOTS, dtype=float) + 100 * base + v
            )
        )
        response = MagicMock()
        response.Minutely15.return_value = minutely
        responses.append(response)

    client = MagicMock()
    client.weather_api.return_value = responses
    return client


# ── slot_of ───────────────────────────────────────────────────────

def test_slot_rounds_down():
    stamp = datetime(2026, 5, 12, 8, 37, 42, tzinfo=timezone.utc)
    assert slot_of(stamp) == int(datetime(2026, 5, 12, 8, 30, tzinfo=timezone.utc).timestamp())

def test_slot_on_boundary_is_unchanged():
    stamp = datetime(2026, 5, 12, 8, 30, tzinfo=timezone.utc)
    assert slot_of(stamp) == int(stamp.timestamp())

def test_slot_assumes_utc_when_naive():
    naive = datetime(2026, 5, 12, 8, 30)
    aware = datetime(2026, 5, 12, 8, 30, tzinfo=timezone.utc)
    assert slot_of(naive) == slot_of(aware)

def test_slot_is_multiple_of_interval():
    assert slot_of(datetime(2026, 5, 12, 8, 37, tzinfo=timezone.utc)) % SLOT_SECONDS == 0


# ── ArchiveWeather.at ─────────────────────────────────────────────

def test_lookup_picks_the_containing_slot():
    archive = make_archive()
    got = archive.at(0, np.array([START_UNIX + 5]))
    assert got["wind_speed_m_s"][0] == 0.0

def test_lookup_advances_with_time():
    archive = make_archive()
    got = archive.at(0, np.array([START_UNIX, START_UNIX + SLOT_SECONDS]))
    assert got["wind_speed_m_s"].tolist() == [0.0, 1.0]

def test_lookup_is_per_location():
    archive = make_archive()
    first = archive.at(0, np.array([START_UNIX]))["wind_speed_m_s"][0]
    second = archive.at(1, np.array([START_UNIX]))["wind_speed_m_s"][0]
    assert second - first == 100.0

def test_lookup_returns_all_variables():
    archive = make_archive()
    got = archive.at(0, np.array([START_UNIX]))
    assert set(got) == {
        "wind_speed_m_s", "wind_direction_deg", "wind_gusts_m_s",
        "precipitation_mm", "temperature_c", "pressure_hpa",
    }

def test_lookup_beyond_range_is_nan():
    archive = make_archive()
    beyond = START_UNIX + (N_SLOTS + 10) * SLOT_SECONDS
    assert np.isnan(archive.at(0, np.array([beyond]))["wind_speed_m_s"][0])

def test_lookup_within_a_slot_is_constant():
    """Anything inside one quarter hour must resolve to the same forecast."""
    archive = make_archive()
    inside = np.array([START_UNIX + s for s in (0, 300, 899)])
    values = archive.at(0, inside)["wind_speed_m_s"]
    assert len(set(values.tolist())) == 1


# ── fetch_archive ─────────────────────────────────────────────────

def test_fetch_returns_one_row_per_location(tmp_path):
    weather = fetch_archive(
        [(48.0, 11.0), (48.1, 11.1)],
        date(2025, 6, 4), date(2025, 6, 4),
        cache_dir=tmp_path, client=fake_client(2),
    )
    assert weather.wind_speed_m_s.shape[0] == 2

def test_fetch_requests_wind_in_metres_per_second(tmp_path):
    client = fake_client(1)
    fetch_archive([(48.0, 11.0)], date(2025, 6, 4), date(2025, 6, 4),
                  cache_dir=tmp_path, client=client)
    params = client.weather_api.call_args.kwargs["params"]
    assert params["wind_speed_unit"] == "ms"

def test_fetch_requests_all_variables(tmp_path):
    client = fake_client(1)
    fetch_archive([(48.0, 11.0)], date(2025, 6, 4), date(2025, 6, 4),
                  cache_dir=tmp_path, client=client)
    assert client.weather_api.call_args.kwargs["params"]["minutely_15"] == VARIABLES

def test_second_fetch_is_served_from_cache(tmp_path):
    client = fake_client(1)
    args = ([(48.0, 11.0)], date(2025, 6, 4), date(2025, 6, 4))
    first = fetch_archive(*args, cache_dir=tmp_path, client=client)
    second = fetch_archive(*args, cache_dir=tmp_path, client=client)

    assert client.weather_api.call_count == 1
    assert np.array_equal(first.wind_speed_m_s, second.wind_speed_m_s)

def test_different_dates_are_cached_separately(tmp_path):
    client = fake_client(1)
    fetch_archive([(48.0, 11.0)], date(2025, 6, 4), date(2025, 6, 4),
                  cache_dir=tmp_path, client=client)
    fetch_archive([(48.0, 11.0)], date(2025, 6, 5), date(2025, 6, 5),
                  cache_dir=tmp_path, client=client)
    assert client.weather_api.call_count == 2

def test_nearly_identical_coordinates_share_a_cache_entry(tmp_path):
    """Rounding to about 100 m is far finer than the weather model's grid."""
    client = fake_client(1)
    fetch_archive([(48.00001, 11.00001)], date(2025, 6, 4), date(2025, 6, 4),
                  cache_dir=tmp_path, client=client)
    fetch_archive([(48.00002, 11.00002)], date(2025, 6, 4), date(2025, 6, 4),
                  cache_dir=tmp_path, client=client)
    assert client.weather_api.call_count == 1

def test_no_locations_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        fetch_archive([], date(2025, 6, 4), date(2025, 6, 4), cache_dir=tmp_path)
