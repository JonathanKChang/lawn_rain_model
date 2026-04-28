# lawn_rain_model/simulation/runner.py
"""Model-agnostic scenario runner."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from lawn_rain_model.models.protocol import LawnModel
from lawn_rain_model.calibration.scenarios import Scenario, WeatherConditions
from lawn_rain_model.simulation.weather import WeatherStep
from lawn_rain_model.simulation.solar import sun_elevation


def build_weather_steps(
    scenario: Scenario,
    base_path: Path | None = None,
) -> list[WeatherStep]:
    """
    Build the hourly WeatherStep list for a scenario.

    If scenario.history_file is set, resample the CSV.
    Otherwise, generate steps from scenario.weather + solar model.
    """
    if scenario.history_file:
        from lawn_rain_model.simulation.weather import resample_history, DEFAULT_SENSOR_MAP
        csv_path = Path(scenario.history_file)
        if base_path and not csv_path.is_absolute():
            csv_path = base_path / csv_path
        sensor_map = {**DEFAULT_SENSOR_MAP, **scenario.sensor_map}
        return resample_history(csv_path, sensor_map)
    else:
        assert scenario.weather is not None, (
            f"Scenario '{scenario.name}' has no history_file and no weather block."
        )
        w = scenario.weather
        rain_map = {e.hour: e.inches for e in scenario.rain_events}
        steps: list[WeatherStep] = []
        for h in range(scenario.duration_hours):
            tod = (scenario.start_hour + h) % 24
            elev = (
                sun_elevation(tod, scenario.day_of_year, scenario.latitude)
                if scenario.use_solar_model
                else w.elevation
            )
            steps.append(WeatherStep(
                hour=h, tod=tod,
                temp=w.temp, rh=w.rh, wind=w.wind, clouds=w.clouds,
                elevation=elev,
                rain_inches=rain_map.get(h, 0.0),
            ))
        return steps


def run_scenario(
    scenario: Scenario,
    model: LawnModel,
    params: dict[str, float],
    weather_steps: list[WeatherStep] | None = None,
) -> list[dict[str, Any]]:
    """
    Run a scenario for its full duration.

    weather_steps: pre-built list (from history resampler). If None, steps
                   are generated from scenario.weather + solar model.
    """
    if weather_steps is None:
        weather_steps = build_weather_steps(scenario)

    state = model.initial_state(scenario.initial_wetness)
    rows: list[dict[str, Any]] = []

    for ws in weather_steps:
        wetness_in  = model.surface_wetness(state)
        result      = model.step(state, ws, params)
        wetness_out = result["wetness_out"]

        rows.append({
            "hour":        ws.hour,
            "tod":         ws.tod,
            "elevation":   ws.elevation,
            "rain_inches": ws.rain_inches,
            "wetness_in":  wetness_in,
            "wetness_out": wetness_out,
            "drying_rate": result["drying_rate"],
            "can_mow":     wetness_out <= scenario.mow_threshold,
            "diagnostics": result["diagnostics"],
        })
        state = model.initial_state(wetness_out)

    return rows


def hours_to_mow(rows: list[dict[str, Any]], threshold: float) -> int | None:
    """Return the first hour where wetness_out ≤ threshold, or None."""
    for r in rows:
        if r["wetness_out"] <= threshold:
            return r["hour"]
    return None
