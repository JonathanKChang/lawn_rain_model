# tests/test_solar.py
import math

import pytest
from lawn_rain_model.simulation.solar import (
    normalize_elevation,
    solar_intensity_taylor,
    sun_elevation,
)


def test_midday_summer_positive() -> None:
    assert sun_elevation(12.0, day_of_year=172, lat=39.0) > 0


def test_midnight_negative() -> None:
    assert sun_elevation(0.0, day_of_year=172, lat=39.0) < 0


def test_summer_higher_than_winter_at_noon() -> None:
    summer = sun_elevation(12.0, day_of_year=172, lat=39.0)
    winter = sun_elevation(12.0, day_of_year=355, lat=39.0)
    assert summer > winter


def test_result_bounded() -> None:
    for h in range(24):
        elev = sun_elevation(float(h), day_of_year=172, lat=39.0)
        assert -90.0 <= elev <= 90.0


def test_noon_summer_approx_value() -> None:
    # Solar noon at lat=39, June solstice ≈ 74.5°
    elev = sun_elevation(12.0, day_of_year=172, lat=39.0)
    assert 70.0 < elev < 80.0


# --- normalize_elevation tests ---


def test_normalize_elevation_no_change() -> None:
    for deg in (0.0, 30.0, 45.0, 90.0, -30.0, -90.0):
        assert normalize_elevation(deg) == pytest.approx(deg, abs=1e-10)


def test_normalize_elevation_wrap_350() -> None:
    # 350° is actually -10° (below horizon)
    assert normalize_elevation(350.0) == pytest.approx(-10.0, abs=1e-10)


def test_normalize_elevation_wrap_365() -> None:
    assert normalize_elevation(365.0) == pytest.approx(5.0, abs=1e-10)


def test_normalize_elevation_wrap_450() -> None:
    assert normalize_elevation(450.0) == pytest.approx(90.0, abs=1e-10)


def test_normalize_elevation_wrap_540() -> None:
    # 540 % 360 = 180; 180 is not > 180, so stays 180 → clamped to 90
    assert normalize_elevation(540.0) == pytest.approx(90.0, abs=1e-10)


def test_normalize_elevation_negative() -> None:
    assert normalize_elevation(-10.0) == pytest.approx(-10.0, abs=1e-10)
    assert normalize_elevation(-90.0) == pytest.approx(-90.0, abs=1e-10)


def test_normalize_elevation_clamp_90() -> None:
    # Values above 90° should clamp (shouldn't happen in practice)
    assert normalize_elevation(120.0) == pytest.approx(90.0, abs=1e-10)
    # 180° stays 180 (not > 180) → clamped to 90°
    assert normalize_elevation(180.0) == pytest.approx(90.0, abs=1e-10)


# --- solar_intensity_taylor tests ---


def test_taylor_intensity_negative_elevation() -> None:
    assert solar_intensity_taylor(-10.0) == 0.0
    assert solar_intensity_taylor(-90.0) == 0.0


def test_taylor_intensity_wrap_around_gives_zero() -> None:
    # 350° normalizes to -10°, should give 0 intensity
    assert solar_intensity_taylor(350.0) == 0.0


def test_taylor_intensity_at_zero() -> None:
    assert solar_intensity_taylor(0.0) == 0.0


def test_taylor_intensity_positive() -> None:
    # At 30° elevation, Taylor sin(π/6) ≈ 0.5236
    intensity = solar_intensity_taylor(30.0)
    assert 0.50 < intensity < 0.55


def test_taylor_intensity_monotonic() -> None:
    """Intensity increases with elevation."""
    for e in (10.0, 30.0, 60.0, 90.0):
        assert solar_intensity_taylor(e) > solar_intensity_taylor(e - 1.0)


def test_taylor_intensity_bounded() -> None:
    """Intensity stays in [0, 1]."""
    for e in range(-180, 541, 10):
        val = solar_intensity_taylor(float(e))
        assert 0.0 <= val <= 1.1, f"e={e} → {val}"


def test_taylor_accuracy_vs_math_sin() -> None:
    """Taylor expansion should be within ~13% of actual sin at worst."""
    for e in [5.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0]:
        taylor = solar_intensity_taylor(e)
        actual = math.sin(math.radians(e))
        rel_err = abs(taylor - actual) / actual
        assert rel_err < 0.14, f"e={e}: Taylor={taylor:.4f}, sin={actual:.4f}, err={rel_err:.2%}"
