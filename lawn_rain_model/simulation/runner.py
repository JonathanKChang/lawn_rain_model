# lawn_rain_model/simulation/runner.py
"""Model-agnostic scenario runner."""
from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Any

from lawn_rain_model.models.protocol import LawnModel
from lawn_rain_model.calibration.scenarios import Scenario, WeatherConditions
from lawn_rain_model.simulation.weather import WeatherStep
from lawn_rain_model.simulation.solar import sun_elevation


class InterpolationMode(Enum):
    """How weather values are interpolated between consecutive hours."""

    LINEAR = "linear"           # Linear interpolation (weather-backed)
    FORWARD_FILL = "ffill"      # Last observation carried forward (CSV)


def _expand_to_substeps(
    hourly_steps: list[WeatherStep],
    scenario: Scenario,
    interpolation: InterpolationMode = InterpolationMode.LINEAR,
) -> list[WeatherStep]:
    """
    Expand a list of hourly WeatherStep objects into sub-steps.

    For weather-backed scenarios (INTERPOLATION=LINEAR), linearly interpolate
    weather values between consecutive hours across sub-steps.

    For history CSV scenarios (INTERPOLATION=FORWARD_FILL), keep weather values
    constant (forward-filled) across all sub-steps within the hour.

    Rain events apply only to the first sub-step (sub_step=0).
    """
    sph = scenario.steps_per_hour
    if sph == 1:
        return hourly_steps

    steps: list[WeatherStep] = []
    for idx, h_step in enumerate(hourly_steps):
        for ss in range(sph):
            rain = h_step.rain_inches if ss == 0 else 0.0
            fraction = ss / sph

            # Get next hour's weather for interpolation
            has_next = (idx + 1 < len(hourly_steps))
            n_step = hourly_steps[idx + 1] if has_next else None

            if interpolation == InterpolationMode.FORWARD_FILL or not has_next:
                # Forward-fill: use current hour's values for all sub-steps
                temp = h_step.temp
                rh = h_step.rh
                wind = h_step.wind
                clouds = h_step.clouds
                elevation = h_step.elevation
            else:
                # Linear interpolation between current and next hour
                assert n_step is not None  # mypy needs this
                temp = h_step.temp * (1 - fraction) + n_step.temp * fraction
                rh = h_step.rh * (1 - fraction) + n_step.rh * fraction
                wind = h_step.wind * (1 - fraction) + n_step.wind * fraction
                clouds = h_step.clouds * (1 - fraction) + n_step.clouds * fraction
                elevation = h_step.elevation * (1 - fraction) + n_step.elevation * fraction

            steps.append(WeatherStep(
                hour=h_step.hour,
                sub_step=ss,
                steps_per_hour=sph,
                tod=h_step.tod,
                temp=temp,
                rh=rh,
                wind=wind,
                clouds=clouds,
                elevation=elevation,
                rain_inches=rain,
            ))
    return steps


def build_weather_steps(
    scenario: Scenario,
) -> list[WeatherStep]:
    """
    Build the WeatherStep list for a scenario.

    For sub-hourly resolution, each clock hour is expanded into
    ``steps_per_hour`` sub-steps with linearly interpolated weather
    (weather-backed) or forward-filled values (history CSV).

    Rain events apply only to the first sub-step (sub_step=0) of
    their target hour.

    If scenario.history_file is set, resample the CSV and expand to
    sub-steps with forward-fill.
    Otherwise, generate sub-steps from scenario.weather + solar model
    with linear interpolation between consecutive hours.
    """
    if scenario.history_file is None and scenario.duration_hours <= 0:
        raise ValueError(
            f"Scenario '{scenario.name}': duration_hours must be positive, "
            f"got {scenario.duration_hours}."
        )

    if scenario.history_file:
        from lawn_rain_model.simulation.weather import resample_history, DEFAULT_SENSOR_MAP
        csv_path = Path(scenario.history_file)
        sensor_map = {**DEFAULT_SENSOR_MAP, **scenario.sensor_map}
        hourly_steps = resample_history(csv_path, sensor_map)
        return _expand_to_substeps(hourly_steps, scenario,
                                   interpolation=InterpolationMode.FORWARD_FILL)
    else:
        assert scenario.weather is not None, (
            f"Scenario '{scenario.name}' has no history_file and no weather block."
        )
        w = scenario.weather
        rain_map = {e.hour: e.inches for e in scenario.rain_events}
        weather_steps: list[WeatherStep] = []
        for h in range(scenario.duration_hours):
            tod = (scenario.start_hour + h) % 24
            elev = (
                sun_elevation(tod, scenario.day_of_year, scenario.latitude)
                if scenario.use_solar_model
                else w.elevation
            )
            weather_steps.append(WeatherStep(
                hour=h, sub_step=0, tod=tod,
                temp=w.temp, rh=w.rh, wind=w.wind, clouds=w.clouds,
                elevation=elev,
                rain_inches=rain_map.get(h, 0.0),
            ))
        return _expand_to_substeps(weather_steps, scenario,
                                   interpolation=InterpolationMode.LINEAR)


def run_scenario(
    scenario: Scenario,
    model: LawnModel,
    params: dict[str, float],
    weather_steps: list[WeatherStep] | None = None,
    stop_after_mow: bool = False,
) -> list[dict[str, Any]]:
    """
    Run a scenario for its full duration.

    weather_steps: pre-built list (from history resampler). If None, steps
                   are generated from scenario.weather + solar model.
    stop_after_mow: if True, stop once the lawn first dries below the mow
                    threshold after having been wet (wetness > threshold).
    """
    if weather_steps is None:
        weather_steps = build_weather_steps(scenario)

    state = model.initial_state(scenario.initial_wetness)
    rows: list[dict[str, Any]] = []
    mow_threshold = params["mow_threshold"]
    became_wet = False

    for ws in weather_steps:
        wetness_in  = model.surface_wetness(state)
        result      = model.step(state, ws, params)
        wetness_out = result["wetness_out"]

        rows.append({
            "hour":           ws.hour,
            "sub_step":       ws.sub_step,
            "steps_per_hour": ws.steps_per_hour,
            "tod":            ws.tod,
            "elevation":      ws.elevation,
            "rain_inches":    ws.rain_inches,
            "wetness_in":     wetness_in,
            "wetness_out":    wetness_out,
            "drying_rate":    result["drying_rate"],
            "can_mow":        wetness_out <= mow_threshold,
            "diagnostics":    result["diagnostics"],
        })

        if stop_after_mow:
            if wetness_out > mow_threshold:
                became_wet = True
            elif became_wet and wetness_out <= mow_threshold:
                state = model.initial_state(wetness_out)
                return rows
        state = model.initial_state(wetness_out)

    return rows


def hours_to_mow(
    rows: list[dict[str, Any]],
    threshold: float,
    steps_per_hour: int = 1,
) -> int | None:
    """
    Return the first hour where wetness_out ≤ threshold *after* the lawn
    has been wet (wetness > threshold at any earlier point).

    For sub-hourly resolution, the hour is computed as
    ``first_matching_sub_step // steps_per_hour``.

    This skips the initial dry period so that CSVs starting with low
    wetness don't report hour-0 mow when rain hasn't actually occurred yet.
    """
    became_wet = False
    for i, r in enumerate(rows):
        if r["wetness_out"] > threshold:
            became_wet = True
        elif became_wet and r["wetness_out"] <= threshold:
            return int(i // steps_per_hour)
    return None
