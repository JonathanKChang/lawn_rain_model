"""Tests for the display module (cli/display.py).

Previously zero coverage. Tests the sparkline visualization logic.
"""
from __future__ import annotations

import pytest
from lawn_rain_model.cli.display import sparkline, BAR_WIDTH


class TestSparkline:
    """Test sparkline rendering with boundary values and thresholds."""

    def _stage_idx(self, stage_thresh: float = 18.0) -> int:
        return int(stage_thresh / 100.0 * BAR_WIDTH)

    def _pool_idx(self, pool_thresh: float = 40.0) -> int:
        return int(pool_thresh / 100.0 * BAR_WIDTH)

    def test_sparkline_zero_all_dots_with_markers(self) -> None:
        """Wetness 0.0: all dots except threshold positions get pipe markers."""
        result = sparkline(0.0)
        stage_i = self._stage_idx()
        pool_i = self._pool_idx()
        for i, ch in enumerate(result):
            if i == stage_i:
                assert ch == "|"
            elif i == pool_i:
                assert ch == "|"
            else:
                assert ch == "\u00b7", f"Non-dot at idx {i}: {repr(ch)}"

    def test_sparkline_100_all_bars_no_markers(self) -> None:
        """Wetness 100.0: all bars, no markers (thresholds fall in bar region)."""
        result = sparkline(100.0)
        assert result.count("\u2588") == BAR_WIDTH
        assert "|" not in result

    def test_sparkline_50_half_bars_half_dots_no_markers(self) -> None:
        """Wetness 50.0: half bars, half dots. Markers fall in bar region (not replaced)."""
        result = sparkline(50.0)
        assert result.count("\u2588") == BAR_WIDTH // 2
        assert result.count("\u00b7") == BAR_WIDTH // 2
        assert "|" not in result

    def test_sparkline_nan_placeholder(self) -> None:
        """NaN input should return placeholder with question marks."""
        result = sparkline(float("nan"))
        assert result == "[" + "?" * BAR_WIDTH + "]"

    def test_sparkline_negative_clamped_like_zero(self) -> None:
        """Negative wetness clamps to 0 — same output as 0.0."""
        assert sparkline(-5.0) == sparkline(0.0)

    def test_sparkline_above_100_clamped_to_full(self) -> None:
        """Wetness above 100 clamps to all bars, no markers."""
        result = sparkline(120.0)
        assert result.count("\u2588") == BAR_WIDTH
        assert "|" not in result

    def test_sparkline_threshold_in_dot_region_replaces(self) -> None:
        """When threshold falls on a dot, it is replaced with pipe marker."""
        # wetness=35: stage_idx=7 (bar region), pool_idx=16 (dot region)
        result = sparkline(35.0)
        stage_i = self._stage_idx()  # 7
        pool_i = self._pool_idx()    # 16
        assert result[stage_i] == "\u2588"   # in bar region
        assert result[pool_i] == "|"         # in dot region, replaced

    def test_sparkline_threshold_in_bar_region_unchanged(self) -> None:
        """When threshold falls on a bar, it stays as bar (not replaced)."""
        result = sparkline(50.0)
        stage_i = self._stage_idx()
        pool_i = self._pool_idx()
        # Both in bar region (positions 0-19)
        assert result[stage_i] == "\u2588"
        assert result[pool_i] == "\u2588"

    def test_sparkline_custom_thresholds(self) -> None:
        """Custom thresholds produce markers at correct custom positions."""
        # Use low wetness so both custom thresholds fall in dot region
        result = sparkline(5.0, stage_thresh=20.0, pool_thresh=60.0)
        stage_i = int(20.0 / 100.0 * BAR_WIDTH)   # = 8 (dots start at pos 2)
        pool_i = int(60.0 / 100.0 * BAR_WIDTH)    # = 24
        assert result[stage_i] == "|"
        assert result[pool_i] == "|"

    def test_sparkline_length(self) -> None:
        """Output should always be exactly BAR_WIDTH chars (plus brackets for NaN)."""
        assert len(sparkline(50.0)) == BAR_WIDTH
        assert len(sparkline(0.0)) == BAR_WIDTH
        assert len(sparkline(100.0)) == BAR_WIDTH
        assert len(sparkline(float("nan"))) == BAR_WIDTH + 2  # brackets

    def test_sparkline_produces_valid_unicode(self) -> None:
        """Output should only contain valid characters."""
        for v in [0.0, 25.0, 50.0, 75.0, 100.0]:
            result = sparkline(v)
            for ch in result:
                assert ch in ("\u2588", "\u00b7", "|"), f"Unexpected char {repr(ch)} at wetness={v}"

    def test_sparkline_progressive_bars(self) -> None:
        """Increasing wetness should progressively add bars from left."""
        r0 = sparkline(0.0)
        r25 = sparkline(25.0)
        r75 = sparkline(75.0)
        # Position 0: always a bar for w>=3%
        assert r25[0] == "\u2588"
        assert r75[0] == "\u2588"
        # Position 39: never a bar (would need 97.5+)
        assert r0[39] == "\u00b7"
        assert r25[39] == "\u00b7"
