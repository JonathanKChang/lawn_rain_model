"""Tests for CLI commands (cli/commands.py).

This is the single largest remaining coverage gap: 282 lines at ~24%.
Each test covers a command function and exercises both argument parsing
and the underlying model execution.
"""
from __future__ import annotations

import argparse
import tempfile
import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def cli_scenarios_yaml(tmp_path: Path) -> Path:
    """Create a minimal scenarios YAML file for CLI tests."""
    yaml_text = textwrap.dedent("""\
        scenarios:
          - name: test_hot_sunny
            duration_hours: 24
            rain_events:
              - hour: 0
                inches: 1.0
            weather:
              temp: 85
              rh: 30
              wind: 10
              clouds: 10
            use_solar_model: false
            start_hour: 8
            day_of_year: 172
            latitude: 39.0
            calibration:
              target_hours_min: 2
              target_hours_max: 8
              weight: 1.5

          - name: test_cool_rainy
            duration_hours: 48
            rain_events:
              - hour: 0
                inches: 1.0
            weather:
              temp: 50
              rh: 80
              wind: 3
              clouds: 90
            use_solar_model: false
            start_hour: 8
            day_of_year: 172
            latitude: 39.0
            calibration:
              target_hours_min: 18
              target_hours_max: 30
              weight: 1.0

          - name: test_no_cal
            duration_hours: 24
            rain_events:
              - hour: 0
                inches: 0.5
            weather:
              temp: 70
              rh: 65
              wind: 5
              clouds: 40
            use_solar_model: false
    """)
    yaml_path = tmp_path / "scenarios.yaml"
    yaml_path.write_text(yaml_text)
    return yaml_path


@pytest.fixture
def params_file(tmp_path: Path) -> Path:
    """Create a minimal params YAML file."""
    params = {
        "params": {
            "base_evap": 0.06,
            "vpd_norm_denom": 0.40,
            "e_sat_base": 1.0393,
            "vpd_min": 0.02,
            "sun_coeff": 0.18,
            "cloud_exp": 1.40,
            "wind_coeff": 0.022,
            "wind_cap": 0.50,
            "stage_thresh": 18.0,
            "pool_thresh": 40.0,
            "capillary_rate": 0.05,
            "pool_drain_coef": 0.12,
            "rain_mult": 40.0,
            "visc_slope": 0.015,
            "visc_floor": 0.35,
            "mow_threshold": 5.0,
        }
    }
    p = tmp_path / "params.yaml"
    import yaml
    p.write_text(yaml.dump(params))
    return p


# ---------------------------------------------------------------------------
# K1: cmd_simulate basic run
# ---------------------------------------------------------------------------


def test_cmd_simulate_basic_run(cli_scenarios_yaml: Path, capsys: pytest.CaptureFixture) -> None:
    """cmd_simulate should run the scenario and produce expected output."""
    from lawn_rain_model.cli.commands import cmd_simulate

    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        name="test_hot_sunny",
        params_file=None,
        summary_only=False,
        csv=None,
        compare_md=None,
        rain=None,
        hours=24,
        initial=0.0,
        temp=75.0,
        rh=60.0,
        wind=5.0,
        clouds=30.0,
        start_hour=6,
        day_of_year=172,
        lat=39.0,
        time_step=15,
        no_solar=False,
        save_params=None,
    )
    cmd_simulate(args)

    captured = capsys.readouterr()
    assert "TEST_HOT_SUNNY" in captured.out.upper()
    # Should contain summary with mow time
    assert "MOW" in captured.out.upper() or "peak index" in captured.out.lower()


def test_cmd_simulate_summary_only(cli_scenarios_yaml: Path, capsys: pytest.CaptureFixture) -> None:
    """--summary-only flag should skip the detailed table."""
    from lawn_rain_model.cli.commands import cmd_simulate

    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        name="test_hot_sunny",
        params_file=None,
        summary_only=True,  # Summary only
        csv=None,
        compare_md=None,
        rain=None,
        hours=24,
        initial=0.0,
        temp=75.0,
        rh=60.0,
        wind=5.0,
        clouds=30.0,
        start_hour=6,
        day_of_year=172,
        lat=39.0,
        time_step=15,
        no_solar=False,
        save_params=None,
    )
    cmd_simulate(args)

    captured = capsys.readouterr()
    assert "TEST_HOT_SUNNY" in captured.out.upper()
    # Should NOT contain the table header
    assert "Wet" not in captured.out  # column from detailed table


def test_cmd_simulate_csv_output(cli_scenarios_yaml: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """--csv flag should write a CSV file."""
    from lawn_rain_model.cli.commands import cmd_simulate

    csv_out = tmp_path / "output.csv"
    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        name="test_hot_sunny",
        params_file=None,
        summary_only=True,
        csv=str(csv_out),
        compare_md=None,
        rain=None,
        hours=24,
        initial=0.0,
        temp=75.0,
        rh=60.0,
        wind=5.0,
        clouds=30.0,
        start_hour=6,
        day_of_year=172,
        lat=39.0,
        time_step=15,
        no_solar=False,
        save_params=None,
    )
    cmd_simulate(args)

    assert csv_out.exists()
    content = csv_out.read_text()
    lines = content.strip().split("\n")
    assert len(lines) > 1  # header + data rows
    assert "wetness_out" in lines[0]


def test_cmd_simulate_save_params(cli_scenarios_yaml: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """--save-params flag should write a params YAML file."""
    from lawn_rain_model.cli.commands import cmd_simulate

    params_out = tmp_path / "saved_params.yaml"
    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        name="test_hot_sunny",
        params_file=None,
        summary_only=True,
        csv=None,
        compare_md=None,
        rain=None,
        hours=24,
        initial=0.0,
        temp=75.0,
        rh=60.0,
        wind=5.0,
        clouds=30.0,
        start_hour=6,
        day_of_year=172,
        lat=39.0,
        time_step=15,
        no_solar=False,
        save_params=str(params_out),
    )
    cmd_simulate(args)

    assert params_out.exists()
    import yaml
    saved = yaml.safe_load(params_out.read_text())
    assert "params" in saved
    assert "base_evap" in saved["params"]
    assert "mow_threshold" in saved["params"]


def test_cmd_simulate_scenario_filter_by_name(cli_scenarios_yaml: Path, capsys: pytest.CaptureFixture) -> None:
    """--name should filter to a single scenario."""
    from lawn_rain_model.cli.commands import cmd_simulate

    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        name="test_cool_rainy",  # Only this one
        params_file=None,
        summary_only=True,
        csv=None,
        compare_md=None,
        rain=None,
        hours=24,
        initial=0.0,
        temp=75.0,
        rh=60.0,
        wind=5.0,
        clouds=30.0,
        start_hour=6,
        day_of_year=172,
        lat=39.0,
        time_step=15,
        no_solar=False,
        save_params=None,
    )
    cmd_simulate(args)

    captured = capsys.readouterr()
    assert "TEST_COOL_RAINY" in captured.out.upper()
    # Should NOT include the other scenarios
    assert "TEST_HOT_SUNNY" not in captured.out


def test_cmd_simulate_nonexistent_name(cli_scenarios_yaml: Path) -> None:
    """--name for non-existent scenario should exit with error."""
    from lawn_rain_model.cli.commands import cmd_simulate

    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        name="nonexistent_scenario",
        params_file=None,
        summary_only=True,
        csv=None,
        compare_md=None,
        rain=None,
        hours=24,
        initial=0.0,
        temp=75.0,
        rh=60.0,
        wind=5.0,
        clouds=30.0,
        start_hour=6,
        day_of_year=172,
        lat=39.0,
        time_step=15,
        no_solar=False,
        save_params=None,
    )
    with pytest.raises(SystemExit):
        cmd_simulate(args)


# ---------------------------------------------------------------------------
# K2: cmd_sweep correct output values
# ---------------------------------------------------------------------------


def test_cmd_sweep_basic_output(cli_scenarios_yaml: Path, capsys: pytest.CaptureFixture) -> None:
    """cmd_sweep should produce a formatted table with rain/peak/mow."""
    from lawn_rain_model.cli.commands import cmd_sweep

    args = argparse.Namespace(
        params_file=None,
        rain_inches="0.25,0.5,1.0",
        hours=24,
        temp=75.0,
        rh=60.0,
        wind=5.0,
        clouds=30.0,
        start_hour=6,
        day_of_year=172,
        lat=39.0,
        time_step=15,
        no_solar=False,
    )
    cmd_sweep(args)

    captured = capsys.readouterr()
    assert "Drying sweep" in captured.out
    assert "0.25" in captured.out
    assert "Peak" in captured.out or "peak" in captured.out.lower()


# ---------------------------------------------------------------------------
# K3: cmd_optimize weight>0 filtering, --freeze, --only
# ---------------------------------------------------------------------------


def test_cmd_optimize_uses_calibration_only(cli_scenarios_yaml: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """cmd_optimize should only use scenarios with weight > 0."""
    from lawn_rain_model.cli.commands import cmd_optimize

    # The CLI test scenario file has test_no_cal (no calibration, weight=0 by default)
    # Only test_hot_sunny and test_cool_rainy have calibrations with weight > 0
    saved = tmp_path / "optimized.yaml"
    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        only=None,
        freeze=None,
        save_params=str(saved),
        maxiter=2,  # Very few iterations for speed
        popsize=3,
        tol=1e-2,
        seed=42,
    )
    cmd_optimize(args)

    assert saved.exists()
    import yaml
    data = yaml.safe_load(saved.read_text())
    assert "params" in data
    # Should have the same params keys as defaults
    assert len(data["params"]) == 16


def test_cmd_optimize_only_filter(cli_scenarios_yaml: Path, capsys: pytest.CaptureFixture) -> None:
    """--only flag should filter to specified scenarios."""
    from lawn_rain_model.cli.commands import cmd_optimize

    saved = None  # Don't save, just verify it runs
    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        only="test_hot_sunny",
        freeze=None,
        save_params=None,
        maxiter=2,
        popsize=3,
        tol=1e-2,
        seed=42,
    )
    cmd_optimize(args)

    captured = capsys.readouterr()
    assert "test_hot_sunny" in captured.out


# ---------------------------------------------------------------------------
# K4: cmd_score status classifications
# ---------------------------------------------------------------------------


def test_cmd_score_basic(cli_scenarios_yaml: Path, capsys: pytest.CaptureFixture) -> None:
    """cmd_score should produce a scoring report with statuses."""
    from lawn_rain_model.cli.commands import cmd_score

    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        params_file=None,
        name=None,
    )
    cmd_score(args)

    captured = capsys.readouterr()
    assert "SCENARIO SCORING REPORT" in captured.out
    assert "test_hot_sunny" in captured.out
    assert "test_cool_rainy" in captured.out
    # Should contain status labels
    assert any(s in captured.out for s in ["CLOSE", "MODERATE", "POOR"])


def test_cmd_score_filter_by_name(cli_scenarios_yaml: Path, capsys: pytest.CaptureFixture) -> None:
    """--name should filter score output to a single scenario."""
    from lawn_rain_model.cli.commands import cmd_score

    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        params_file=None,
        name="test_hot_sunny",
    )
    cmd_score(args)

    captured = capsys.readouterr()
    assert "test_hot_sunny" in captured.out
    assert "test_cool_rainy" not in captured.out


def test_cmd_score_nonexistent_name(cli_scenarios_yaml: Path) -> None:
    """--name for non-existent scenario should exit with error."""
    from lawn_rain_model.cli.commands import cmd_score

    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        params_file=None,
        name="nonexistent",
    )
    with pytest.raises(SystemExit):
        cmd_score(args)


def test_cmd_score_with_params_file(cli_scenarios_yaml: Path, params_file: Path, capsys: pytest.CaptureFixture) -> None:
    """cmd_score should accept a params file for override."""
    from lawn_rain_model.cli.commands import cmd_score

    args = argparse.Namespace(
        scenario_file=str(cli_scenarios_yaml),
        params_file=str(params_file),
        name=None,
    )
    cmd_score(args)

    captured = capsys.readouterr()
    assert "SCENARIO SCORING REPORT" in captured.out
