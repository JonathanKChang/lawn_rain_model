"""Tests for the csv-run CLI command."""
from __future__ import annotations
from pathlib import Path
import textwrap
import pytest
from lawn_rain_model.cli.commands import cmd_csv_run
from lawn_rain_model.models.single_layer import SingleLayerModel
import argparse

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_HISTORY_CSV = FIXTURES_DIR / "test_history.csv"


def _make_csv(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def _make_args(**overrides) -> argparse.Namespace:
    defaults = {
        "csv_file": [],
        "params_file": None,
        "sensor_map": None,
        "initial": 0.0,
        "output": None,
        "summary_only": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_csv_run_single_file(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """csv-run processes a single CSV and produces output rows."""
    hist = _make_csv(tmp_path, "test.csv",
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

    args = _make_args(csv_file=[str(hist)])
    cmd_csv_run(args)

    model = SingleLayerModel()
    output = Path(str(hist.with_suffix("")) + "_test.csv")
    assert output.exists()
    rows = list(output.read_text().strip().split("\n"))
    assert len(rows) > 1  # header + data rows


def test_csv_run_multiple_files(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """csv-run processes multiple CSVs, each gets its own output."""
    csv1 = _make_csv(tmp_path, "a.csv",
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z\n"
    )
    csv2 = _make_csv(tmp_path, "b.csv",
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,80.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,50,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,3.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,10,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,60.0,2026-04-24T10:00:00.000Z\n"
    )

    args = _make_args(csv_file=[str(csv1), str(csv2)])
    cmd_csv_run(args)

    assert Path(str(csv1.with_suffix("")) + "_a.csv").exists()
    assert Path(str(csv2.with_suffix("")) + "_b.csv").exists()


def test_csv_run_with_output_prefix(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """csv-run with --output prefix creates files in the same directory."""
    hist = _make_csv(tmp_path, "data.csv",
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z\n"
    )

    args = _make_args(csv_file=[str(hist)], output=str(tmp_path / "results"))
    cmd_csv_run(args)

    assert (tmp_path / "results_data.csv").exists()


def test_csv_run_missing_file() -> None:
    """csv-run exits with error for missing CSV."""
    args = _make_args(csv_file=["/nonexistent/file.csv"])
    with pytest.raises(SystemExit) as excinfo:
        cmd_csv_run(args)
    assert excinfo.value.code == 1


def test_csv_run_no_files(capsys: pytest.CaptureFixture) -> None:
    """csv-run exits with error when no CSV files provided."""
    args = _make_args(csv_file=[])
    with pytest.raises(SystemExit) as excinfo:
        cmd_csv_run(args)
    assert excinfo.value.code == 1


def test_csv_run_initial_wetness(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """csv-run respects --initial wetness parameter."""
    hist = _make_csv(tmp_path, "init.csv",
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z\n"
    )

    args = _make_args(csv_file=[str(hist)], initial=50.0)
    cmd_csv_run(args)

    output = Path(str(hist.with_suffix("")) + "_init.csv")
    content = output.read_text()
    # First row should have wetness_out around 50 (initial)
    lines = content.strip().split("\n")
    header = lines[0].split(",")
    wetness_idx = header.index("wetness_out")
    first_wetness = float(lines[1].split(",")[wetness_idx])
    assert 45 <= first_wetness <= 55  # initial 50, slight drying in hour 10
