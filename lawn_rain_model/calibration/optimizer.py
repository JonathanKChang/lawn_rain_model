# lawn_rain_model/calibration/optimizer.py
"""Differential evolution optimizer for model parameter fitting."""
from __future__ import annotations
from typing import Any
from scipy.optimize import differential_evolution
from lawn_rain_model.models.protocol import LawnModel
from lawn_rain_model.calibration.scenarios import Scenario
from lawn_rain_model.calibration.loss import scenario_loss
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow

_iter_count: list[int] = [0]


def _progress_cb(xk: Any, convergence: float) -> None:
    _iter_count[0] += 1
    if _iter_count[0] % 50 == 0:
        print(f"  iter={_iter_count[0]:>5}  convergence={convergence:.8f}", end="\r", flush=True)


def build_objective(
    calibration_scenarios: list[Scenario],
    model: LawnModel,
    base_params: dict[str, float],
    tunable_keys: list[str],
) -> Any:
    def objective(vec: Any) -> float:
        p = base_params.copy()
        for k, v in zip(tunable_keys, vec):
            p[k] = v
        # Hard constraint: stage_thresh must be below pool_thresh
        if p["stage_thresh"] >= p["pool_thresh"]:
            return 1e6
        total = 0.0
        for s in calibration_scenarios:
            rows = run_scenario(s, model, p)
            h2m  = hours_to_mow(rows, p["mow_threshold"])
            loss = scenario_loss(h2m, s.calibration, s.duration_hours)  # type: ignore[arg-type]
            total += loss * s.calibration.weight  # type: ignore[union-attr]
        return total
    return objective


def run_optimizer(
    calibration_scenarios: list[Scenario],
    model: LawnModel,
    frozen: dict[str, float] | None = None,
    maxiter: int = 2000,
    popsize: int = 20,
    tol: float = 1e-5,
    seed: int = 42,
) -> dict[str, Any]:
    frozen = frozen or {}
    bounds_map = model.param_bounds
    tunable_keys = [k for k in bounds_map if k not in frozen]
    bounds       = [bounds_map[k] for k in tunable_keys]

    base_params = model.default_params
    base_params.update(frozen)

    print(f"\nOptimizing {len(tunable_keys)} parameters across "
          f"{len(calibration_scenarios)} calibration scenarios")
    print(f"Frozen: {list(frozen.keys()) or 'none'}")
    print(f"Popsize={popsize}  maxiter={maxiter}  tol={tol}\n")

    _iter_count[0] = 0
    result = differential_evolution(
        build_objective(calibration_scenarios, model, base_params, tunable_keys),
        bounds,
        seed=seed,
        maxiter=maxiter,
        popsize=popsize,
        tol=tol,
        polish=True,
        updating="deferred",
        workers=1,
        callback=_progress_cb,
    )
    print()

    best_params = base_params.copy()
    for k, v in zip(tunable_keys, result.x):
        best_params[k] = v

    return {
        "params":       best_params,
        "loss":         result.fun,
        "success":      result.success,
        "message":      result.message,
        "iterations":   result.nit,
        "tunable_keys": tunable_keys,
    }
