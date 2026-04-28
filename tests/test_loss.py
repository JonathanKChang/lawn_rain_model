# tests/test_loss.py
import pytest
from lawn_rain_model.calibration.loss import scenario_loss
from lawn_rain_model.calibration.scenarios import CalibrationTarget


def _range(lo: float, hi: float, weight: float = 1.0) -> CalibrationTarget:
    return CalibrationTarget(target_hours_min=lo, target_hours_max=hi, weight=weight)


def _point(t: float, weight: float = 1.0) -> CalibrationTarget:
    return CalibrationTarget(target_hours_min=t, target_hours_max=t, weight=weight)


def test_within_range_zero() -> None:
    assert scenario_loss(4, _range(3, 6), duration=48) == 0.0


def test_at_lower_boundary_zero() -> None:
    assert scenario_loss(3, _range(3, 6), duration=48) == 0.0


def test_at_upper_boundary_zero() -> None:
    assert scenario_loss(6, _range(3, 6), duration=48) == 0.0


def test_too_fast_positive() -> None:
    assert scenario_loss(2, _range(10, 16), duration=48) > 0.0


def test_too_slow_positive() -> None:
    assert scenario_loss(20, _range(3, 6), duration=48) > 0.0


def test_further_miss_is_larger_loss() -> None:
    t = _range(10, 16)
    assert scenario_loss(20, t, 48) < scenario_loss(30, t, 48)


def test_never_uses_duration() -> None:
    t = _range(3, 6)
    assert scenario_loss(None, t, 48) == scenario_loss(48, t, 48)


def test_point_target_exact_zero() -> None:
    assert scenario_loss(18, _point(18.0), duration=72) == 0.0


def test_point_target_miss_positive() -> None:
    assert scenario_loss(20, _point(18.0), duration=72) > 0.0


def test_point_target_no_division_by_zero() -> None:
    # span would be 0; must not raise
    loss = scenario_loss(19, _point(18.0), duration=72)
    assert loss > 0.0


def test_weight_zero_still_computes() -> None:
    # weight=0 is applied by the optimizer, not inside scenario_loss itself
    t = _range(8, 14, weight=0)
    assert scenario_loss(33, t, 48) > 0.0
