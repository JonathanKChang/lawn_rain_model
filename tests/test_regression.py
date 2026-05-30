"""Regression tests — catch bugs that have been discovered and fixed.

These tests ensure that previously-fixed bugs don't reappear. Each test
documents the bug scenario and verifies the correct behavior.
"""
from __future__ import annotations

import math
import tempfile
import os

import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow
from lawn_rain_model.calibration.scenarios import (
    Scenario, WeatherConditions, RainEvent,
)


@pytest.fixture
def m() -> SingleLayerModel:
    return SingleLayerModel()


# --- M1: Dry-start-then-rain first-mow-after-rain regression ---
# Bug: hours_to_mow returned 0 when lawn started dry then got wet from rain.
# Fix: introduced "became_wet" tracking to skip initial dry period.


def test_regression_dry_start_then_rain(m: SingleLayerModel) -> None:
    """First-mow-after-rain regression: lawn starts dry, gets rain,
    then dries back. hours_to_mow must NOT return hour 0."""
    s = Scenario(
        name="dry_then_wet",
        duration_hours=100,
        rain_events=[
            RainEvent(hour=0, inches=0.01),    # tiny, stays dry
            RainEvent(hour=13, inches=0.11),   # pushes wetness > 5
            RainEvent(hour=14, inches=0.21),
            RainEvent(hour=15, inches=0.17),
            RainEvent(hour=16, inches=0.06),
        ],
        weather=WeatherConditions(temp=70, rh=70, wind=5, clouds=40),
        initial_wetness=0.4,
        use_solar_model=False,
    )
    threshold = m.default_params["mow_threshold"]
    rows = run_scenario(s, m, m.default_params)
    h2m = hours_to_mow(rows, threshold, s.steps_per_hour)

    assert h2m is not None
    assert h2m > 0, "Bug: hours_to_mow returned 0 for dry-start-then-rain"
    # The lawn gets wet at hour 13, so h2m must be after hour 13
    assert h2m > 13, f"h2m={h2m} should be after rain at hour 13"


# --- M2: NaN rain values from missing accumulation readings ---
# Bug: when accumulation sensor stops reporting, rain became NaN.
# Fix: fillna(0.0) for remaining hours beyond last accumulation reading.


def test_regression_nan_rain_values(m: SingleLayerModel) -> None:
    """NaN rain regression: rain beyond last accumulation reading must not be NaN."""
    from lawn_rain_model.simulation.weather import resample_history, DEFAULT_SENSOR_MAP

    csv_text = (
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:00:00.000Z\n"
        "sensor.pirateweather_temperature_0h,73.0,2026-04-24T12:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.3,2026-04-24T10:30:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,61,2026-04-24T11:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,62,2026-04-24T12:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,40.0,2026-04-24T11:00:00.000Z\n"
        "sensor.sun_elevation,30.0,2026-04-24T12:00:00.000Z\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        csv_path = f.name

    try:
        steps = resample_history(csv_path, DEFAULT_SENSOR_MAP)
        for s in steps:
            assert s.rain_inches == s.rain_inches, (  # NaN check
                f"Hour {s.hour} has NaN rain"
            )
            assert s.rain_inches >= 0, (
                f"Hour {s.hour} negative rain: {s.rain_inches}"
            )
        total = sum(st.rain_inches for st in steps)
        assert total == total, "Total rain is NaN"
        assert total > 0, "Expected some rain from accumulation delta"
    finally:
        os.unlink(csv_path)


# --- M3: Wetness never exceeds 100 even with extreme rain ---


def test_regression_wetness_never_exceeds_100(m: SingleLayerModel) -> None:
    """Wetness regression: even with massive rain at max bounds,
    wetness must never exceed 100."""
    from lawn_rain_model.simulation.weather import WeatherStep

    params = m.default_params.copy()
    # Set rain_mult to maximum bound (70.0)
    params["rain_mult"] = 70.0

    ws = WeatherStep(
        hour=0, tod=12, temp=75.0, rh=60.0,
        wind=5.0, clouds=30.0, elevation=45.0,
        rain_inches=10.0,  # extreme rain
    )
    state = m.initial_state(0.0)
    result = m.step(state, ws, params)

    assert result["wetness_out"] <= 100.0, (
        f"Wetness exceeded 100 with extreme rain: {result['wetness_out']}"
    )
    # Verify no NaN
    assert math.isfinite(result["wetness_out"])


# --- M4: Capillary rate never goes negative at extreme cold ---


def test_regression_capillary_never_negative(m: SingleLayerModel) -> None:
    """Capillary regression: capillary_rate must never go negative,
    even at very low temperatures (viscosity correction should floor)."""
    from lawn_rain_model.simulation.weather import WeatherStep

    for temp in [-40, 0, 20, 38, 50, 70, 100]:
        ws = WeatherStep(
            hour=0, tod=12, temp=float(temp), rh=60.0,
            wind=5.0, clouds=30.0, elevation=45.0,
            rain_inches=0.0,
        )
        state = m.initial_state(30.0)
        result = m.step(state, ws, m.default_params)

        # Capillary sink should never be negative
        assert result["diagnostics"]["capillary_sink"] >= 0, (
            f"Capillary sink negative at temp={temp}°F: {result['diagnostics']['capillary_sink']}"
        )
        # Viscosity factor: no upper cap in the model — it increases above 1.0
        # when temp > 70°F (thinner water). Only lower bound is visc_floor.
        visc = result["diagnostics"]["visc_factor"]
        assert m.default_params["visc_floor"] <= visc, (
            f"Viscosity factor below floor at temp={temp}°F: {visc}"
        )


# --- M5: Sub-step rain only applies to first sub-step ---


def test_regression_rain_only_first_substep(m: SingleLayerModel) -> None:
    """Rain regression: rain must only apply to sub_step=0 of the target hour."""
    from lawn_rain_model.simulation.runner import build_weather_steps

    s = Scenario(
        name="rain_check",
        duration_hours=4,
        rain_events=[RainEvent(hour=2, inches=1.0)],
        weather=WeatherConditions(temp=75.0, rh=60.0, wind=5.0, clouds=30.0),
        use_solar_model=False,
        start_hour=12,
        day_of_year=172,
        latitude=39.0,
        time_step_minutes=15,  # 4 sub-steps per hour
    )
    steps = build_weather_steps(s)
    sph = s.steps_per_hour

    # Hour 2 rain should only be at sub_step=0
    hour2_start = sph * 2
    assert steps[hour2_start].rain_inches == 1.0
    for ss in range(1, sph):
        assert steps[hour2_start + ss].rain_inches == 0.0, (
            f"Rain at sub_step {ss} of hour 2: {steps[hour2_start + ss].rain_inches}"
        )
    # Other hours should have zero rain
    for idx in range(len(steps)):
        hour = idx // sph
        if hour != 2:
            assert steps[idx].rain_inches == 0.0, (
                f"Rain at hour {hour}, sub_step {idx % sph}: {steps[idx].rain_inches}"
            )


# --- M6: Stop-after-mow invariant ---


def test_regression_stop_after_mow_invariant(m: SingleLayerModel) -> None:
    """Stop-after-mow regression: truncated run's last row must be at or below threshold,
    and all preceding rows should show the lawn was wet first."""
    s = Scenario(
        name="mow_test",
        duration_hours=48,
        rain_events=[RainEvent(hour=0, inches=1.0)],
        weather=WeatherConditions(temp=85, rh=30, wind=10, clouds=10),
        use_solar_model=False,
        start_hour=8,
        day_of_year=172,
        latitude=39.0,
    )
    threshold = m.default_params["mow_threshold"]

    truncated = run_scenario(s, m, m.default_params, stop_after_mow=True)
    assert len(truncated) > 0
    # Last row should be at or below threshold
    assert truncated[-1]["wetness_out"] <= threshold, (
        f"Last wetness {truncated[-1]['wetness_out']} > threshold {threshold}"
    )
    # At least one preceding row should be above threshold
    has_wet = any(r["wetness_out"] > threshold for r in truncated)
    assert has_wet, "Truncated run should include the wet period"


# --- M7: Sub-step row count matches expected ---


def test_regression_substep_row_count(m: SingleLayerModel) -> None:
    """Sub-step regression: total rows must equal duration_hours * steps_per_hour."""
    for time_step in [5, 10, 15, 20, 30, 60]:
        s = Scenario(
            name=f"count_{time_step}",
            duration_hours=4,
            rain_events=[RainEvent(hour=0, inches=1.0)],
            weather=WeatherConditions(temp=75.0, rh=60.0, wind=5.0, clouds=30.0),
            use_solar_model=False,
            start_hour=12,
            day_of_year=172,
            latitude=39.0,
            time_step_minutes=time_step,
        )
        rows = run_scenario(s, m, m.default_params)
        expected = s.duration_hours * s.steps_per_hour
        assert len(rows) == expected, (
            f"time_step={time_step}: got {len(rows)} rows, expected {expected}"
        )


# --- M8: Wetness monotonicity without rain after hour 0 ---


def test_regression_wetness_monotone_no_rain(m: SingleLayerModel) -> None:
    """Without rain after hour 0, wetness should be non-increasing across sub-steps."""
    s = Scenario(
        name="monotone",
        duration_hours=48,
        rain_events=[RainEvent(hour=0, inches=1.0)],
        weather=WeatherConditions(temp=50, rh=80, wind=3, clouds=90),
        use_solar_model=False,
        start_hour=8,
        day_of_year=172,
        latitude=39.0,
    )
    rows = run_scenario(s, m, m.default_params)
    sph = s.steps_per_hour

    # Skip hour 0 (rain lands at sub_step=0); from there wetness should not increase
    for i in range(sph, len(rows) - 1):
        assert rows[i + 1]["wetness_out"] <= rows[i]["wetness_out"] + 1e-9, (
            f"Wetness increased at row {i}: {rows[i]['wetness_out']} → {rows[i+1]['wetness_out']}"
        )


# --- M9: Pool drain is zero below pool threshold ---


def test_regression_pool_drain_zero_below_thresh(m: SingleLayerModel) -> None:
    """Pool drain regression: no pool drainage should occur below pool_thresh."""
    from lawn_rain_model.simulation.weather import WeatherStep

    params = m.default_params
    pool_thresh = params["pool_thresh"]  # default 40.0

    for wetness in [0.0, 10.0, 25.0, 39.9]:
        ws = WeatherStep(
            hour=0, tod=12, temp=75.0, rh=60.0,
            wind=5.0, clouds=30.0, elevation=45.0, rain_inches=0.0,
        )
        state = m.initial_state(wetness)
        result = m.step(state, ws, params)

        assert result["diagnostics"]["pool_drain_rate"] == 0.0, (
            f"Pool drain {result['diagnostics']['pool_drain_rate']} at wetness={wetness} "
            f"(below pool_thresh={pool_thresh})"
        )


# --- M10: Pre-dry calculation uses pre-rain wetness + rain input ---


def test_regression_pre_dry_calculation(m: SingleLayerModel) -> None:
    """Pre-dry regression: pre_dry = min(wetness + rain * rain_mult, 100)."""
    from lawn_rain_model.simulation.weather import WeatherStep

    params = m.default_params
    ws = WeatherStep(
        hour=0, tod=12, temp=75.0, rh=60.0,
        wind=5.0, clouds=30.0, elevation=45.0,
        rain_inches=1.0,
    )

    for wetness_in in [0.0, 10.0, 20.0]:
        state = m.initial_state(wetness_in)
        result = m.step(state, ws, params)
        expected_pre = min(wetness_in + 1.0 * params["rain_mult"], 100.0)
        assert abs(result["diagnostics"]["pre_dry"] - expected_pre) < 1e-6, (
            f"pre_dry mismatch: wetness={wetness_in}, got {result['diagnostics']['pre_dry']}, "
            f"expected {expected_pre}"
        )
