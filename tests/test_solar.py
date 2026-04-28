# tests/test_solar.py
from lawn_rain_model.simulation.solar import sun_elevation


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
