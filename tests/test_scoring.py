"""Tests for scoring module."""
from __future__ import annotations

import pytest
from pathlib import Path

from lawn_rain_model.calibration.scoring import (
    score_scenario,
    score_all_scenarios,
    print_score_report,
)
from lawn_rain_model.calibration.scenarios import (
    Scenario,
    CalibrationTarget,
    WeatherConditions,
)
from lawn_rain_model.models.single_layer import SingleLayerModel


def _build_history_csv(
    path: Path,
    rain_hour: int = 1,
    rain_inches: float = 0.5,
    hours: int = 24,
) -> None:
    """Build a history CSV with a rain event at a given hour.

    Uses warm/dry conditions so the lawn dries within ~12-15 hours after rain.
    """
    lines: list[str] = ["entity_id,state,last_changed"]
    for h in range(hours):
        hour = h  # 0–23 to stay within a single day
        ts = f"2026-04-24T{hour:02d}:00:00.000Z"
        lines.append(f"sensor.pirateweather_temperature_0h,85.0,{ts}")
        lines.append(f"sensor.pirateweather_humidity_0h,30.0,{ts}")
        lines.append(f"sensor.pirateweather_wind_speed,10.0,{ts}")
        lines.append(f"sensor.pirateweather_cloud_coverage,10.0,{ts}")
        # Simplified sun elevation: peaks at noon
        elev = max(0.0, 50.0 * (1.0 - abs(hour - 12) / 6.0)) if 6 <= hour <= 18 else 0.0
        lines.append(f"sensor.sun_elevation,{elev:.1f},{ts}")
        # Rain accumulation: 0 before rain_hour, rain_inches after
        accum = rain_inches if h >= rain_hour else 0.0
        lines.append(f"sensor.pirateweather_current_day_liquid_accumulation,{accum},{ts}")
    path.write_text("\n".join(lines) + "\n")


def test_score_scenario_with_history_and_calibration(
    tmp_path: Path, model: SingleLayerModel
) -> None:
    """Score a history scenario with a calibration target."""
    hist_csv = tmp_path / "test_history.csv"
    _build_history_csv(hist_csv, rain_hour=1, rain_inches=0.5)

    scenario = Scenario(
        name="test_history",
        duration_hours=24,
        rain_events=[],
        weather=None,
        history_file=str(hist_csv),
        calibration=CalibrationTarget(
            target_hours_min=12.0,
            target_hours_max=12.0,
            weight=1.0,
        ),
    )

    result = score_scenario(scenario, model)

    assert result["name"] == "test_history"
    assert result["target_hours"] == 12.0
    assert result["predicted_hours"] is not None
    assert result["error_hours"] is not None
    assert result["loss"] is not None
    assert result["status"] in ("CLOSE", "MODERATE", "POOR")


def test_score_scenario_no_calibration(model: SingleLayerModel) -> None:
    """Score a scenario without calibration target returns NO_TARGET."""
    scenario = Scenario(
        name="no_cal",
        duration_hours=24,
        rain_events=[],
        weather=WeatherConditions(temp=80.0, rh=50.0, wind=5.0, clouds=20.0),
        calibration=None,
    )

    result = score_scenario(scenario, model)

    assert result["name"] == "no_cal"
    assert result["status"] == "NO_TARGET"
    assert result["target_hours"] is None
    assert result["error_hours"] is None
    assert result["loss"] is None


def test_score_scenario_never_dries(tmp_path: Path, model: SingleLayerModel) -> None:
    """Score a scenario where the lawn never dries below threshold."""
    hist_csv = tmp_path / "rainy_history.csv"
    # Rain every hour — lawn stays wet
    lines: list[str] = ["entity_id,state,last_changed"]
    for h in range(24):
        hour = h  # 0–23 to stay within a single day
        ts = f"2026-04-24T{hour:02d}:00:00.000Z"
        accum = round(h * 0.5, 2)
        lines.append(f"sensor.pirateweather_temperature_0h,80.0,{ts}")
        lines.append(f"sensor.pirateweather_humidity_0h,95.0,{ts}")
        lines.append(f"sensor.pirateweather_wind_speed,1.0,{ts}")
        lines.append(f"sensor.pirateweather_cloud_coverage,100.0,{ts}")
        lines.append(f"sensor.sun_elevation,20.0,{ts}")
        lines.append(f"sensor.pirateweather_current_day_liquid_accumulation,{accum},{ts}")
    hist_csv.write_text("\n".join(lines) + "\n")

    scenario = Scenario(
        name="rainy",
        duration_hours=24,
        rain_events=[],
        weather=None,
        history_file=str(hist_csv),
        calibration=CalibrationTarget(
            target_hours_min=12.0,
            target_hours_max=12.0,
            weight=1.0,
        ),
    )

    result = score_scenario(scenario, model)

    assert result["status"] == "NEVER_DRIED"
    assert result["predicted_hours"] is None


def test_score_all_scenarios(model: SingleLayerModel) -> None:
    """Score multiple scenarios returns list of score dicts."""
    scenarios = [
        Scenario(
            name="s1",
            duration_hours=24,
            rain_events=[],
            weather=WeatherConditions(temp=80.0, rh=50.0, wind=5.0, clouds=20.0),
            calibration=CalibrationTarget(
                target_hours_min=12.0, target_hours_max=12.0, weight=1.0
            ),
        ),
        Scenario(
            name="s2",
            duration_hours=24,
            rain_events=[],
            weather=WeatherConditions(temp=70.0, rh=70.0, wind=3.0, clouds=60.0),
            calibration=CalibrationTarget(
                target_hours_min=18.0, target_hours_max=18.0, weight=1.0
            ),
        ),
    ]

    results = score_all_scenarios(scenarios, model)

    assert len(results) == 2
    for r in results:
        assert "name" in r
        assert "status" in r
        assert "predicted_hours" in r
        assert "target_hours" in r


def test_print_score_report_no_crash(capsys: pytest.CaptureFixture) -> None:
    """print_score_report prints a formatted report without crashing."""
    scores = [
        {
            "name": "s1",
            "predicted_hours": 12,
            "target_hours": 12.0,
            "error_hours": 0.0,
            "loss": 0.0,
            "status": "CLOSE",
        },
        {
            "name": "s2",
            "predicted_hours": 20,
            "target_hours": 18.0,
            "error_hours": 2.0,
            "loss": 0.4444,
            "status": "MODERATE",
        },
    ]

    print_score_report(scores)

    captured = capsys.readouterr()
    assert "SCENARIO SCORING REPORT" in captured.out
    assert "s1" in captured.out
    assert "s2" in captured.out
    assert "Total loss:" in captured.out
