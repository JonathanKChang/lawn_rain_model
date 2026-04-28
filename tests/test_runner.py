# tests/test_runner.py
from __future__ import annotations
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow
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
    assert len(rows) == s.duration_hours


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
        assert r["hour"] == i


def test_tod_wraps_correctly(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()  # start_hour=8
    rows = run_scenario(s, model, model.default_params)
    assert rows[0]["tod"] == 8
    assert rows[16]["tod"] == (8 + 16) % 24  # = 0


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
    h2m = hours_to_mow(rows, threshold=5.0)
    assert h2m is not None
    assert 10 <= h2m <= 20  # hot/dry with 1" rain at 8 AM start


def test_hours_to_mow_none_when_never_clears(model: SingleLayerModel) -> None:
    s = Scenario(
        name="never",
        duration_hours=3,
        rain_events=[RainEvent(hour=0, inches=2.5)],
        weather=WeatherConditions(temp=45, rh=95, wind=1, clouds=100),
        use_solar_model=False,
    )
    rows = run_scenario(s, model, model.default_params)
    assert hours_to_mow(rows, threshold=5.0) is None


def test_wetness_monotone_no_rain(model: SingleLayerModel) -> None:
    """Without rain after hour 0, wetness should be non-increasing."""
    s = _cool_overcast_scenario()
    rows = run_scenario(s, model, model.default_params)
    # Skip hour 0 (rain lands); from hour 1 onward wetness should not increase
    for i in range(1, len(rows) - 1):
        assert rows[i + 1]["wetness_out"] <= rows[i]["wetness_out"] + 1e-9
