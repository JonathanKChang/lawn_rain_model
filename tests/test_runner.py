# tests/test_runner.py
from __future__ import annotations
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.runner import (
    run_scenario,
    hours_to_mow,
    _expand_to_substeps,
)
from lawn_rain_model.calibration.scenarios import (
    Scenario, WeatherConditions, RainEvent,
)


def _hot_dry_scenario() -> Scenario:
    return Scenario(
        name="test_hot_dry",
        duration_hours=48,
        rain_events=[RainEvent(hour=0, inches=1.0)],
        weather=WeatherConditions(temp=85, rh=30, wind=10, clouds=10),
        use_solar_model=True,
        start_hour=8,
        day_of_year=172,
        latitude=39.0,
    )


def _cool_overcast_scenario() -> Scenario:
    return Scenario(
        name="test_cool",
        duration_hours=96,
        rain_events=[RainEvent(hour=0, inches=1.0)],
        weather=WeatherConditions(temp=50, rh=80, wind=3, clouds=90),
        use_solar_model=True,
        start_hour=8,
        day_of_year=172,
        latitude=39.0,
    )


@pytest.fixture
def model() -> SingleLayerModel:
    return SingleLayerModel()


def test_output_length(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    assert len(rows) == s.duration_hours * s.steps_per_hour


def test_first_hour_rain(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    assert rows[0]["rain_inches"] == 1.0


def test_non_rain_hours_zero(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    for r in rows[1:]:
        assert r["rain_inches"] == 0.0


def test_hour_sequence(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    for i, r in enumerate(rows):
        assert r["hour"] == i // s.steps_per_hour
        assert r["sub_step"] == i % s.steps_per_hour


def test_tod_wraps_correctly(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()  # start_hour=8
    rows = run_scenario(s, model, model.default_params)
    # TOD is constant within each hour (from the hour's clock time)
    assert rows[0]["tod"] == 8
    # Row 16 is sub_step 0 of hour 4, tod = (8+4)%24 = 12
    assert rows[16]["tod"] == (8 + 16 // s.steps_per_hour) % 24


def test_can_mow_uses_threshold(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    threshold = model.default_params["mow_threshold"]
    for r in rows:
        assert r["can_mow"] == (r["wetness_out"] <= threshold)


def test_required_row_keys(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    required = {"hour", "tod", "can_mow", "elevation", "rain_inches",
                "wetness_in", "wetness_out", "drying_rate", "diagnostics"}
    assert required.issubset(rows[0].keys())


def test_hot_dry_hits_calib_target(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    h2m = hours_to_mow(rows, threshold=5.0, steps_per_hour=s.steps_per_hour)
    assert h2m is not None
    # With 15-min resolution, drying is more granular; expect ~10-25h
    assert 8 <= h2m <= 25  # hot/dry with 1" rain at 8 AM start


def test_hours_to_mow_none_when_never_clears(model: SingleLayerModel) -> None:
    s = Scenario(
        name="never",
        duration_hours=3,
        rain_events=[RainEvent(hour=0, inches=2.5)],
        weather=WeatherConditions(temp=45, rh=95, wind=1, clouds=100),
        use_solar_model=False,
    )
    rows = run_scenario(s, model, model.default_params)
    assert hours_to_mow(rows, threshold=5.0, steps_per_hour=s.steps_per_hour) is None


def test_wetness_monotone_no_rain(model: SingleLayerModel) -> None:
    """Without rain after hour 0, wetness should be non-increasing."""
    s = _cool_overcast_scenario()
    rows = run_scenario(s, model, model.default_params)
    # Skip hour 0 (rain lands at sub_step 0); from hour 1 onward wetness
    # should not increase across sub-steps (no rain after hour 0)
    for i in range(s.steps_per_hour, len(rows) - 1):
        assert rows[i + 1]["wetness_out"] <= rows[i]["wetness_out"] + 1e-9


# ---------------------------------------------------------------------------
# Bug-fix tests: first-mow-after-rain, stop_after_mow, NaN rain
# ---------------------------------------------------------------------------


def _dry_start_then_rain_scenario() -> Scenario:
    """
    Simulates a CSV that starts dry (wetness 0.4, below threshold) with
    tiny rain, then delivers a big rain burst at hour 13 that pushes
    wetness well above threshold, then the lawn dries back down.
    """
    # We build a scenario with weather-backed rain events that mimic
    # the 2026-04-05 CSV pattern: dry start, big rain at hour 13.
    return Scenario(
        name="dry_then_wet",
        duration_hours=100,
        rain_events=[
            RainEvent(hour=0, inches=0.01),   # tiny, wetness stays low
            RainEvent(hour=13, inches=0.11),  # big rain → wetness > 5
            RainEvent(hour=14, inches=0.21),
            RainEvent(hour=15, inches=0.17),
            RainEvent(hour=16, inches=0.06),
        ],
        weather=WeatherConditions(temp=70, rh=70, wind=5, clouds=40),
        initial_wetness=0.4,
        use_solar_model=False,
    )


def test_hours_to_mow_skips_initial_dry_period(model: SingleLayerModel) -> None:
    """hours_to_mow must NOT return hour 0 when the lawn starts dry."""
    s = _dry_start_then_rain_scenario()
    rows = run_scenario(s, model, model.default_params)
    threshold = model.default_params["mow_threshold"]

    # Hour 0 is already below threshold → should NOT be the first mow
    assert rows[0]["wetness_out"] <= threshold

    h2m = hours_to_mow(rows, threshold, s.steps_per_hour)
    assert h2m is not None
    assert h2m > 0, (
        f"hours_to_mow returned {h2m} but should skip the initial dry period"
    )
    # The lawn gets wet at hour 13 (wetness > 5), then dries back down
    # somewhere after hour 20.  h2m should be after hour 13.
    assert h2m > 13


def test_hours_to_mow_returns_none_when_never_wet(model: SingleLayerModel) -> None:
    """If wetness never exceeds threshold, hours_to_mow returns None."""
    s = Scenario(
        name="always_dry",
        duration_hours=24,
        rain_events=[RainEvent(hour=0, inches=0.01)],
        weather=WeatherConditions(temp=85, rh=20, wind=10, clouds=5),
        initial_wetness=0.1,
        use_solar_model=True,
    )
    rows = run_scenario(s, model, model.default_params)
    # Wetness never exceeds 5
    assert all(r["wetness_out"] <= 5.0 for r in rows)
    assert hours_to_mow(rows, 5.0) is None


def test_stop_after_mow_truncates_rows(model: SingleLayerModel) -> None:
    """stop_after_mow=True should stop at first post-rain mow."""
    s = _dry_start_then_rain_scenario()
    # Full run
    full_rows = run_scenario(s, model, model.default_params)
    # Truncated run
    truncated_rows = run_scenario(
        s, model, model.default_params, stop_after_mow=True,
    )

    # Truncated should be shorter
    assert len(truncated_rows) < len(full_rows)

    # Last row of truncated should be a can_mow row
    assert truncated_rows[-1]["can_mow"]

    # All rows in truncated should be <= last hour in truncated
    max_hour = truncated_rows[-1]["hour"]
    for r in truncated_rows:
        assert r["hour"] <= max_hour

    # The truncated result should NOT contain the big rain hours
    # (hours 14-16) if the lawn dries before them — but in this scenario
    # the lawn gets wet at hour 13 and dries back down after hour 20,
    # so the truncated rows should include hours 0..mow_hour.
    threshold = model.default_params["mow_threshold"]
    # There should be at least one row where wetness > threshold (the wet period)
    has_wet = any(r["wetness_out"] > threshold for r in truncated_rows)
    assert has_wet, "Truncated rows should include the wet period before mow"


def test_nan_rain_values_filled_in_resampler() -> None:
    """Rain values beyond the last accumulation reading must not be NaN."""
    from pathlib import Path
    import textwrap
    from lawn_rain_model.simulation.weather import resample_history, DEFAULT_SENSOR_MAP

    csv_text = textwrap.dedent("""\
        entity_id,state,last_changed
        sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z
        sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:00:00.000Z
        sensor.pirateweather_temperature_0h,73.0,2026-04-24T12:00:00.000Z
        sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z
        sensor.pirateweather_current_day_liquid_accumulation,0.3,2026-04-24T10:30:00.000Z
        sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z
        sensor.pirateweather_humidity_0h,61,2026-04-24T11:00:00.000Z
        sensor.pirateweather_humidity_0h,62,2026-04-24T12:00:00.000Z
        sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z
        sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z
        sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z
        sensor.sun_elevation,40.0,2026-04-24T11:00:00.000Z
        sensor.sun_elevation,30.0,2026-04-24T12:00:00.000Z
    """)

    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        csv_path = f.name

    try:
        steps = resample_history(csv_path, DEFAULT_SENSOR_MAP)
        # All rain values must be valid numbers (no NaN)
        for s in steps:
            assert s.rain_inches == s.rain_inches, (
                f"Hour {s.hour} has NaN rain_inches"
            )
            assert s.rain_inches >= 0, (
                f"Hour {s.hour} has negative rain_inches: {s.rain_inches}"
            )
        # Total rain must not be NaN
        total = sum(st.rain_inches for st in steps)
        assert total == total, "Total rain is NaN"
        assert total > 0, "Expected some rain from the accumulation delta"
    finally:
        os.unlink(csv_path)


# ---------------------------------------------------------------------------
# Phase F: Scenario Runner edge cases
# ---------------------------------------------------------------------------


def test_interpolation_correctness():
    """Weather interpolation between two different hours should be exact linear."""
    from lawn_rain_model.simulation.runner import build_weather_steps
    from lawn_rain_model.calibration.scenarios import (
        Scenario, WeatherConditions, RainEvent,
    )

    # Create a scenario with varying weather (temp changes each hour)
    s = Scenario(
        name="interp_test",
        duration_hours=2,
        rain_events=[],
        weather=None,  # will be overridden per-hour in build_weather_steps
        use_solar_model=False,
        start_hour=12,
        day_of_year=172,
        latitude=39.0,
        time_step_minutes=15,  # 4 sub-steps per hour
    )

    # Manually build weather steps with known varying values
    from lawn_rain_model.simulation.weather import WeatherStep

    hourly_steps = [
        WeatherStep(hour=0, tod=12, temp=60.0, rh=80.0, wind=2.0, clouds=90.0,
                    elevation=30.0, rain_inches=0.0),
        WeatherStep(hour=1, tod=13, temp=80.0, rh=40.0, wind=10.0, clouds=10.0,
                    elevation=60.0, rain_inches=0.0),
    ]
    from lawn_rain_model.simulation.runner import InterpolationMode

    steps = _expand_to_substeps(
        hourly_steps, s,
        interpolation=InterpolationMode.LINEAR,
    )
    sph = s.steps_per_hour  # = 4

    # Hour 0 sub_step=2 (fraction=0.5): temp should interpolate from 60→80
    # at fraction 0.5: 60*0.5 + 80*0.5 = 70
    step_2 = steps[2]
    assert step_2.temp == pytest.approx(70.0, abs=1e-9)
    assert step_2.rh == pytest.approx(60.0, abs=1e-9)
    assert step_2.wind == pytest.approx(6.0, abs=1e-9)


def test_zero_duration_scenario():
    """A scenario with duration=0 should produce zero rows."""
    s = Scenario(
        name="zero_dur",
        duration_hours=0,
        rain_events=[],
        weather=WeatherConditions(temp=75.0, rh=60.0, wind=5.0, clouds=30.0),
        use_solar_model=False,
        start_hour=12,
        day_of_year=172,
        latitude=39.0,
    )
    rows = run_scenario(s, SingleLayerModel(), SingleLayerModel().default_params)
    assert len(rows) == 0


def test_single_hour_scenario():
    """A scenario with duration=1 should produce exactly steps_per_hour rows."""
    s = Scenario(
        name="one_hour",
        duration_hours=1,
        rain_events=[RainEvent(hour=0, inches=0.5)],
        weather=WeatherConditions(temp=75.0, rh=60.0, wind=5.0, clouds=30.0),
        use_solar_model=False,
        start_hour=12,
        day_of_year=172,
        latitude=39.0,
        time_step_minutes=15,  # 4 sub-steps
    )
    model = SingleLayerModel()
    rows = run_scenario(s, model, model.default_params)
    assert len(rows) == s.steps_per_hour  # = 4
    # First row should have the rain
    assert rows[0]["rain_inches"] == 0.5
    # Remaining sub-steps in hour 0 should have no rain
    for r in rows[1:]:
        assert r["rain_inches"] == 0.0


def test_row_ordering_by_hour_substep():
    """Rows must be strictly ordered by (hour, sub_step) tuple."""
    s = _hot_dry_scenario()
    rows = run_scenario(s, SingleLayerModel(), SingleLayerModel().default_params)
    for i in range(len(rows) - 1):
        cur_hour = rows[i]["hour"]
        cur_ss = rows[i]["sub_step"]
        nxt_hour = rows[i + 1]["hour"]
        nxt_ss = rows[i + 1]["sub_step"]
        assert (cur_hour, cur_ss) < (nxt_hour, nxt_ss), (
            f"Row order violated at index {i}: ({cur_hour},{cur_ss}) not < ({nxt_hour},{nxt_ss})"
        )


def test_multiple_rain_events_same_hour():
    """Multiple RainEvents for the same hour: last one wins (dict comprehension behavior)."""
    from lawn_rain_model.calibration.scenarios import (
        Scenario, WeatherConditions, RainEvent,
    )

    s = Scenario(
        name="multi_rain",
        duration_hours=2,
        rain_events=[RainEvent(hour=0, inches=1.0), RainEvent(hour=0, inches=2.0)],
        weather=WeatherConditions(temp=75.0, rh=60.0, wind=5.0, clouds=30.0),
        use_solar_model=False,
        start_hour=12,
        day_of_year=172,
        latitude=39.0,
    )
    rows = run_scenario(s, SingleLayerModel(), SingleLayerModel().default_params)
    # Hour 0 sub_step=0 has rain_inches from the LAST event (dict comprehension: 2.0)
    assert rows[0]["rain_inches"] == 2.0
