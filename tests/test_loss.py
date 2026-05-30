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


# --- G1: Large negative h2m edge case ---


def test_h2m_zero_far_from_target() -> None:
    """When h2m=0 and target range starts far away, loss should be large but finite."""
    t = _range(10, 16)
    # h2m=0 is 10 units below lo=10, span=6
    loss = scenario_loss(0, t, duration=48)
    expected = ((10 - 0) / 6.0) ** 2  # (lo - h2m) / span)^2
    assert abs(loss - expected) < 1e-9


def test_h2m_beyond_duration() -> None:
    """When h2m exceeds duration, loss should be based on distance from hi."""
    t = _range(3, 6)
    # h2m=48 (beyond any realistic duration), hi=6
    loss = scenario_loss(48, t, duration=48)
    expected = ((48 - 6) / 3.0) ** 2  # distance from hi=6, span=3
    assert abs(loss - expected) < 1e-9


# --- G2: Point target span=1.0 exact loss verification ---


def test_point_target_span_uses_one() -> None:
    """Point targets use span=1.0 (not 0) to avoid division by zero."""
    # For a point target at 18, h2m=19 should give loss = ((19-18)/1)^2 = 1.0
    loss = scenario_loss(19, _point(18.0), duration=72)
    assert abs(loss - 1.0) < 1e-9


def test_point_target_loss_formula() -> None:
    """Verify exact loss value for known point target miss."""
    # Point target at 14, h2m=17 → loss = ((17-14)/1)^2 = 9.0
    loss = scenario_loss(17, _point(14.0), duration=48)
    assert abs(loss - 9.0) < 1e-9

    # h2m=12, point target=14 → loss = ((14-12)/1)^2 = 4.0
    loss_left = scenario_loss(12, _point(14.0), duration=48)
    assert abs(loss_left - 4.0) < 1e-9
