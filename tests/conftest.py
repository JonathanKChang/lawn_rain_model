# tests/conftest.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
import textwrap

import pytest
from lawn_rain_model.calibration.scenarios import (
    Scenario,
    WeatherConditions,
    RainEvent,
    CalibrationTarget,
)
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.weather import WeatherStep


@pytest.fixture
def model() -> SingleLayerModel:
    return SingleLayerModel()


@pytest.fixture
def default_params(model: SingleLayerModel) -> dict[str, float]:
    return model.default_params


@pytest.fixture
def dry_step() -> WeatherStep:
    return WeatherStep(
        hour=0, tod=12, temp=75.0, rh=60.0,
        wind=5.0, clouds=30.0, elevation=45.0, rain_inches=0.0,
    )


@pytest.fixture
def rainy_step() -> WeatherStep:
    return WeatherStep(
        hour=0, tod=12, temp=70.0, rh=80.0,
        wind=3.0, clouds=70.0, elevation=30.0, rain_inches=1.0,
    )


@pytest.fixture
def hot_dry_step() -> WeatherStep:
    """Fastest-drying condition: hot, low humidity, high wind, clear sky."""
    return WeatherStep(
        hour=0, tod=12, temp=85.0, rh=30.0,
        wind=10.0, clouds=10.0, elevation=60.0, rain_inches=0.0,
    )


@pytest.fixture
def cold_wet_step() -> WeatherStep:
    """Slowest-drying condition: cold, high humidity, no wind, overcast."""
    return WeatherStep(
        hour=0, tod=3, temp=38.0, rh=95.0,
        wind=1.0, clouds=100.0, elevation=-10.0, rain_inches=0.0,
    )


# ---------------------------------------------------------------------------
# Factory helpers for creating Scenario objects and test CSVs
# ---------------------------------------------------------------------------

_DEFAULT_WEATHER = WeatherConditions(temp=75.0, rh=60.0, wind=5.0, clouds=30.0)


def make_scenario(**overrides: Any) -> Scenario:
    """Create a Scenario with sensible defaults that can be selectively overridden.

    Defaults (match typical calibration scenario):
        duration_hours=48, 1.0" rain at hour=0, warm weather,
        solar model, start_hour=8, day=172, lat=39.0, 15-min steps.
    """
    kwargs: dict[str, Any] = dict(
        name=overrides.pop("name", "test_scenario"),
        duration_hours=overrides.pop("duration_hours", 48),
        rain_events=overrides.pop(
            "rain_events",
            [RainEvent(hour=0, inches=1.0)],
        ),
        weather=overrides.pop("weather", _DEFAULT_WEATHER),
        initial_wetness=overrides.pop("initial_wetness", 0.0),
        use_solar_model=overrides.pop("use_solar_model", True),
        start_hour=overrides.pop("start_hour", 8),
        day_of_year=overrides.pop("day_of_year", 172),
        latitude=overrides.pop("latitude", 39.0),
        time_step_minutes=overrides.pop("time_step_minutes", 15),
        calibration=overrides.pop("calibration", None),
        history_file=overrides.pop("history_file", None),
        sensor_map=overrides.pop("sensor_map", {}),
    )
    return Scenario(**kwargs)


@pytest.fixture
def make_history_csv(tmp_path: Path):
    """Factory fixture that generates a valid HA-history CSV.

    Usage:
        csv_path = make_history_csv(hours=24, rain_hour=5, rain_inches=0.5)
        # Returns Path to the generated CSV file.
    """
    def _make(
        hours: int = 24,
        rain_hour: Optional[int] = None,
        rain_inches: float = 0.0,
        temp: float = 75.0,
        rh: float = 60.0,
        wind: float = 5.0,
        clouds: float = 30.0,
        start_hour: int = 0,
    ) -> Path:
        lines: list[str] = [
            "entity_id,state,last_changed",
        ]
        for h in range(hours):
            ts = f"2026-04-24T{(start_hour + h) % 24:02d}:00:00.000Z"
            lines.append(f"sensor.pirateweather_temperature_0h,{temp},{ts}")
            lines.append(f"sensor.pirateweather_humidity_0h,{rh},{ts}")
            lines.append(f"sensor.pirateweather_wind_speed,{wind},{ts}")
            lines.append(f"sensor.pirateweather_cloud_coverage,{clouds},{ts}")
            # Sun elevation: positive 6-18, negative otherwise
            tod = (start_hour + h) % 24
            elev = max(0.0, 50.0 * (1.0 - abs(tod - 12) / 6.0)) if 6 <= tod <= 18 else 0.0
            lines.append(f"sensor.sun_elevation,{elev:.1f},{ts}")
            # Rain accumulation
            accum = rain_inches if rain_hour is not None and h >= rain_hour else 0.0
            lines.append(f"sensor.pirateweather_current_day_liquid_accumulation,{accum},{ts}")
        csv_path = tmp_path / "history.csv"
        csv_path.write_text("\n".join(lines) + "\n")
        return csv_path
    return _make
