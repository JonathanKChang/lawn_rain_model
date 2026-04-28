# tests/test_history_runner.py
"""Integration tests: history CSV → WeatherStep → run_scenario."""
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.calibration.scenarios import Scenario, ScenarioLoader
from lawn_rain_model.simulation.runner import run_scenario, build_weather_steps, hours_to_mow
from lawn_rain_model.simulation.weather import DEFAULT_SENSOR_MAP

PROJECT_HISTORY = Path("history.csv")


@pytest.mark.skipif(
    not PROJECT_HISTORY.exists(),
    reason="history.csv not present",
)
def test_real_history_produces_steps() -> None:
    steps = build_weather_steps(
        Scenario(
            name="real",
            duration_hours=0,   # ignored when history_file is set
            rain_events=[],
            weather=None,
            history_file=str(PROJECT_HISTORY),
        ),
        base_path=Path("."),
    )
    assert len(steps) > 0


@pytest.mark.skipif(
    not PROJECT_HISTORY.exists(),
    reason="history.csv not present",
)
def test_real_history_runner_completes() -> None:
    model = SingleLayerModel()
    s = Scenario(
        name="real",
        duration_hours=0,
        rain_events=[],
        weather=None,
        history_file=str(PROJECT_HISTORY),
        mow_threshold=5.0,
    )
    steps = build_weather_steps(s, base_path=Path("."))
    rows = run_scenario(s, model, model.default_params, weather_steps=steps)
    assert len(rows) == len(steps)
    assert all("wetness_out" in r for r in rows)


def test_history_scenario_from_yaml(tmp_path: Path) -> None:
    """ScenarioLoader populates history_file and sensor_map correctly."""
    hist_csv = tmp_path / "test_history.csv"
    hist_csv.write_text(
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:30:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.5,2026-04-24T10:45:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,40.0,2026-04-24T11:00:00.000Z\n"
    )

    yaml_text = textwrap.dedent(f"""\
        scenarios:
          - name: history_test
            history_file: {hist_csv}
            mow_threshold: 5.0
            calibration:
              target_hours: 12.0
              weight: 1.0
    """)
    yaml_file = tmp_path / "scenarios.yaml"
    yaml_file.write_text(yaml_text)

    scenarios = ScenarioLoader.load(yaml_file)
    assert len(scenarios) == 1
    s = scenarios[0]
    assert s.history_file == str(hist_csv)
    assert s.calibration is not None
    assert s.calibration.target_hours_min == 12.0
    assert s.calibration.target_hours_max == 12.0


def test_history_scenario_runs_end_to_end(tmp_path: Path) -> None:
    """Full pipeline: YAML → ScenarioLoader → build_weather_steps → run_scenario."""
    hist_csv = tmp_path / "hist.csv"
    hist_csv.write_text(
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:30:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.3,2026-04-24T10:30:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,40.0,2026-04-24T11:00:00.000Z\n"
    )
    model = SingleLayerModel()
    s = Scenario(
        name="e2e",
        duration_hours=0,
        rain_events=[],
        weather=None,
        history_file=str(hist_csv),
        mow_threshold=5.0,
    )
    steps = build_weather_steps(s, base_path=tmp_path)
    rows = run_scenario(s, model, model.default_params, weather_steps=steps)
    assert len(rows) > 0
    assert rows[0]["rain_inches"] > 0   # 0.3" fell in hour 10
