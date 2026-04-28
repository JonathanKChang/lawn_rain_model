"""Integration tests: history CSV → WeatherStep → run_scenario."""
from __future__ import annotations
from pathlib import Path
import textwrap
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.calibration.scenarios import Scenario, ScenarioLoader
from lawn_rain_model.simulation.runner import run_scenario, build_weather_steps, hours_to_mow
from lawn_rain_model.simulation.weather import DEFAULT_SENSOR_MAP

# Path to the fixture history CSV used by end-to-end tests.
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_HISTORY_CSV = FIXTURES_DIR / "test_history.csv"
FIXTURE_SCENARIOS_YAML = FIXTURES_DIR / "scenarios_test.yaml"


@pytest.mark.skipif(
    not TEST_HISTORY_CSV.exists(),
    reason="test_history.csv not present",
)
def test_real_history_produces_steps() -> None:
    steps = build_weather_steps(
        Scenario(
            name="real",
            duration_hours=0,   # ignored when history_file is set
            rain_events=[],
            weather=None,
            history_file=str(TEST_HISTORY_CSV),
        ),
        base_path=FIXTURES_DIR,
    )
    assert len(steps) > 0


@pytest.mark.skipif(
    not TEST_HISTORY_CSV.exists(),
    reason="test_history.csv not present",
)
def test_real_history_runner_completes() -> None:
    model = SingleLayerModel()
    s = Scenario(
        name="real",
        duration_hours=0,
        rain_events=[],
        weather=None,
        history_file=str(TEST_HISTORY_CSV),
    )
    steps = build_weather_steps(s, base_path=FIXTURES_DIR)
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
    )
    steps = build_weather_steps(s, base_path=tmp_path)
    rows = run_scenario(s, model, model.default_params, weather_steps=steps)
    assert len(rows) > 0
    assert rows[0]["rain_inches"] > 0   # 0.3" fell in hour 10


# ---------------------------------------------------------------------------
# Tests for loading the fixture scenarios YAML
# ---------------------------------------------------------------------------

def test_load_fixture_scenarios_yaml() -> None:
    """Fixture YAML loads and returns the expected number of scenarios."""
    scenarios = ScenarioLoader.load(FIXTURE_SCENARIOS_YAML)
    assert len(scenarios) == 2


def test_fixture_scenario_history_backed() -> None:
    """The history_test_scenario references test_history.csv correctly."""
    scenarios = ScenarioLoader.load(FIXTURE_SCENARIOS_YAML)
    history_scenarios = [s for s in scenarios if s.history_file]
    assert len(history_scenarios) == 1
    s = history_scenarios[0]
    assert s.name == "history_test_scenario"
    assert Path(s.history_file).name == "test_history.csv"
    assert s.calibration is not None
    assert s.calibration.target_hours_min == 12.0
    assert s.calibration.target_hours_max == 12.0


def test_fixture_scenario_weather_backed() -> None:
    """The simple_warm_sunny scenario uses weather dict, not history."""
    scenarios = ScenarioLoader.load(FIXTURE_SCENARIOS_YAML)
    weather_scenarios = [s for s in scenarios if s.weather is not None]
    assert len(weather_scenarios) == 1
    s = weather_scenarios[0]
    assert s.name == "simple_warm_sunny"
    assert s.history_file is None
    assert s.weather is not None
    assert s.weather.temp == 80
    assert s.weather.rh == 50
    assert s.calibration is not None
    assert s.calibration.target_hours_min == 4
    assert s.calibration.target_hours_max == 10


@pytest.mark.skipif(
    not TEST_HISTORY_CSV.exists(),
    reason="test_history.csv not present",
)
def test_fixture_history_scenario_runs(tmp_path: Path) -> None:
    """Load fixture YAML, run the history-backed scenario end-to-end."""
    scenarios = ScenarioLoader.load(FIXTURE_SCENARIOS_YAML)
    history_scenario = next(s for s in scenarios if s.name == "history_test_scenario")

    model = SingleLayerModel()
    steps = build_weather_steps(history_scenario, base_path=FIXTURES_DIR)
    rows = run_scenario(history_scenario, model, model.default_params, weather_steps=steps)
    assert len(rows) > 0
    assert rows[0]["rain_inches"] >= 0
    # Check that at least one row has a wetness value
    assert any("wetness_out" in r for r in rows)


def test_fixture_weather_scenario_runs() -> None:
    """Load fixture YAML, run the weather-backed scenario end-to-end."""
    scenarios = ScenarioLoader.load(FIXTURE_SCENARIOS_YAML)
    weather_scenario = next(s for s in scenarios if s.name == "simple_warm_sunny")

    model = SingleLayerModel()
    rows = run_scenario(weather_scenario, model, model.default_params)
    assert len(rows) == weather_scenario.duration_hours
    assert rows[0]["rain_inches"] > 0  # rain at hour 0
    # Find the mow time (first hour where wetness drops below threshold)
    threshold = model.default_params["mow_threshold"]
    mow_times = [
        r["hour"] for r in rows if r["wetness_out"] <= threshold
    ]
    # With warm conditions and 1" rain (no solar model), mow time ~21h
    assert len(mow_times) > 0
    first_mow = min(mow_times)
    assert 18 <= first_mow <= 24
