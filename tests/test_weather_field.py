"""Tests for app/services/weather_field.py"""

import math
import numpy as np
import pytest
from datetime import date
from unittest.mock import MagicMock

from app.models import RoutePoint
from app.services.weather_field import (
    FIELD_VARIABLES,
    MAX_GRID_SIDE,
    MIN_GRID_SIDE,
    SLOT_SECONDS,
    fetch_field,
    grid_for_bounds,
    route_bounds,
)

START_UNIX = 1_770_000_000 // SLOT_SECONDS * SLOT_SECONDS
N_SLOTS = 96


def fake_client(
    speed_m_s: float = 5.0,
    direction_deg: float = 270.0,
    rain_mm: float = 0.25,
    probability: float = 40.0,
):
    """Build a stub client returning one uniform value per variable."""
    values = {
        "precipitation": rain_mm,
        "wind_speed_10m": speed_m_s,
        "wind_direction_10m": direction_deg,
        "wind_gusts_10m": speed_m_s * 1.5,
        "precipitation_probability": probability,
    }

    def response_for(_):
        minutely = MagicMock()
        minutely.Time.return_value = START_UNIX
        minutely.TimeEnd.return_value = START_UNIX + N_SLOTS * SLOT_SECONDS
        minutely.Interval.return_value = SLOT_SECONDS
        minutely.Variables.side_effect = lambda i: MagicMock(
            ValuesAsNumpy=MagicMock(
                return_value=np.full(N_SLOTS, values[FIELD_VARIABLES[i]], dtype=float)
            )
        )
        response = MagicMock()
        response.Minutely15.return_value = minutely
        return response

    client = MagicMock()
    client.weather_api.side_effect = lambda url, params: [
        response_for(i) for i in range(len(params["latitude"]))
    ]
    return client


# ── route_bounds ──────────────────────────────────────────────────

def test_bounds_enclose_every_point():
    points = [RoutePoint(lat=48.0, lon=11.0), RoutePoint(lat=48.2, lon=11.3)]
    south, north, west, east = route_bounds(points)

    assert south < 48.0 and north > 48.2
    assert west < 11.0 and east > 11.3

def test_bounds_add_a_margin():
    """A single point still needs an area around it."""
    south, north, west, east = route_bounds([RoutePoint(lat=48.0, lon=11.0)])
    assert north > south
    assert east > west

def test_bounds_need_points():
    with pytest.raises(ValueError):
        route_bounds([])

def test_longitude_margin_widens_towards_the_poles():
    """A degree of longitude is shorter up north, so the margin must be wider."""
    _, _, west_south, east_south = route_bounds([RoutePoint(lat=10.0, lon=11.0)])
    _, _, west_north, east_north = route_bounds([RoutePoint(lat=65.0, lon=11.0)])

    assert (east_north - west_north) > (east_south - west_south)


# ── grid_for_bounds ───────────────────────────────────────────────

def test_grid_spans_the_bounds_exactly():
    latitudes, longitudes = grid_for_bounds((48.0, 48.2, 11.0, 11.3))
    assert latitudes[0] == 48.0 and latitudes[-1] == 48.2
    assert longitudes[0] == 11.0 and longitudes[-1] == 11.3

def test_grid_is_ascending():
    latitudes, longitudes = grid_for_bounds((48.0, 48.2, 11.0, 11.3))
    assert latitudes == sorted(latitudes)
    assert longitudes == sorted(longitudes)

def test_large_area_is_capped():
    """Beyond the model's own resolution more points add nothing."""
    latitudes, longitudes = grid_for_bounds((45.0, 55.0, 5.0, 15.0))
    assert len(latitudes) <= MAX_GRID_SIDE
    assert len(longitudes) <= MAX_GRID_SIDE

def test_tiny_area_still_gets_a_usable_grid():
    latitudes, longitudes = grid_for_bounds((48.0, 48.001, 11.0, 11.001))
    assert len(latitudes) >= MIN_GRID_SIDE
    assert len(longitudes) >= MIN_GRID_SIDE

def test_wide_area_gets_more_columns_than_rows():
    latitudes, longitudes = grid_for_bounds((48.0, 48.02, 11.0, 11.4))
    assert len(longitudes) > len(latitudes)


# ── fetch_field ───────────────────────────────────────────────────

def test_field_is_shaped_rows_columns_slots():
    field = fetch_field((48.0, 48.2, 11.0, 11.3), date(2026, 8, 12), client=fake_client())
    rows, columns, slots = field.shape

    assert rows == len(field.latitudes)
    assert columns == len(field.longitudes)
    assert slots == len(field.slots)

def test_one_request_covers_the_whole_grid():
    client = fake_client()
    fetch_field((48.0, 48.2, 11.0, 11.3), date(2026, 8, 12), client=client)
    assert client.weather_api.call_count == 1

def test_slots_are_quarter_hours():
    field = fetch_field((48.0, 48.2, 11.0, 11.3), date(2026, 8, 12), client=fake_client())
    gaps = {b - a for a, b in zip(field.slots, field.slots[1:])}
    assert gaps == {SLOT_SECONDS}

def test_precipitation_is_converted_to_millimetres_per_hour():
    """Open-Meteo reports accumulation over each quarter hour."""
    field = fetch_field(
        (48.0, 48.2, 11.0, 11.3), date(2026, 8, 12), client=fake_client(rain_mm=0.25)
    )
    assert np.allclose(field.precipitation_mm_h, 1.0)

def test_wind_from_the_west_blows_eastward():
    field = fetch_field(
        (48.0, 48.2, 11.0, 11.3), date(2026, 8, 12),
        client=fake_client(speed_m_s=5.0, direction_deg=270.0),
    )
    assert np.allclose(field.wind_u_m_s, 5.0, atol=1e-9)
    assert np.allclose(field.wind_v_m_s, 0.0, atol=1e-9)

def test_wind_from_the_north_blows_southward():
    field = fetch_field(
        (48.0, 48.2, 11.0, 11.3), date(2026, 8, 12),
        client=fake_client(speed_m_s=4.0, direction_deg=0.0),
    )
    assert np.allclose(field.wind_u_m_s, 0.0, atol=1e-9)
    assert np.allclose(field.wind_v_m_s, -4.0, atol=1e-9)

def test_components_preserve_wind_speed():
    field = fetch_field(
        (48.0, 48.2, 11.0, 11.3), date(2026, 8, 12),
        client=fake_client(speed_m_s=7.0, direction_deg=137.0),
    )
    magnitude = np.hypot(field.wind_u_m_s, field.wind_v_m_s)
    assert np.allclose(magnitude, 7.0, atol=1e-9)

def test_gusts_are_carried_through():
    field = fetch_field(
        (48.0, 48.2, 11.0, 11.3), date(2026, 8, 12), client=fake_client(speed_m_s=6.0)
    )
    assert np.allclose(field.wind_gusts_m_s, 9.0)

def test_request_asks_for_metres_per_second():
    client = fake_client()
    fetch_field((48.0, 48.2, 11.0, 11.3), date(2026, 8, 12), client=client)
    assert client.weather_api.call_args.kwargs["params"]["wind_speed_unit"] == "ms"


def test_probability_is_carried_through():
    field = fetch_field(
        (48.0, 48.2, 11.0, 11.3), date(2026, 8, 12), client=fake_client(probability=65.0)
    )
    assert np.allclose(field.precipitation_probability, 65.0)

def test_probability_is_shaped_like_the_rest():
    field = fetch_field((48.0, 48.2, 11.0, 11.3), date(2026, 8, 12), client=fake_client())
    assert field.precipitation_probability.shape == field.precipitation_mm_h.shape
