"""Tests for the optimizer module.

These are the highest-priority tests — the optimizer is currently at 25% coverage
with zero dedicated tests. A bug here produces silently wrong parameters after
hours of computation.

Structure: unit tests for build_objective (fast), integration-ready scaffolding
for run_optimizer (marked slow). Designed to be extended with hypothesis later.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest
from lawn_rain_model.calibration.optimizer import build_objective, run_optimizer
from lawn_rain_model.calibration.scenarios import (
    Scenario,
    WeatherConditions,
    RainEvent,
    CalibrationTarget,
)
from lawn_rain_model.models.single_layer import SingleLayerModel


@pytest.fixture
def model() -> SingleLayerModel:
    return SingleLayerModel()


# ---------------------------------------------------------------------------
# Helper: create a minimal calibration scenario for testing the objective function
# ---------------------------------------------------------------------------

def _make_cal_scenario(
    name: str = "cal_test",
    duration_hours: int = 48,
    rain_inches: float = 1.0,
    temp: float = 75.0,
    rh: float = 60.0,
    wind: float = 5.0,
    clouds: float = 30.0,
    target_min: float = 8,
    target_max: float = 14,
    weight: float = 1.0,
    time_step_minutes: int = 60,  # 1 step/hour for predictable results
) -> Scenario:
    return Scenario(
        name=name,
        duration_hours=duration_hours,
        rain_events=[RainEvent(hour=0, inches=rain_inches)],
        weather=WeatherConditions(temp=temp, rh=rh, wind=wind, clouds=clouds),
        use_solar_model=False,
        start_hour=12,
        day_of_year=172,
        latitude=39.0,
        time_step_minutes=time_step_minutes,
        calibration=CalibrationTarget(
            target_hours_min=target_min,
            target_hours_max=target_max,
            weight=weight,
        ),
    )


# ---------------------------------------------------------------------------
# H1: build_objective returns callable
# ---------------------------------------------------------------------------


def test_build_objective_returns_callable(model: SingleLayerModel) -> None:
    """build_objective should return a callable that accepts an array and returns float."""
    cal_scenarios = [_make_cal_scenario()]
    base_params = model.default_params
    tunable_keys = list(base_params.keys())

    objective = build_objective(cal_scenarios, model, base_params, tunable_keys)

    assert callable(objective)

    # Call with a numpy-like array of correct length
    import numpy as np
    vec = np.array([base_params[k] for k in tunable_keys])
    result = objective(vec)
    assert isinstance(result, float)
    assert result >= 0.0


def test_build_objective_accepts_array_like(model: SingleLayerModel) -> None:
    """Objective should accept list as well as numpy array."""
    cal_scenarios = [_make_cal_scenario()]
    base_params = model.default_params
    tunable_keys = list(base_params.keys())

    objective = build_objective(cal_scenarios, model, base_params, tunable_keys)
    vec = [base_params[k] for k in tunable_keys]
    result = objective(vec)
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# H2: Objective loss matches manual calculation
# ---------------------------------------------------------------------------


def test_objective_matches_manual_loss(model: SingleLayerModel) -> None:
    """The objective function should compute the same total loss as manually
    running scenarios and summing weighted losses."""
    from lawn_rain_model.calibration.loss import scenario_loss
    from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow

    cal_scenarios = [
        _make_cal_scenario(name="s1", temp=80, rh=40, weight=1.0),
        _make_cal_scenario(name="s2", temp=60, rh=75, weight=2.0),
    ]
    base_params = model.default_params
    tunable_keys = list(base_params.keys())

    # Set all parameters to defaults
    vec = [base_params[k] for k in tunable_keys]
    objective = build_objective(cal_scenarios, model, base_params, tunable_keys)
    computed_loss = objective(vec)

    # Manual calculation — must use steps_per_hour (not time_step_minutes!)
    manual_total = 0.0
    for s in cal_scenarios:
        rows = run_scenario(s, model, base_params)
        h2m = hours_to_mow(rows, base_params["mow_threshold"], s.steps_per_hour)
        loss = scenario_loss(h2m, s.calibration, s.duration_hours)
        manual_total += loss * s.calibration.weight

    assert abs(computed_loss - manual_total) < 1e-6, (
        f"Objective computed {computed_loss:.6f} but manual calculation gives {manual_total:.6f}"
    )


def test_objective_changes_with_parameter_change(model: SingleLayerModel) -> None:
    """Changing parameters should change the objective value."""
    cal_scenarios = [_make_cal_scenario()]
    base_params = model.default_params
    tunable_keys = list(base_params.keys())
    objective = build_objective(cal_scenarios, model, base_params, tunable_keys)

    # Default params
    vec_default = [base_params[k] for k in tunable_keys]
    loss_default = objective(vec_default)

    # Modify base_evap significantly (use max bound)
    vec_modified = list(vec_default)
    idx = tunable_keys.index("base_evap")
    evap_bounds = model.param_bounds["base_evap"]
    vec_modified[idx] = evap_bounds[1]  # max value

    loss_modified = objective(vec_modified)
    assert abs(loss_modified - loss_default) > 1e-6, (
        "Objective should change when parameters change"
    )


# ---------------------------------------------------------------------------
# H4: Hard constraint: stage_thresh >= pool_thresh → returns 1e6
# ---------------------------------------------------------------------------


def test_hard_constraint_violated_returns_large_loss(model: SingleLayerModel) -> None:
    """When stage_thresh >= pool_thresh, objective must return a large penalty (1e6)."""
    cal_scenarios = [_make_cal_scenario()]
    base_params = model.default_params
    tunable_keys = list(base_params.keys())
    objective = build_objective(cal_scenarios, model, base_params, tunable_keys)

    # Create parameter vector where stage_thresh >= pool_thresh
    vec = list(base_params[k] for k in tunable_keys)
    stage_idx = tunable_keys.index("stage_thresh")
    pool_idx = tunable_keys.index("pool_thresh")

    # Set stage_thresh above pool_thresh
    vec[stage_idx] = 50.0
    vec[pool_idx] = 30.0

    result = objective(vec)
    assert result >= 1e5, (
        f"Expected large penalty for stage_thresh >= pool_thresh, got {result}"
    )


def test_hard_constraint_satisfied_returns_normal_loss(model: SingleLayerModel) -> None:
    """When stage_thresh < pool_thresh (valid), objective should return normal loss."""
    cal_scenarios = [_make_cal_scenario()]
    base_params = model.default_params
    tunable_keys = list(base_params.keys())
    objective = build_objective(cal_scenarios, model, base_params, tunable_keys)

    vec = list(base_params[k] for k in tunable_keys)
    result = objective(vec)
    assert result < 1e5, (
        f"Expected normal loss with valid params, got {result}"
    )
    assert math.isfinite(result), "Objective should return finite value"


# ---------------------------------------------------------------------------
# H5: Weighted loss aggregation proportional
# ---------------------------------------------------------------------------


def test_weighted_loss_proportional(model: SingleLayerModel) -> None:
    """Two identical scenarios with different weights should contribute proportionally."""
    from lawn_rain_model.calibration.loss import scenario_loss
    from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow

    # Create two identical scenarios but with different weights
    s1 = _make_cal_scenario(name="w1", weight=1.0)
    s2 = _make_cal_scenario(name="w2", weight=3.0)
    cal_scenarios = [s1, s2]
    base_params = model.default_params
    tunable_keys = list(base_params.keys())
    objective = build_objective(cal_scenarios, model, base_params, tunable_keys)

    vec = list(base_params[k] for k in tunable_keys)
    total_loss = objective(vec)

    # Manual: each scenario should have the same loss value, so
    # total = loss_s1 * 1.0 + loss_s2 * 3.0 = loss * (1 + 3) = 4 * loss
    rows1 = run_scenario(s1, model, base_params)
    h2m = hours_to_mow(rows1, base_params["mow_threshold"], s1.steps_per_hour)
    single_loss = scenario_loss(h2m, s1.calibration, s1.duration_hours)
    expected = single_loss * 1.0 + single_loss * 3.0

    assert abs(total_loss - expected) < 1e-6


# ---------------------------------------------------------------------------
# H6: run_optimizer return structure
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_run_optimizer_return_structure(model: SingleLayerModel) -> None:
    """run_optimizer should return a dict with all expected keys and correct types."""
    cal_scenarios = [_make_cal_scenario(duration_hours=24, time_step_minutes=60)]
    result = run_optimizer(
        cal_scenarios, model, maxiter=5, popsize=5, tol=1e-3, seed=42,
    )

    expected_keys = {"params", "loss", "success", "message", "iterations", "tunable_keys"}
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )
    assert isinstance(result["params"], dict)
    assert isinstance(result["loss"], float)
    assert isinstance(result["success"], bool)
    assert isinstance(result["message"], str)
    assert isinstance(result["iterations"], int)
    assert isinstance(result["tunable_keys"], list)
    # params should have the same keys as default_params
    assert set(result["params"].keys()) == set(model.default_params.keys())


@pytest.mark.slow
def test_run_optimizer_respects_freeze(model: SingleLayerModel) -> None:
    """Frozen parameters should remain at their original values after optimization."""
    cal_scenarios = [_make_cal_scenario(duration_hours=24, time_step_minutes=60)]
    frozen = {"base_evap": 0.1}

    result = run_optimizer(
        cal_scenarios, model, frozen=frozen, maxiter=5, popsize=5, tol=1e-3, seed=42,
    )

    # Frozen param should be unchanged
    assert result["params"]["base_evap"] == frozen["base_evap"], (
        f"base_evap was mutated from {frozen['base_evap']} to {result['params']['base_evap']}"
    )


# ---------------------------------------------------------------------------
# H7: Deterministic seeding — identical results with same seed
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_deterministic_seeding(model: SingleLayerModel) -> None:
    """Same seed + same data should produce identical optimized params."""
    cal_scenarios = [_make_cal_scenario(duration_hours=24, time_step_minutes=60)]

    result1 = run_optimizer(
        cal_scenarios, model.copy() if hasattr(model, 'copy') else SingleLayerModel(),
        maxiter=3, popsize=3, tol=1e-2, seed=42,
    )
    result2 = run_optimizer(
        cal_scenarios, SingleLayerModel(),
        maxiter=3, popsize=3, tol=1e-2, seed=42,
    )

    for key in result1["tunable_keys"]:
        assert result1["params"][key] == pytest.approx(
            result2["params"][key], rel=1e-9
        ), f"Parameter {key} differs between runs: {result1['params'][key]} vs {result2['params'][key]}"


# ---------------------------------------------------------------------------
# H8: Hypothesis-ready scaffolding — parametrized test for future property extension
# ---------------------------------------------------------------------------


class TestOptimizerParametrizedScenarios:
    """Tests parameterized over multiple scenario configurations.

    These are designed to be extended with hypothesis:
    - @hypothesis.given(...) could generate random scenario parameters
    - Property: loss is always non-negative
    - Property: loss decreases when optimizer runs (for well-behaved landscapes)
    """

    @pytest.mark.parametrize("rain_inches", [0.25, 0.5, 1.0, 2.0])
    def test_objective_valid_for_various_rain_amounts(
        self, model: SingleLayerModel, rain_inches: float
    ) -> None:
        """Objective should produce finite, non-negative loss for various rain amounts."""
        cal_scenario = _make_cal_scenario(rain_inches=rain_inches)
        base_params = model.default_params
        tunable_keys = list(base_params.keys())
        objective = build_objective(
            [cal_scenario], model, base_params, tunable_keys
        )
        vec = list(base_params[k] for k in tunable_keys)
        loss = objective(vec)
        assert math.isfinite(loss), f"Non-finite loss for rain={rain_inches}"
        assert loss >= 0.0, f"Negative loss for rain={rain_inches}"

    @pytest.mark.parametrize(
        "weight", [0.5, 1.0, 2.0, 5.0]
    )
    def test_objective_valid_for_various_weights(
        self, model: SingleLayerModel, weight: float
    ) -> None:
        """Objective should handle different calibration weights correctly."""
        cal_scenario = _make_cal_scenario(weight=weight)
        base_params = model.default_params
        tunable_keys = list(base_params.keys())
        objective = build_objective(
            [cal_scenario], model, base_params, tunable_keys
        )
        vec = list(base_params[k] for k in tunable_keys)
        loss = objective(vec)
        assert math.isfinite(loss)
        assert loss >= 0.0

    @pytest.mark.parametrize("target_range", [(6, 12), (8, 14), (16, 24)])
    def test_objective_valid_for_various_targets(
        self, model: SingleLayerModel, target_range: tuple
    ) -> None:
        """Objective should handle different calibration target ranges."""
        lo, hi = target_range
        cal_scenario = _make_cal_scenario(target_min=lo, target_max=hi)
        base_params = model.default_params
        tunable_keys = list(base_params.keys())
        objective = build_objective(
            [cal_scenario], model, base_params, tunable_keys
        )
        vec = list(base_params[k] for k in tunable_keys)
        loss = objective(vec)
        assert math.isfinite(loss)
        assert loss >= 0.0
