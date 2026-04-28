# tests/test_resampler.py
from __future__ import annotations
from pathlib import Path
import pytest
from lawn_rain_model.simulation.weather import resample_history, DEFAULT_SENSOR_MAP

FIXTURES = Path(__file__).parent / "fixtures"


def test_simple_output_length() -> None:
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert len(steps) == 2  # hours 10 and 11


def test_hour_indices_sequential() -> None:
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    for i, s in enumerate(steps):
        assert s.hour == i


def test_tod_hour_10() -> None:
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert steps[0].tod == 10


def test_rain_hour_10() -> None:
    """Accumulation goes from 0.0 → 0.5 during hour 10: rain = 0.5"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert abs(steps[0].rain_inches - 0.5) < 0.001


def test_rain_hour_11() -> None:
    """Accumulation goes from 0.5 → 0.8 during hour 11: rain = 0.3"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert abs(steps[1].rain_inches - 0.3) < 0.001


def test_temp_forward_fill_hour_10() -> None:
    """Last temp reading in hour 10 is 76.0 at 10:30"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert steps[0].temp == 76.0


def test_temp_forward_fill_hour_11() -> None:
    """Last temp reading in hour 11 is 74.0 at 11:30"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert steps[1].temp == 74.0


def test_elevation_last_in_hour() -> None:
    """sun_elevation: last reading in hour 10 is 45.0 at 10:30"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert steps[0].elevation == 45.0


def test_midnight_reset_rain() -> None:
    """
    Hour 23: accum = 0.9 (no change during hour).
    Hour 0: accum resets from 0.9 → 0.1 at 00:30.
    The negative delta is detected at hour 0; rain = post-reset value = 0.1.
    """
    steps = resample_history(FIXTURES / "history_midnight.csv", DEFAULT_SENSOR_MAP)
    # Hour 0 is where the midnight reset is detected
    hour_0 = next(s for s in steps if s.tod == 0)
    assert abs(hour_0.rain_inches - 0.1) < 0.001


def test_custom_sensor_map(tmp_path: Path) -> None:
    """A scenario-level sensor_map override renames entity IDs."""
    csv_text = (
        "entity_id,state,last_changed\n"
        "my.temp_sensor,72.0,2026-04-24T08:00:00.000Z\n"
        "my.accum_sensor,0.0,2026-04-24T08:00:00.000Z\n"
        "my.accum_sensor,0.2,2026-04-24T08:45:00.000Z\n"
        "my.rh_sensor,55,2026-04-24T08:00:00.000Z\n"
        "my.wind_sensor,3.0,2026-04-24T08:00:00.000Z\n"
        "my.cloud_sensor,20,2026-04-24T08:00:00.000Z\n"
        "my.elev_sensor,30.0,2026-04-24T08:00:00.000Z\n"
    )
    p = tmp_path / "custom.csv"
    p.write_text(csv_text)
    custom_map = {
        "temp":                "my.temp_sensor",
        "rh":                  "my.rh_sensor",
        "wind":                "my.wind_sensor",
        "clouds":              "my.cloud_sensor",
        "elevation":           "my.elev_sensor",
        "liquid_accumulation": "my.accum_sensor",
    }
    steps = resample_history(p, custom_map)
    assert len(steps) == 1
    assert steps[0].temp == 72.0
    assert abs(steps[0].rain_inches - 0.2) < 0.001
