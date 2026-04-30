"""Scoring functions for history-backed scenarios.

Provides utilities to evaluate how well the model predicts mowable
times against manually annotated ground truth.
"""
from __future__ import annotations

from typing import Any

from lawn_rain_model.calibration.scenarios import Scenario, CalibrationTarget
from lawn_rain_model.calibration.loss import scenario_loss
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow
from lawn_rain_model.models.protocol import LawnModel


def score_scenario(
    scenario: Scenario,
    model: LawnModel,
    params: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Score a single scenario against its ground truth.

    Args:
        scenario: The scenario to score (should have calibration for meaningful scores).
        model: LawnModel to run.
        params: Model parameters (or None for defaults).

    Returns:
        Dict with scenario name, predicted hours, target hours, error, loss, status.
    """
    effective_params = params if params is not None else model.default_params
    rows = run_scenario(scenario, model, effective_params)
    threshold = effective_params.get("mow_threshold", 5.0)
    h2m = hours_to_mow(rows, threshold, scenario.steps_per_hour)

    if scenario.calibration is None:
        return {
            "name": scenario.name,
            "predicted_hours": h2m,
            "target_hours": None,
            "error_hours": None,
            "loss": None,
            "status": "NO_TARGET",
        }

    cal = scenario.calibration
    target = cal.target_hours_min
    loss = scenario_loss(h2m, cal, scenario.duration_hours)

    if h2m is None:
        error: float | None = None
        status = "NEVER_DRIED"
    else:
        error = h2m - target
        if abs(error) < 1.0:
            status = "CLOSE"
        elif abs(error) < 3.0:
            status = "MODERATE"
        else:
            status = "POOR"

    return {
        "name": scenario.name,
        "predicted_hours": h2m,
        "target_hours": target,
        "error_hours": error,
        "loss": loss,
        "status": status,
    }


def score_all_scenarios(
    scenarios: list[Scenario],
    model: LawnModel,
    params: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Score multiple scenarios.

    Args:
        scenarios: List of scenarios to score.
        model: LawnModel to run.
        params: Model parameters.

    Returns:
        List of score dicts.
    """
    return [score_scenario(s, model, params) for s in scenarios]


def print_score_report(scores: list[dict[str, Any]]) -> None:
    """Print a formatted scoring report.

    Args:
        scores: List of score dicts from score_scenario.
    """
    print(f"\n{'=' * 72}")
    print("  SCENARIO SCORING REPORT")
    print(f"{'=' * 72}")
    print(f"\n  {'Scenario':<35} {'Predicted':>10} {'Target':>10} {'Error':>8}  {'Loss':>8}  Status")
    print("  " + "-" * 80)

    total_loss = 0.0
    for s in scores:
        pred = f"{s['predicted_hours']}h" if s["predicted_hours"] is not None else "never"
        target = f"{s['target_hours']:.1f}h" if s["target_hours"] is not None else "\u2014"
        error = f"{s['error_hours']:+.1f}h" if s["error_hours"] is not None else "\u2014"
        loss = f"{s['loss']:.4f}" if s["loss"] is not None else "\u2014"
        total_loss += s["loss"] or 0.0
        print(f"  {s['name']:<35} {pred:>10} {target:>10} {error:>8}  {loss:>8}  {s['status']}")

    print(f"\n  Total loss: {total_loss:.4f}")
    print(f"{'=' * 72}\n")
