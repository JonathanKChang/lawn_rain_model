"""Tests for individual physical regimes in SingleLayerModel.

Each regime (Stage 2 evaporation, Stage 1 evaporation, Pool drainage) has
distinct formulas. Tests verify the correct regime activates at the right
wetness thresholds and produces expected breakdowns.
"""
from __future__ import annotations

import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.weather import WeatherStep


@pytest.fixture
def m() -> SingleLayerModel:
    return SingleLayerModel()


def _step(m, wetness, **weather_kwargs):
    """Convenience: create a weather step and run one model step."""
    ws = WeatherStep(
        hour=0, tod=12, temp=75.0, rh=60.0,
        wind=5.0, clouds=30.0, elevation=45.0, rain_inches=0.0,
        **weather_kwargs,
    )
    state = m.initial_state(wetness)
    return m.step(state, ws, m.default_params)


class TestStage2Evaporation:
    """Stage 2: wetness < stage_thresh (default 18.0).

    Dominant mechanism: soil-limited evaporation.
    Stage factor = wetness / stage_thresh, so evaporation is proportional
    to how much moisture remains below field capacity.
    """

    def test_stage_factor_below_one(self, m: SingleLayerModel) -> None:
        """At wetness=10 (below stage_thresh=18), stage_factor should be < 1."""
        result = _step(m, wetness=10.0)
        assert result["diagnostics"]["stage_factor"] < 1.0
        # Expected: 10.0 / 18.0 ≈ 0.556
        expected = 10.0 / m.default_params["stage_thresh"]
        assert abs(result["diagnostics"]["stage_factor"] - expected) < 1e-9

    def test_stage_factor_zero_at_zero_wetness(self, m: SingleLayerModel) -> None:
        """At wetness=0, stage_factor should be exactly 0."""
        result = _step(m, wetness=0.0)
        assert result["diagnostics"]["stage_factor"] == 0.0

    def test_stage2_no_pool_drain(self, m: SingleLayerModel) -> None:
        """Stage 2 regime should produce zero pool drainage."""
        result = _step(m, wetness=15.0)  # well below pool_thresh=40
        assert result["diagnostics"]["pool_drain_rate"] == 0.0

    def test_stage2_drying_rate_is_linear_in_wetness(self, m: SingleLayerModel) -> None:
        """Since stage_factor is linear in wetness (below thresh),
        doubling wetness should approximately double the evaporation component.
        """
        r1 = _step(m, wetness=5.0)
        r2 = _step(m, wetness=10.0)
        # Evap_rate at 10 should be roughly 2x that at 5
        ratio = r2["diagnostics"]["evap_rate"] / max(r1["diagnostics"]["evap_rate"], 1e-12)
        assert 1.8 < ratio < 2.2  # allow small numerical tolerance

    def test_stage2_vs_stage1_evap_rate(self, m: SingleLayerModel) -> None:
        """Stage 1 (above stage_thresh) should have higher evaporation
        than Stage 2 at the same base conditions, because stage_factor=1."""
        r_stage2 = _step(m, wetness=15.0)  # below thresh
        r_stage1 = _step(m, wetness=25.0)  # above thresh, below pool
        assert r_stage1["diagnostics"]["evap_rate"] > r_stage2["diagnostics"]["evap_rate"]


class TestStage1Evaporation:
    """Stage 1: stage_thresh <= wetness < pool_thresh (18.0 ≤ w < 40.0).

    Dominant mechanism: atmosphere-limited evaporation.
    Stage factor is capped at 1.0, so evaporation runs at full rate
    regardless of how much moisture remains (as long as below pool_thresh).
    """

    def test_stage_factor_capped_at_one(self, m: SingleLayerModel) -> None:
        """At wetness=25 (above stage_thresh=18), stage_factor should be exactly 1.0."""
        result = _step(m, wetness=25.0)
        assert result["diagnostics"]["stage_factor"] == 1.0

    def test_stage1_no_pool_drain(self, m: SingleLayerModel) -> None:
        """Stage 1 regime (below pool_thresh) should produce zero pool drainage."""
        result = _step(m, wetness=35.0)  # above stage_thresh, below pool_thresh=40
        assert result["diagnostics"]["pool_drain_rate"] == 0.0

    def test_stage1_evap_independent_of_wetness(self, m: SingleLayerModel) -> None:
        """In Stage 1, evaporation rate should be constant regardless of wetness
        (stage_factor=1.0, evap formula has no wetness dependency beyond stage_factor)."""
        r_low = _step(m, wetness=20.0)
        r_high = _step(m, wetness=39.0)
        # evap_rate should be identical (stage_factor=1 for both, all other factors same)
        assert r_low["diagnostics"]["evap_rate"] == r_high["diagnostics"]["evap_rate"]

    def test_stage1_capillary_present(self, m: SingleLayerModel) -> None:
        """Stage 1 should still have capillary sink (soil_wetness = min(wetness, pool_thresh))."""
        result = _step(m, wetness=30.0)
        assert result["diagnostics"]["capillary_sink"] > 0.0

    def test_stage1_vs_stage2_total_drying(self, m: SingleLayerModel) -> None:
        """Total drying rate should be higher in Stage 1 than Stage 2
        because Stage 1 has full evaporation + capillary, while Stage 2
        has reduced evaporation + capillary."""
        r_stage2 = _step(m, wetness=15.0)
        r_stage1 = _step(m, wetness=25.0)
        assert r_stage1["drying_rate"] > r_stage2["drying_rate"]


class TestPoolDrainage:
    """Pool regime: wetness >= pool_thresh (default 40.0).

    Dominant mechanism: standing water drainage + Stage 1 evaporation.
    Pool depth = wetness - pool_thresh.
    Pool drain = pool_depth * pool_drain_coef.
    """

    def test_pool_drain_positive_above_thresh(self, m: SingleLayerModel) -> None:
        """At wetness=45 (> pool_thresh=40), pool drainage should be positive."""
        result = _step(m, wetness=45.0)
        assert result["diagnostics"]["pool_drain_rate"] > 0.0
        # Expected: (45 - 40) * 0.12 = 0.6
        expected_pool_drain = 5.0 * m.default_params["pool_drain_coef"]
        assert abs(result["diagnostics"]["pool_drain_rate"] - expected_pool_drain) < 1e-9

    def test_pool_drain_scales_with_depth(self, m: SingleLayerModel) -> None:
        """Pool drain should scale linearly with pool depth."""
        r_shallow = _step(m, wetness=41.0)  # depth=1
        r_deep = _step(m, wetness=51.0)     # depth=11
        assert r_deep["diagnostics"]["pool_drain_rate"] > r_shallow["diagnostics"]["pool_drain_rate"]
        ratio = r_deep["diagnostics"]["pool_drain_rate"] / max(r_shallow["diagnostics"]["pool_drain_rate"], 1e-12)
        # depth ratio is 11:1, pool drain should scale similarly
        assert 10.5 < ratio < 11.5

    def test_pool_regime_still_has_evap(self, m: SingleLayerModel) -> None:
        """Pool regime still has evaporation (Stage 1, stage_factor=1)."""
        result = _step(m, wetness=60.0)
        assert result["diagnostics"]["evap_rate"] > 0.0
        assert result["diagnostics"]["stage_factor"] == 1.0

    def test_pool_regime_still_has_capillary(self, m: SingleLayerModel) -> None:
        """Pool regime still has capillary sink (soil_wetness = min(wetness, pool_thresh))."""
        result = _step(m, wetness=60.0)
        # soil_wetness = min(60, 40) = 40
        expected_soil = m.default_params["pool_thresh"]
        visc_factor = max(
            1.0 - (70.0 - result.get("_temp", 75.0)) * m.default_params["visc_slope"],
            m.default_params["visc_floor"],
        )
        expected_cap = expected_soil * m.default_params["capillary_rate"] * visc_factor
        # Allow small tolerance for rounding
        assert abs(result["diagnostics"]["capillary_sink"] - expected_cap) < 1e-6

    def test_pool_dominates_total_drying(self, m: SingleLayerModel) -> None:
        """At high wetness, pool drainage should be the dominant drying mechanism."""
        result = _step(m, wetness=70.0)
        pool = result["diagnostics"]["pool_drain_rate"]
        evap = result["diagnostics"]["evap_rate"]
        cap = result["diagnostics"]["capillary_sink"]
        assert pool > evap, "Pool drainage should dominate evaporation at high wetness"
        assert pool > cap, "Pool drainage should dominate capillary at high wetness"


class TestBoundaryWetnessValues:
    """Test that the model handles extreme wetness values without producing NaN,
    overflow, or negative results. These are regression tests for boundary conditions."""

    def test_wetness_zero_no_crash(self, m: SingleLayerModel) -> None:
        """Initial state of 0 should produce valid output (no crash, no NaN)."""
        result = _step(m, wetness=0.0)
        assert result["wetness_out"] >= 0.0
        assert result["wetness_out"] == result["wetness_out"]  # not NaN
        assert result["drying_rate"] >= 0.0

    def test_wetness_at_50(self, m: SingleLayerModel) -> None:
        """Mid-range wetness should produce valid output."""
        result = _step(m, wetness=50.0)
        assert result["wetness_out"] >= 0.0
        assert result["wetness_out"] <= 100.0
        assert result["wetness_out"] == result["wetness_out"]  # not NaN
        assert result["drying_rate"] >= 0.0
        assert result["wetness_out"] < 50.0  # should dry (no rain input)

    def test_wetness_99_point_9(self, m: SingleLayerModel) -> None:
        """Near-max wetness should produce valid output without overflow."""
        result = _step(m, wetness=99.9)
        assert result["wetness_out"] >= 0.0
        assert result["wetness_out"] < 99.9  # should dry
        assert result["wetness_out"] == result["wetness_out"]  # not NaN
        # Should have significant pool drain at this level
        assert result["diagnostics"]["pool_drain_rate"] > 0.0

    def test_wetness_at_100(self, m: SingleLayerModel) -> None:
        """Maximum wetness (100) should produce valid output."""
        result = _step(m, wetness=100.0)
        assert result["wetness_out"] >= 0.0
        assert result["wetness_out"] < 100.0  # should dry
        assert result["wetness_out"] == result["wetness_out"]  # not NaN
        # Pool depth = 100 - 40 = 60, drain = 60 * 0.12 = 7.2
        expected_pool_drain = (100.0 - m.default_params["pool_thresh"]) * m.default_params["pool_drain_coef"]
        assert abs(result["diagnostics"]["pool_drain_rate"] - expected_pool_drain) < 1e-6

    def test_wetness_never_negative(self, m: SingleLayerModel) -> None:
        """Wetness should never drop below zero, regardless of input."""
        for w in [0.0, 1.0, 5.0, 20.0, 50.0, 90.0, 100.0]:
            result = _step(m, wetness=w)
            assert result["wetness_out"] >= -1e-9, f"wetness_out negative at input {w}"

    def test_wetness_never_exceeds_100_after_rain(self, m: SingleLayerModel) -> None:
        """Even with massive rain input, wetness should stay <= 100."""
        ws = WeatherStep(
            hour=0, tod=12, temp=75.0, rh=60.0,
            wind=5.0, clouds=30.0, elevation=45.0, rain_inches=10.0,  # extreme
        )
        state = m.initial_state(0.0)
        result = m.step(state, ws, m.default_params)
        assert result["wetness_out"] <= 100.0
        assert result["wetness_out"] == result["wetness_out"]  # not NaN


class TestDiagnosticsCompleteness:
    """Verify that model.step() always returns a complete diagnostics dict
    with the expected keys and valid numeric values."""

    EXPECTED_KEYS = {
        "pre_dry",
        "vpd_norm",
        "sun_factor",
        "wind_factor",
        "stage_factor",
        "evap_rate",
        "pool_drain_rate",
        "capillary_sink",
        "visc_factor",
    }

    def test_all_expected_keys_present(self, m: SingleLayerModel) -> None:
        """Every diagnostics dict must contain all expected keys."""
        result = _step(m, wetness=50.0)
        assert self.EXPECTED_KEYS.issubset(result["diagnostics"].keys())

    def test_all_values_are_finite_floats(self, m: SingleLayerModel) -> None:
        """All diagnostic values must be finite floats (no NaN, no inf)."""
        import math
        for w in [0.0, 5.0, 15.0, 25.0, 45.0, 80.0, 100.0]:
            result = _step(m, wetness=w)
            for key, val in result["diagnostics"].items():
                assert isinstance(val, (int, float)), f"{key} is {type(val)}, not numeric"
                assert math.isfinite(val), f"{key}={val} at wetness={w} is not finite"

    def test_result_keys_always_present(self, m: SingleLayerModel) -> None:
        """Top-level result dict must always have wetness_out, drying_rate, diagnostics."""
        for w in [0.0, 50.0, 100.0]:
            result = _step(m, wetness=w)
            assert "wetness_out" in result
            assert "drying_rate" in result
            assert "diagnostics" in result


class TestDryingRateMonotonicity:
    """Property test: since all drying mechanisms are linear in wetness,
    doubling wetness (within the same regime) should roughly double drying_rate.

    This is a mathematically provable invariant that catches regression
    if any non-linear term is accidentally introduced."""

    def test_drying_rate_increases_with_wetness_stage2(self, m: SingleLayerModel) -> None:
        """In Stage 2 (below thresh), drying_rate should increase monotonically with wetness."""
        prev_rate = 0.0
        for w in [1.0, 5.0, 10.0, 15.0]:
            result = _step(m, wetness=w)
            assert result["drying_rate"] > prev_rate, (
                f"drying_rate not monotonic in Stage 2: {w}→{result['drying_rate']:.4f}, "
                f"prev={prev_rate:.4f}"
            )
            prev_rate = result["drying_rate"]

    def test_drying_rate_increases_with_wetness_stage1(self, m: SingleLayerModel) -> None:
        """In Stage 1 (between thresh and pool), capillary increases with wetness,
        so total drying should still increase monotonically."""
        prev_rate = 0.0
        for w in [20.0, 28.0, 35.0, 39.0]:
            result = _step(m, wetness=w)
            assert result["drying_rate"] > prev_rate, (
                f"drying_rate not monotonic in Stage 1: {w}→{result['drying_rate']:.4f}, "
                f"prev={prev_rate:.4f}"
            )
            prev_rate = result["drying_rate"]

    def test_drying_rate_increases_with_wetness_pool(self, m: SingleLayerModel) -> None:
        """In Pool regime, both pool_drain and capillary increase with wetness."""
        prev_rate = 0.0
        for w in [41.0, 50.0, 60.0, 80.0]:
            result = _step(m, wetness=w)
            assert result["drying_rate"] > prev_rate, (
                f"drying_rate not monotonic in Pool: {w}→{result['drying_rate']:.4f}, "
                f"prev={prev_rate:.4f}"
            )
            prev_rate = result["drying_rate"]

    def test_double_wetness_approx_double_evap_stage2(self, m: SingleLayerModel) -> None:
        """In Stage 2, doubling wetness should approximately double evaporation
        (since stage_factor is linear in wetness)."""
        r1 = _step(m, wetness=4.0)
        r2 = _step(m, wetness=8.0)
        ratio = r2["diagnostics"]["evap_rate"] / max(r1["diagnostics"]["evap_rate"], 1e-12)
        assert 1.9 < ratio < 2.1

    def test_double_wetness_approx_double_capillary_stage1(self, m: SingleLayerModel) -> None:
        """In Stage 1, evaporation is independent of wetness (stage_factor=1).
        But capillary IS linear, so verify evap stays constant while capillary increases."""
        r_low = _step(m, wetness=20.0)
        r_high = _step(m, wetness=40.0)  # just at pool_thresh boundary
        # Evap stays constant (stage_factor=1 for both)
        assert abs(r_low["diagnostics"]["evap_rate"] - r_high["diagnostics"]["evap_rate"]) < 1e-9
        # But capillary increases (proportional to soil_wetness = min(w, pool_thresh))
        ratio_cap = r_high["diagnostics"]["capillary_sink"] / max(r_low["diagnostics"]["capillary_sink"], 1e-12)
        # soil_wetness = min(w, pool_thresh) so ratio ≈ 40/20 = 2
        assert ratio_cap > 1.8
