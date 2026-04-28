# tests/test_scenarios.py
from __future__ import annotations
import textwrap
import pytest
from pathlib import Path
from lawn_rain_model.calibration.scenarios import ScenarioLoader


SAMPLE_YAML = textwrap.dedent("""\
    scenarios:
      - name: range_target
        duration_hours: 48
        rain_events:
          - hour: 0
            inches: 1.0
        weather:
          temp: 75
          rh: 60
          wind: 5
          clouds: 30
        calibration:
          target_hours_min: 3
          target_hours_max: 6
          weight: 1.5
          note: "range scenario"

      - name: point_target
        duration_hours: 72
        rain_events:
          - hour: 0
            inches: 1.0
        weather:
          temp: 65
          rh: 60
          wind: 5
          clouds: 50
        calibration:
          target_hours: 14.0
          weight: 2.0
          note: "point scenario"

      - name: no_cal
        duration_hours: 24
        rain_events: []
        weather:
          temp: 70
          rh: 65
          wind: 5
          clouds: 40
""")


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    p = tmp_path / "scenarios.yaml"
    p.write_text(SAMPLE_YAML)
    return p


def test_loads_all_scenarios(yaml_file: Path) -> None:
    scenarios = ScenarioLoader.load(yaml_file)
    assert len(scenarios) == 3


def test_range_target_bounds(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    r = next(x for x in s if x.name == "range_target")
    assert r.calibration is not None
    assert r.calibration.target_hours_min == 3
    assert r.calibration.target_hours_max == 6
    assert r.calibration.weight == 1.5


def test_point_target_min_equals_max(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    p = next(x for x in s if x.name == "point_target")
    assert p.calibration is not None
    assert p.calibration.target_hours_min == 14.0
    assert p.calibration.target_hours_max == 14.0
    assert p.calibration.weight == 2.0


def test_no_calibration_is_none(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    n = next(x for x in s if x.name == "no_cal")
    assert n.calibration is None


def test_skip_calibration_flag(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file, include_calibration=False)
    for scenario in s:
        assert scenario.calibration is None


def test_rain_events_loaded(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    r = next(x for x in s if x.name == "range_target")
    assert len(r.rain_events) == 1
    assert r.rain_events[0].hour == 0
    assert r.rain_events[0].inches == 1.0


def test_weather_conditions_loaded(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    r = next(x for x in s if x.name == "range_target")
    assert r.weather is not None
    assert r.weather.temp == 75
    assert r.weather.rh == 60


def test_existing_scenarios_yaml_loads() -> None:
    """The project's actual scenarios.yaml must load without error."""
    scenarios = ScenarioLoader.load("scenarios/scenarios.yaml")
    assert len(scenarios) > 0
    names = [s.name for s in scenarios]
    assert "calib_hot_sunny" in names
