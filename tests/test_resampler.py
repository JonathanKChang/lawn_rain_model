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


# --- Weather resampler edge cases (E1-E2) ---


def test_empty_csv_returns_empty_list() -> None:
    """A CSV with only a header row should return an empty list of steps."""
    import tempfile, os
    csv_text = "entity_id,state,last_changed\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        tmp_path = f.name
    try:
        steps = resample_history(tmp_path, DEFAULT_SENSOR_MAP)
        assert steps == []
    finally:
        os.unlink(tmp_path)


def test_headers_only_returns_empty_list() -> None:
    """A file with headers but no data rows should return an empty list."""
    import tempfile, os
    csv_text = "entity_id,state,last_changed\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        tmp_path = f.name
    try:
        steps = resample_history(tmp_path, DEFAULT_SENSOR_MAP)
        assert len(steps) == 0
    finally:
        os.unlink(tmp_path)


def test_single_row_csv_produces_one_step() -> None:
    """A CSV with exactly one reading per entity should produce one WeatherStep."""
    import tempfile, os
    csv_text = (
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,45.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        tmp_path = f.name
    try:
        steps = resample_history(tmp_path, DEFAULT_SENSOR_MAP)
        assert len(steps) == 1
        assert steps[0].hour == 0
        assert steps[0].tod == 10
        assert steps[0].temp == 75.0
        assert steps[0].rh == 60.0
    finally:
        os.unlink(tmp_path)


def test_missing_sensor_entity_graceful() -> None:
    """If a required sensor entity is missing, the resampler should handle it gracefully."""
    import tempfile, os
    # CSV only has temp — missing rh, wind, clouds, elevation, accumulation
    csv_text = (
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        tmp_path = f.name
    try:
        steps = resample_history(tmp_path, DEFAULT_SENSOR_MAP)
        # Resampler produces one step but with NaN for missing sensors
        assert len(steps) == 1 and steps[0].rh != steps[0].rh
    finally:
        os.unlink(tmp_path)


def test_non_numeric_states_handled() -> None:
    """Non-numeric state values should be coerced/ignored without crashing."""
    import tempfile, os
    csv_text = (
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_temperature_0h,not_a_number,2026-04-24T10:30:00.000Z\n"
        "sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,45.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        tmp_path = f.name
    try:
        steps = resample_history(tmp_path, DEFAULT_SENSOR_MAP)
        # Should still produce valid steps (non-numeric row was dropped by coerce)
        for s in steps:
            assert s.temp == s.temp  # not NaN check
    finally:
        os.unlink(tmp_path)


def test_rain_accumulation_with_gaps() -> None:
    """Missing intermediate readings should still produce correct delta from last known."""
    import tempfile, os
    csv_text = (
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,45.0,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,35.0,2026-04-24T11:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        # No accumulation reading until hour 12 — gap in data
        "sensor.pirateweather_current_day_liquid_accumulation,0.4,2026-04-24T12:00:00.000Z\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        tmp_path = f.name
    try:
        steps = resample_history(tmp_path, DEFAULT_SENSOR_MAP)
        # Hour 10 and 11: accumulation was 0.0 at hour 10, so rain = 0.0 for those hours
        # (diff of same value or first bucket uses accumulation value which is 0.0)
        hour_10_step = next(s for s in steps if s.hour == 0)
        assert hour_10_step.rain_inches == 0.0
    finally:
        os.unlink(tmp_path)


def test_concurrent_same_hour_readings_last_wins() -> None:
    """Multiple readings within the same hour should use the last one (forward-fill)."""
    # The existing fixture history_simple.csv already covers this — it has readings at :00 and :30.
    # Additional explicit test: 3 readings in same hour.
    import tempfile, os
    csv_text = (
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,70.0,2026-04-24T10:05:00.000Z\n"
        "sensor.pirateweather_temperature_0h,73.0,2026-04-24T10:20:00.000Z\n"
        "sensor.pirateweather_temperature_0h,76.0,2026-04-24T10:55:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,45.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        tmp_path = f.name
    try:
        steps = resample_history(tmp_path, DEFAULT_SENSOR_MAP)
        assert len(steps) == 1
        # Last reading in the hour should be used (forward-fill last)
        assert steps[0].temp == 76.0, f"Expected temp=76.0 (last reading), got {steps[0].temp}"
    finally:
        os.unlink(tmp_path)
