# tests/test_substeps.py
"""Tests for sub-step time resolution behavior."""
from __future__ import annotations
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow, build_weather_steps
from lawn_rain_model.calibration.scenarios import (
    Scenario, WeatherConditions, RainEvent,
)


@pytest.fixture
def model() -> SingleLayerModel:
    return SingleLayerModel()


def _substep_scenario(
    duration_hours: int = 4,
    rain_inches: float = 1.0,
    rain_hour: int = 0,
    time_step_minutes: int = 15,
) -> Scenario:
    """Create a simple scenario for sub-step testing."""
    return Scenario(
        name="substep_test",
        duration_hours=duration_hours,
        rain_events=[RainEvent(hour=rain_hour, inches=rain_inches)],
        weather=WeatherConditions(temp=75, rh=60, wind=5, clouds=30),
        use_solar_model=False,
        start_hour=12,
        day_of_year=172,
        latitude=39.0,
        time_step_minutes=time_step_minutes,
    )


class TestSubStepInterpolation:
    """Test weather interpolation for weather-backed scenarios."""

    def test_interpolation_weather_backed(self) -> None:
        """Weather values should interpolate between hours for weather-backed scenarios."""
        s = Scenario(
            name="interp_test",
            duration_hours=2,
            rain_events=[],
            weather=WeatherConditions(temp=70, rh=60, wind=5, clouds=30),
            use_solar_model=False,
            start_hour=12,
            day_of_year=172,
            latitude=39.0,
            time_step_minutes=15,
        )
        steps = build_weather_steps(s)
        sph = s.steps_per_hour  # = 4

        # Hour 0 should have temp=70 (constant for weather-backed)
        # Hour 1 should have temp=70 (constant for weather-backed)
        # With constant weather, interpolation doesn't change values
        for step in steps:
            assert step.temp == 70.0
            assert step.rh == 60.0
            assert step.wind == 5.0
            assert step.clouds == 30.0

    def test_sub_step_count(self) -> None:
        """Should generate correct number of sub-steps."""
        s = _substep_scenario(duration_hours=4, time_step_minutes=15)
        steps = build_weather_steps(s)
        assert len(steps) == 4 * s.steps_per_hour  # 4 hours * 4 steps/hour = 16


class TestRainAtFirstSubStep:
    """Test that rain applies only to the first sub-step of each hour."""

    def test_rain_only_first_sub_step(self) -> None:
        """Rain should only appear at sub_step=0 of the target hour."""
        s = _substep_scenario(duration_hours=4, rain_hour=2, time_step_minutes=15)
        steps = build_weather_steps(s)
        sph = s.steps_per_hour

        # Hours 0 and 1: no rain
        for i in range(sph * 2):
            assert steps[i].rain_inches == 0.0

        # Hour 2: rain only at sub_step=0
        hour2_start = sph * 2
        assert steps[hour2_start].rain_inches == 1.0  # sub_step=0
        for ss in range(1, sph):
            assert steps[hour2_start + ss].rain_inches == 0.0  # sub_steps 1,2,3

        # Hour 3: no rain
        for i in range(sph * 3, sph * 4):
            assert steps[i].rain_inches == 0.0

    def test_rain_at_hour_zero(self) -> None:
        """Rain at hour 0 should only be at sub_step=0."""
        s = _substep_scenario(duration_hours=2, rain_hour=0, time_step_minutes=15)
        steps = build_weather_steps(s)
        assert steps[0].rain_inches == 1.0
        for ss in range(1, s.steps_per_hour):
            assert steps[ss].rain_inches == 0.0


class TestHoursToMowWithSubSteps:
    """Test hours_to_mow with sub-step rows."""

    def test_hours_to_mow_returns_correct_hour(self) -> None:
        """hours_to_mow should return the correct hour index with sub-steps."""
        s = _substep_scenario(duration_hours=48, rain_inches=1.0, time_step_minutes=15)
        rows = run_scenario(s, model=SingleLayerModel(),
                           params=SingleLayerModel().default_params)
        sph = s.steps_per_hour
        h2m = hours_to_mow(rows, threshold=5.0, steps_per_hour=sph)

        assert h2m is not None
        # The returned hour should be an integer (not a sub-step index)
        assert isinstance(h2m, int)
        # It should be less than duration_hours
        assert h2m < s.duration_hours

    def test_hours_to_mow_with_different_step_sizes(self) -> None:
        """hours_to_mow should work with different step sizes."""
        for time_step in [5, 10, 15, 20, 30, 60]:
            s = _substep_scenario(duration_hours=4, time_step_minutes=time_step)
            rows = run_scenario(
                s, SingleLayerModel(), SingleLayerModel().default_params
            )
            sph = s.steps_per_hour
            h2m = hours_to_mow(rows, threshold=5.0, steps_per_hour=sph)
            # Should return a valid hour or None
            assert h2m is None or isinstance(h2m, int)


class TestDryingRateScaling:
    """Test that drying rate scaling is consistent across step sizes."""

    def test_drying_rate_scaled_by_steps_per_hour(self) -> None:
        """Drying rate per sub-step should be hourly_rate / steps_per_hour."""
        model = SingleLayerModel()
        p = model.default_params

        # Create a WeatherStep with steps_per_hour=4
        from lawn_rain_model.simulation.weather import WeatherStep
        ws_4step = WeatherStep(
            hour=0, sub_step=0, steps_per_hour=4,
            tod=12, temp=75, rh=60, wind=5, clouds=30,
            elevation=45, rain_inches=0.0,
        )
        # Create a WeatherStep with steps_per_hour=1 (hourly)
        ws_1step = WeatherStep(
            hour=0, sub_step=0, steps_per_hour=1,
            tod=12, temp=75, rh=60, wind=5, clouds=30,
            elevation=45, rain_inches=0.0,
        )

        state = model.initial_state(30.0)

        result_4step = model.step(state, ws_4step, p)
        result_1step = model.step(state, ws_1step, p)

        # The unscaled drying_rate should be the same
        assert result_4step["drying_rate"] == result_1step["drying_rate"]

        # The wetness_out with 4 steps should be higher (less drying per step)
        assert result_4step["wetness_out"] > result_1step["wetness_out"]

        # The difference should be approximately drying_rate * (1 - 1/4)
        expected_diff = result_1step["drying_rate"] * (1 - 1/4)
        actual_diff = result_4step["wetness_out"] - result_1step["wetness_out"]
        assert abs(actual_diff - expected_diff) < 0.01
