# lawn_rain_model/types.py
"""Shared type aliases for simulation and calibration data."""
from __future__ import annotations
from typing import Protocol

import numpy as np


class StepResult(Protocol):
    """The dict returned by LawnModel.step()."""

    wetness_out: float
    drying_rate: float
    diagnostics: dict[str, float]


class SimulationRow(Protocol):
    """One row in the simulation output produced by run_scenario."""

    hour: int
    sub_step: int
    steps_per_hour: int
    tod: int
    elevation: float
    rain_inches: float
    wetness_in: float
    wetness_out: float
    drying_rate: float
    can_mow: bool
    diagnostics: dict[str, float]


class OptimizerResult(Protocol):
    """The dict returned by run_optimizer."""

    params: dict[str, float]
    loss: float
    success: bool
    message: str
    iterations: int
    tunable_keys: list[str]


# Convenience type alias used throughout the codebase.
ArrayLike = np.ndarray | list[float]
