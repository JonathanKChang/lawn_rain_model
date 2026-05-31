# lawn_rain_model/calibration/optimizer.py
"""Differential evolution optimizer for model parameter fitting."""
from __future__ import annotations
import logging
from typing import Callable
from scipy.optimize import OptimizeResult, differential_evolution
from lawn_rain_model.models.protocol import LawnModel
from lawn_rain_model.calibration.scenarios import Scenario
from lawn_rain_model.calibration.loss import scenario_loss
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow
from lawn_rain_model.types import ArrayLike, OptimizerResult

logger = logging.getLogger(__name__)


def build_objective(
    calibration_scenarios: list[Scenario],
    model: LawnModel,
    base_params: dict[str, float],
    tunable_keys: list[str],
) -> Callable[[ArrayLike], float]:
    def objective(vec: ArrayLike) -> float:
        p = base_params.copy()
        for k, v in zip(tunable_keys, vec):
            p[k] = v
        # Hard constraint: stage_thresh must be below pool_thresh
        if p["stage_thresh"] >= p["pool_thresh"]:
            return 1e6
        total = 0.0
        for s in calibration_scenarios:
            rows = run_scenario(s, model, p)
            h2m  = hours_to_mow(rows, p["mow_threshold"], s.steps_per_hour)
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
) -> OptimizerResult:
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

    iter_count = 0

    def _progress_cb(xk: ArrayLike, convergence: float) -> None:
        nonlocal iter_count
        iter_count += 1
        if iter_count % 50 == 0:
            logger.info(
                "iter=%5d  convergence=%.8f",
                iter_count, convergence,
            )

    de_result: OptimizeResult = differential_evolution(
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
    for k, v in zip(tunable_keys, de_result.x):
        best_params[k] = v

    return {
        "params":       best_params,
        "loss":         float(de_result.fun),
        "success":      bool(de_result.success),
        "message":      str(de_result.message),
        "iterations":   int(de_result.nit),
        "tunable_keys": tunable_keys,
    }
