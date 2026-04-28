# lawn_rain_model/calibration/loss.py
"""Calibration loss function. Handles both range targets and point targets."""
from __future__ import annotations
from lawn_rain_model.calibration.scenarios import CalibrationTarget


def scenario_loss(
    h2m: int | None,
    target: CalibrationTarget,
    duration: int,
) -> float:
    """
    Squared normalized distance outside [target_min, target_max].

    Returns 0.0 if within range.
    Point targets (min == max) use span=1.0 to avoid division by zero.
    'Never clears' (h2m=None) is treated as h2m == duration.
    """
    if h2m is None:
        h2m = duration
    lo, hi = target.target_hours_min, target.target_hours_max
    if lo <= h2m <= hi:
        return 0.0
    span = max(hi - lo, 1.0)   # floor at 1.0 for point targets
    if h2m < lo:
        return ((lo - h2m) / span) ** 2
    return ((h2m - hi) / span) ** 2
