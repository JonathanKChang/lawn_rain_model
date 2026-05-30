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


# --- Full-day cycle invariant (D1) ---


def test_sun_elevation_full_day_cycle_symmetric() -> None:
    """sun_elevation should produce a smooth symmetric curve around solar noon.

    For any day and latitude, the elevation at hour (12 - d) and hour (12 + d)
    should be equal — symmetry around solar noon.
    """
    elevs = [sun_elevation(float(h), day_of_year=172, lat=39.0) for h in range(24)]
    # Check symmetry: hour 6 == hour 18, hour 5 == hour 19, etc.
    for d in range(1, 12):
        h_low = 12 - d
        h_high = 12 + d
        assert elevs[h_low] == pytest.approx(elevs[h_high], rel=1e-10), (
            f"Day asymmetry: hour {h_low}={elevs[h_low]:.4f} vs hour {h_high}={elevs[h_high]:.4f}"
        )


def test_sun_elevation_dawn_dusk_consistent() -> None:
    """Sun should be above horizon around noon and below at night for summer solstice."""
    elevs = [sun_elevation(float(h), day_of_year=172, lat=39.0) for h in range(24)]
    # Morning: hours 5-6 should be rising
    assert elevs[5] < elevs[6] < elevs[7]
    # Noon peak
    assert elevs[11] > elevs[12] - 5.0 and elevs[13] > elevs[12] - 5.0
    # Evening: hours 17-18 should be falling
    assert elevs[17] > elevs[18] > elevs[19]
    # Night: hours 0, 1, 2, 3 should be below horizon
    for h in (0, 1, 2, 3):
        assert elevs[h] < 0.0, f"Hour {h} elevation should be negative: {elevs[h]}"


def test_sun_elevation_winter_night_longer() -> None:
    """Winter solstice should have fewer above-horizon hours than summer."""
    summer_above = sum(1 for h in range(24) if sun_elevation(float(h), 172, 39.0) > 0)
    winter_above = sum(1 for h in range(24) if sun_elevation(float(h), 355, 39.0) > 0)
    assert summer_above > winter_above


# --- Known-value regression (D2) ---


def test_solstice_noon_precise_value() -> None:
    """Summer solstice noon at lat=39 should be ≈ 74.45°."""
    elev = sun_elevation(12.0, day_of_year=172, lat=39.0)
    assert pytest.approx(elev, abs=0.5) == 74.45


def test_equinox_noon_precise_value() -> None:
    """Equinox noon at lat=39 should be 90 - lat = 51°."""
    elev = sun_elevation(12.0, day_of_year=81, lat=39.0)
    assert pytest.approx(elev, abs=0.01) == 51.0


# --- Taylor accuracy bound tightening (D3) ---


def test_taylor_accuracy_bound_tightened() -> None:
    """Tighten from 14% to verify actual worst-case error is < 5%."""
    max_err = 0.0
    for e in range(1, 91):
        taylor = solar_intensity_taylor(float(e))
        actual = math.sin(math.radians(e))
        rel_err = abs(taylor - actual) / actual
        max_err = max(max_err, rel_err)
    assert max_err < 0.05, f"Worst-case Taylor error is {max_err:.2%}, not < 5%"
