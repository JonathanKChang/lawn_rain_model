# tests/test_single_layer.py
from __future__ import annotations
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.weather import WeatherStep


def make_step(
    rain: float = 0.0, temp: float = 75.0, rh: float = 60.0,
    wind: float = 5.0, clouds: float = 30.0, elevation: float = 45.0,
) -> WeatherStep:
    return WeatherStep(
        hour=0, tod=12, temp=temp, rh=rh,
        wind=wind, clouds=clouds, elevation=elevation, rain_inches=rain,
    )


@pytest.fixture
def m() -> SingleLayerModel:
    return SingleLayerModel()


def test_no_rain_wetness_decreases(m: SingleLayerModel) -> None:
    p = m.default_params
    result = m.step(m.initial_state(20.0), make_step(rain=0.0), p)
    assert result["wetness_out"] < 20.0


def test_rain_adds_wetness(m: SingleLayerModel) -> None:
    p = m.default_params
    result = m.step(m.initial_state(0.0), make_step(rain=1.0), p)
    assert result["wetness_out"] > 0.0


def test_wetness_capped_at_100(m: SingleLayerModel) -> None:
    p = m.default_params
    result = m.step(m.initial_state(0.0), make_step(rain=10.0), p)
    assert result["wetness_out"] <= 100.0


def test_wetness_floor_at_zero(m: SingleLayerModel) -> None:
    p = m.default_params
    result = m.step(m.initial_state(0.0), make_step(rain=0.0), p)
    assert result["wetness_out"] >= 0.0


def test_surface_wetness_returns_state(m: SingleLayerModel) -> None:
    assert m.surface_wetness(m.initial_state(25.0)) == 25.0


def test_hot_dry_dries_faster_than_cool_humid(m: SingleLayerModel) -> None:
    p = m.default_params
    hot = make_step(temp=85, rh=30, wind=10, clouds=10, elevation=60)
    cool = make_step(temp=50, rh=80, wind=3, clouds=90, elevation=10)
    state = m.initial_state(30.0)
    hot_r = m.step(state, hot, p)
    cool_r = m.step(state, cool, p)
    assert hot_r["drying_rate"] > cool_r["drying_rate"]


def test_cold_reduces_capillary_via_visc(m: SingleLayerModel) -> None:
    p = m.default_params
    cold_w = make_step(temp=38)
    warm_w = make_step(temp=70)
    state = m.initial_state(30.0)
    cold_r = m.step(state, cold_w, p)
    warm_r = m.step(state, warm_w, p)
    assert cold_r["diagnostics"]["visc_factor"] < warm_r["diagnostics"]["visc_factor"]


def test_night_no_solar(m: SingleLayerModel) -> None:
    p = m.default_params
    night = make_step(elevation=-10.0)
    result = m.step(m.initial_state(20.0), night, p)
    assert result["diagnostics"]["sun_factor"] == 0.0


def test_result_required_keys(m: SingleLayerModel) -> None:
    result = m.step(m.initial_state(10.0), make_step(), m.default_params)
    assert "wetness_out" in result
    assert "drying_rate" in result
    assert "diagnostics" in result


def test_protocol_compliance(m: SingleLayerModel) -> None:
    # Structural: all Protocol attributes present
    assert hasattr(m, "default_params")
    assert hasattr(m, "param_bounds")
    assert callable(m.initial_state)
    assert callable(m.surface_wetness)
    assert callable(m.step)


def test_default_params_and_bounds_same_keys(m: SingleLayerModel) -> None:
    assert set(m.default_params.keys()) == set(m.param_bounds.keys())


def test_pool_drain_zero_below_pool_thresh(m: SingleLayerModel) -> None:
    p = m.default_params
    # wetness well below pool_thresh (40.0 default)
    result = m.step(m.initial_state(10.0), make_step(), p)
    assert result["diagnostics"]["pool_drain_rate"] == 0.0


def test_pool_drain_positive_above_pool_thresh(m: SingleLayerModel) -> None:
    p = m.default_params
    # wetness above pool_thresh (40.0 default)
    result = m.step(m.initial_state(0.0), make_step(rain=2.0), p)
    # 2.0 * 40.0 = 80.0 > pool_thresh
    assert result["diagnostics"]["pool_drain_rate"] > 0.0


# --- Parameter validation tests ---


def test_validate_params_valid(m: SingleLayerModel) -> None:
    """Default params pass validation."""
    errors = m.validate_params(m.default_params)
    assert errors == []


def test_validate_params_out_of_bounds(m: SingleLayerModel) -> None:
    """Params outside bounds produce errors."""
    p = m.default_params.copy()
    p["base_evap"] = 0.99  # max is 0.20
    errors = m.validate_params(p)
    assert any("base_evap" in e for e in errors)


def test_validate_params_stage_ge_pool(m: SingleLayerModel) -> None:
    """stage_thresh >= pool_thresh produces an ordering error."""
    p = m.default_params.copy()
    p["stage_thresh"] = 50.0  # pool_thresh is 40.0
    errors = m.validate_params(p)
    assert any("stage_thresh" in e for e in errors)


def test_validate_params_missing_key(m: SingleLayerModel) -> None:
    """Missing required parameters produce errors."""
    p = {k: v for k, v in m.default_params.items() if k != "base_evap"}
    errors = m.validate_params(p)
    assert any("base_evap" in e for e in errors)
