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
