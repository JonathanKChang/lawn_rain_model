# Lawn Wetness Index — Refactor + History Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `simulator.py` into a typed, testable package with a Protocol-based model
interface, then add support for real-world HA history files as calibration scenarios with
point-target scoring.

**Architecture:** A `LawnModel` structural Protocol (PEP 544) defines the contract any model must
satisfy — `SingleLayerModel` is the first implementation. The runner is model-agnostic: it
consumes `WeatherStep` objects regardless of whether they came from YAML fixed conditions or a
resampled HA history CSV. Scenario YAML gains `history_file` + `target_hours` (point target) as
optional fields alongside the existing range-target and synthetic-weather paths.

**Tech Stack:** Python 3.11+, `pyyaml`, `numpy`, `scipy`, `pandas` (new — for history
resampling), `pytest`, `mypy`

---

## File Map

**Created (new package):**
```
lawn_rain_model/
  __init__.py
  models/
    __init__.py
    protocol.py          # LawnModel Protocol, WeatherStep used as forward ref
    single_layer.py      # SingleLayerModel: all physics from current step()
  simulation/
    __init__.py
    solar.py             # sun_elevation() — unchanged logic
    weather.py           # WeatherStep dataclass, resample_history(), DEFAULT_SENSOR_MAP
    runner.py            # run_scenario(), hours_to_mow() — model-agnostic
  calibration/
    __init__.py
    scenarios.py         # Scenario, CalibrationTarget, WeatherConditions, RainEvent, ScenarioLoader
    loss.py              # scenario_loss() — handles point (min==max) + range targets
    optimizer.py         # run_optimizer(), build_objective(), print_optimizer_report()
  cli/
    __init__.py
    display.py           # print_table(), print_summary(), sparkline(), print_jinja2()
    commands.py          # cmd_simulate(), cmd_sweep(), cmd_optimize(), build_parser()
tests/
  conftest.py
  fixtures/
    history_simple.csv   # 3-hour synthetic HA export for resampler tests
    history_midnight.csv # midnight-reset edge case
  test_single_layer.py
  test_solar.py
  test_runner.py
  test_loss.py
  test_scenarios.py
  test_resampler.py
  test_history_runner.py
pyproject.toml
simulator.py             # MODIFIED: thin entry point, delegates to lawn_rain_model.cli.commands
```

**Modified:**
- `simulator.py` — gutted to 5 lines
- `scenarios.yaml` — cold/night target stays weight=0; no other changes required by this plan
  (history scenarios are new entries you add manually after the pipeline works)

---

## Task 1: Package Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `lawn_rain_model/__init__.py` and all `__init__.py` stubs
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "lawn_rain_model"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "numpy>=1.26",
    "scipy>=1.12",
    "pandas>=2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "mypy>=1.10",
    "pandas-stubs>=2.2",
]

[project.scripts]
lawn_rain_model = "lawn_rain_model.cli.commands:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["lawn_rain_model*"]

[tool.mypy]
strict = true
ignore_missing_imports = false
```

- [ ] **Step 2: Create all `__init__.py` stubs**

```bash
mkdir -p lawn_rain_model/models lawn_rain_model/simulation lawn_rain_model/calibration lawn_rain_model/cli
mkdir -p tests/fixtures
touch lawn_rain_model/__init__.py
touch lawn_rain_model/models/__init__.py
touch lawn_rain_model/simulation/__init__.py
touch lawn_rain_model/calibration/__init__.py
touch lawn_rain_model/cli/__init__.py
touch tests/__init__.py
```

Each `__init__.py` is empty for now.

- [ ] **Step 3: Create `tests/conftest.py`**

```python
# tests/conftest.py
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.weather import WeatherStep


@pytest.fixture
def model() -> SingleLayerModel:
    return SingleLayerModel()


@pytest.fixture
def default_params(model: SingleLayerModel) -> dict[str, float]:
    return model.default_params


@pytest.fixture
def dry_step() -> WeatherStep:
    return WeatherStep(
        hour=0, tod=12, temp=75.0, rh=60.0,
        wind=5.0, clouds=30.0, elevation=45.0, rain_inches=0.0,
    )


@pytest.fixture
def rainy_step() -> WeatherStep:
    return WeatherStep(
        hour=0, tod=12, temp=70.0, rh=80.0,
        wind=3.0, clouds=70.0, elevation=30.0, rain_inches=1.0,
    )
```

- [ ] **Step 4: Install in editable mode**

```bash
pip install -e ".[dev]"
```

Expected: no errors; `lawn_rain_model` importable from any directory.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml lawn_rain_model/ tests/conftest.py
git commit -m "chore: scaffold lawn_rain_model package structure"
```

---

## Task 2: WeatherStep + LawnModel Protocol

**Files:**
- Create: `lawn_rain_model/simulation/weather.py` (WeatherStep only, no resampler yet)
- Create: `lawn_rain_model/models/protocol.py`

> No test task here — these are pure type definitions. Protocol conformance is verified in
> Task 3's `test_protocol_compliance` test.

- [ ] **Step 1: Create `lawn_rain_model/simulation/weather.py`**

```python
# lawn_rain_model/simulation/weather.py
"""WeatherStep and history resampling. resample_history() is added in Task 11."""
from __future__ import annotations
from dataclasses import dataclass

# Mapping from logical field name → HA entity_id.
# Override per-scenario in YAML under history_sensor_map:.
DEFAULT_SENSOR_MAP: dict[str, str] = {
    "temp":               "sensor.pirateweather_temperature_0h",
    "rh":                 "sensor.pirateweather_humidity_0h",
    "wind":               "sensor.pirateweather_wind_speed",
    "clouds":             "sensor.pirateweather_cloud_coverage",
    "elevation":          "sensor.sun_elevation",
    "liquid_accumulation": "sensor.pirateweather_current_day_liquid_accumulation",
}


@dataclass(frozen=True)
class WeatherStep:
    """One hour of weather conditions fed to the model."""
    hour: int           # simulation index (0, 1, 2, ...)
    tod: int            # time of day 0–23
    temp: float         # °F
    rh: float           # relative humidity 0–100
    wind: float         # mph
    clouds: float       # 0–100
    elevation: float    # solar elevation angle, degrees
    rain_inches: float  # rain that fell during this hour
```

- [ ] **Step 2: Create `lawn_rain_model/models/protocol.py`**

```python
# lawn_rain_model/models/protocol.py
"""
LawnModel structural Protocol (PEP 544).

Any class with these five attributes/methods satisfies LawnModel — no inheritance required.
State is model-defined: SingleLayerModel uses float; a future multi-layer model uses
list[float] or np.ndarray. The Protocol does not constrain state shape.
"""
from __future__ import annotations
from typing import Any, Protocol
from lawn_rain_model.simulation.weather import WeatherStep


class LawnModel(Protocol):
    @property
    def default_params(self) -> dict[str, float]:
        """Parameter dict used when none is supplied by the caller."""
        ...

    @property
    def param_bounds(self) -> dict[str, tuple[float, float]]:
        """Optimizer search bounds keyed by the same names as default_params."""
        ...

    def initial_state(self, initial_wetness: float) -> Any:
        """Construct the model's state from a scalar wetness value (0–100)."""
        ...

    def surface_wetness(self, state: Any) -> float:
        """Extract the mow-relevant surface wetness scalar from state (0–100)."""
        ...

    def step(
        self,
        state: Any,
        weather: WeatherStep,
        params: dict[str, float],
    ) -> dict[str, float]:
        """
        Advance state by one hour.

        Must include in the returned dict:
          wetness_out  float   surface wetness after this step (0–100)
          drying_rate  float   total drying applied this step
          diagnostics  dict[str, float]   model-specific breakdown for display/CSV
        """
        ...
```

- [ ] **Step 3: Commit**

```bash
git add lawn_rain_model/simulation/weather.py lawn_rain_model/models/protocol.py
git commit -m "feat: WeatherStep dataclass and LawnModel Protocol"
```

---

## Task 3: SingleLayerModel

**Files:**
- Create: `lawn_rain_model/models/single_layer.py`
- Create: `tests/test_single_layer.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_single_layer.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'lawn_rain_model.models.single_layer'`

- [ ] **Step 3: Implement `lawn_rain_model/models/single_layer.py`**

```python
# lawn_rain_model/models/single_layer.py
"""
Single-layer surface wetness model.

Mirrors the Home Assistant Jinja2 model exactly.
All rate constants assume a 1-hour update interval.
"""
from __future__ import annotations
import math
from lawn_rain_model.simulation.weather import WeatherStep

_DEFAULT_PARAMS: dict[str, float] = {
    "base_evap":       0.06,
    "vpd_norm_denom":  0.40,
    "e_sat_base":      1.0393,
    "vpd_min":         0.02,
    "sun_coeff":       0.18,
    "cloud_exp":       1.40,
    "solar_exp":       0.70,
    "wind_coeff":      0.022,
    "wind_cap":        0.50,
    "stage_thresh":    18.0,
    "pool_thresh":     40.0,
    "capillary_rate":  0.05,
    "pool_drain_coef": 0.12,
    "rain_mult":       40.0,
    "visc_slope":      0.015,
    "visc_floor":      0.35,
}

_PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "base_evap":       (0.01,  0.20),
    "vpd_norm_denom":  (0.15,  0.80),
    "e_sat_base":      (1.020, 1.060),
    "vpd_min":         (0.005, 0.05),
    "sun_coeff":       (0.05,  0.50),
    "cloud_exp":       (0.50,  2.50),
    "solar_exp":       (0.30,  1.20),
    "wind_coeff":      (0.005, 0.06),
    "wind_cap":        (0.20,  1.00),
    "stage_thresh":    (8.0,   30.0),
    "pool_thresh":     (25.0,  60.0),
    "capillary_rate":  (0.02,  0.35),
    "pool_drain_coef": (0.05,  0.40),
    "rain_mult":       (20.0,  70.0),
    "visc_slope":      (0.005, 0.030),
    "visc_floor":      (0.20,  0.60),
}


class SingleLayerModel:
    """
    Single scalar wetness index (0–100).

    State is a bare float. surface_wetness() is the identity function.
    """

    @property
    def default_params(self) -> dict[str, float]:
        return dict(_DEFAULT_PARAMS)

    @property
    def param_bounds(self) -> dict[str, tuple[float, float]]:
        return dict(_PARAM_BOUNDS)

    def initial_state(self, initial_wetness: float) -> float:
        return float(initial_wetness)

    def surface_wetness(self, state: float) -> float:
        return state

    def step(
        self,
        state: float,
        weather: WeatherStep,
        params: dict[str, float],
    ) -> dict[str, float]:
        p = params
        wetness = state

        # Rain input (capped at 100)
        pre_dry = min(wetness + weather.rain_inches * p["rain_mult"], 100.0)

        # VPD
        e_sat_rel = p["e_sat_base"] ** (weather.temp - 60)
        vpd_raw   = e_sat_rel * ((100 - weather.rh) / 100.0)
        vpd       = max(vpd_raw, p["vpd_min"])
        vpd_norm  = vpd / p["vpd_norm_denom"]

        # Solar
        cloud_factor = ((100 - weather.clouds) / 100) ** p["cloud_exp"]
        if weather.elevation > 0:
            solar_intensity = (weather.elevation / 90) ** p["solar_exp"]
        else:
            solar_intensity = 0.0
        sun_factor = p["sun_coeff"] * cloud_factor * solar_intensity

        # Wind
        wind_factor = min(weather.wind * p["wind_coeff"], p["wind_cap"])

        # Stage 1/2 transition
        stage_factor = min(pre_dry / p["stage_thresh"], 1.0)

        # Evaporation
        evap_rate = (p["base_evap"] + wind_factor + sun_factor) * vpd_norm * stage_factor

        # Pooling
        pool_depth = max(pre_dry - p["pool_thresh"], 0.0)
        pool_drain = pool_depth * p["pool_drain_coef"]

        # Capillary sink with viscosity correction
        soil_wetness   = min(pre_dry, p["pool_thresh"])
        visc_factor    = max(1.0 - (70.0 - weather.temp) * p["visc_slope"], p["visc_floor"])
        capillary_sink = soil_wetness * p["capillary_rate"] * visc_factor

        drying_rate = pool_drain + capillary_sink + evap_rate
        wetness_out = max(pre_dry - drying_rate, 0.0)

        return {
            "wetness_out": wetness_out,
            "drying_rate": drying_rate,
            "diagnostics": {
                "pre_dry":         pre_dry,
                "vpd_norm":        vpd_norm,
                "sun_factor":      sun_factor,
                "wind_factor":     wind_factor,
                "stage_factor":    stage_factor,
                "evap_rate":       evap_rate,
                "pool_drain_rate": pool_drain,
                "capillary_sink":  capillary_sink,
                "visc_factor":     visc_factor,
            },
        }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_single_layer.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lawn_rain_model/models/single_layer.py tests/test_single_layer.py
git commit -m "feat: SingleLayerModel with Protocol-compliant interface"
```

---

## Task 4: Solar Model

**Files:**
- Create: `lawn_rain_model/simulation/solar.py`
- Create: `tests/test_solar.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_solar.py -v 2>&1 | head -5
```

Expected: `ModuleNotFoundError: No module named 'lawn_rain_model.simulation.solar'`

- [ ] **Step 3: Implement `lawn_rain_model/simulation/solar.py`**

```python
# lawn_rain_model/simulation/solar.py
"""Solar elevation angle model. Ported unchanged from simulator.py."""
import math


def sun_elevation(hour_of_day: float, day_of_year: int = 172, lat: float = 39.0) -> float:
    """Return sun elevation in degrees. Negative = below horizon."""
    declination = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
    hour_angle  = 15.0 * (hour_of_day - 12.0)
    lat_r = math.radians(lat)
    dec_r = math.radians(declination)
    ha_r  = math.radians(hour_angle)
    sin_elev = (
        math.sin(lat_r) * math.sin(dec_r)
        + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r)
    )
    return math.degrees(math.asin(max(min(sin_elev, 1.0), -1.0)))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_solar.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lawn_rain_model/simulation/solar.py tests/test_solar.py
git commit -m "feat: solar elevation model"
```

---

## Task 5: Simulation Runner

**Files:**
- Create: `lawn_rain_model/simulation/runner.py`
- Create: `tests/test_runner.py`

The runner assembles `WeatherStep` objects from either a fixed `WeatherConditions` block +
solar model, or a pre-built list from the history resampler (added Task 12). It calls the
model's `step()` and augments the result with runner-level fields (`hour`, `tod`, `can_mow`,
`elevation`, `rain_inches`, `wetness_in`).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_runner.py
from __future__ import annotations
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow
from lawn_rain_model.calibration.scenarios import (
    Scenario, WeatherConditions, RainEvent,
)


def _hot_dry_scenario() -> Scenario:
    return Scenario(
        name="test_hot_dry",
        duration_hours=48,
        rain_events=[RainEvent(hour=0, inches=1.0)],
        weather=WeatherConditions(temp=85, rh=30, wind=10, clouds=10),
        use_solar_model=True,
        start_hour=8,
        day_of_year=172,
        latitude=39.0,
        mow_threshold=5.0,
    )


def _cool_overcast_scenario() -> Scenario:
    return Scenario(
        name="test_cool",
        duration_hours=96,
        rain_events=[RainEvent(hour=0, inches=1.0)],
        weather=WeatherConditions(temp=50, rh=80, wind=3, clouds=90),
        use_solar_model=True,
        start_hour=8,
        day_of_year=172,
        latitude=39.0,
        mow_threshold=5.0,
    )


@pytest.fixture
def model() -> SingleLayerModel:
    return SingleLayerModel()


def test_output_length(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    assert len(rows) == s.duration_hours


def test_first_hour_rain(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    assert rows[0]["rain_inches"] == 1.0


def test_non_rain_hours_zero(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    for r in rows[1:]:
        assert r["rain_inches"] == 0.0


def test_hour_sequence(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    for i, r in enumerate(rows):
        assert r["hour"] == i


def test_tod_wraps_correctly(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()  # start_hour=8
    rows = run_scenario(s, model, model.default_params)
    assert rows[0]["tod"] == 8
    assert rows[16]["tod"] == (8 + 16) % 24  # = 0


def test_can_mow_uses_threshold(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    for r in rows:
        assert r["can_mow"] == (r["wetness_out"] <= s.mow_threshold)


def test_required_row_keys(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    required = {"hour", "tod", "can_mow", "elevation", "rain_inches",
                "wetness_in", "wetness_out", "drying_rate", "diagnostics"}
    assert required.issubset(rows[0].keys())


def test_hot_dry_hits_calib_target(model: SingleLayerModel) -> None:
    s = _hot_dry_scenario()
    rows = run_scenario(s, model, model.default_params)
    h2m = hours_to_mow(rows, threshold=5.0)
    assert h2m is not None
    assert 3 <= h2m <= 6  # USDA loam hot/sunny target


def test_hours_to_mow_none_when_never_clears(model: SingleLayerModel) -> None:
    s = Scenario(
        name="never",
        duration_hours=3,
        rain_events=[RainEvent(hour=0, inches=2.5)],
        weather=WeatherConditions(temp=45, rh=95, wind=1, clouds=100),
        use_solar_model=False,
        mow_threshold=5.0,
    )
    rows = run_scenario(s, model, model.default_params)
    assert hours_to_mow(rows, threshold=5.0) is None


def test_wetness_monotone_no_rain(model: SingleLayerModel) -> None:
    """Without rain after hour 0, wetness should be non-increasing."""
    s = _cool_overcast_scenario()
    rows = run_scenario(s, model, model.default_params)
    # Skip hour 0 (rain lands); from hour 1 onward wetness should not increase
    for i in range(1, len(rows) - 1):
        assert rows[i + 1]["wetness_out"] <= rows[i]["wetness_out"] + 1e-9
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_runner.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError` for `lawn_rain_model.simulation.runner` and `lawn_rain_model.calibration.scenarios`.

- [ ] **Step 3: Implement `lawn_rain_model/calibration/scenarios.py`** (needed by runner tests)

```python
# lawn_rain_model/calibration/scenarios.py
"""Scenario and CalibrationTarget dataclasses, and YAML loader."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class WeatherConditions:
    temp:      float = 75.0
    rh:        float = 60.0
    wind:      float = 5.0
    clouds:    float = 30.0
    elevation: float = 45.0   # used only when use_solar_model=False


@dataclass
class RainEvent:
    hour:   int
    inches: float


@dataclass
class CalibrationTarget:
    target_hours_min: float
    target_hours_max: float   # == target_hours_min for point targets
    weight:           float = 1.0
    note:             str   = ""


@dataclass
class Scenario:
    name:            str
    duration_hours:  int
    rain_events:     list[RainEvent]
    weather:         Optional[WeatherConditions]   # None when history_file is set
    mow_threshold:   float                = 5.0
    initial_wetness: float                = 0.0
    use_solar_model: bool                 = True
    start_hour:      int                  = 6
    day_of_year:     int                  = 172
    latitude:        float                = 39.0
    calibration:     Optional[CalibrationTarget] = None
    history_file:    Optional[str]        = None   # path relative to scenarios YAML
    sensor_map:      dict[str, str]       = field(default_factory=dict)


class ScenarioLoader:
    @staticmethod
    def load(path: Path | str, include_calibration: bool = True) -> list[Scenario]:
        path = Path(path)
        raw  = yaml.safe_load(path.read_text())
        scenarios: list[Scenario] = []

        for s in raw.get("scenarios", []):
            w_raw = s.get("weather") or {}
            weather: Optional[WeatherConditions] = None
            if w_raw:
                weather = WeatherConditions(
                    temp=w_raw.get("temp", 75.0),
                    rh=w_raw.get("rh", 60.0),
                    wind=w_raw.get("wind", 5.0),
                    clouds=w_raw.get("clouds", 30.0),
                    elevation=w_raw.get("elevation", 45.0),
                )

            rain_events = [
                RainEvent(e["hour"], e["inches"])
                for e in s.get("rain_events", [])
            ]

            cal: Optional[CalibrationTarget] = None
            if "calibration" in s and include_calibration:
                c = s["calibration"]
                if "target_hours" in c:
                    # Point target
                    t = float(c["target_hours"])
                    cal = CalibrationTarget(
                        target_hours_min=t,
                        target_hours_max=t,
                        weight=c.get("weight", 1.0),
                        note=c.get("note", ""),
                    )
                else:
                    cal = CalibrationTarget(
                        target_hours_min=c["target_hours_min"],
                        target_hours_max=c["target_hours_max"],
                        weight=c.get("weight", 1.0),
                        note=c.get("note", ""),
                    )

            scenarios.append(Scenario(
                name=s.get("name", "unnamed"),
                duration_hours=s.get("duration_hours", 96),
                rain_events=rain_events,
                weather=weather,
                mow_threshold=s.get("mow_threshold", 5.0),
                initial_wetness=s.get("initial_wetness", 0.0),
                use_solar_model=s.get("use_solar_model", True),
                start_hour=s.get("start_hour", 6),
                day_of_year=s.get("day_of_year", 172),
                latitude=s.get("latitude", 39.0),
                calibration=cal,
                history_file=s.get("history_file"),
                sensor_map=s.get("history_sensor_map", {}),
            ))

        return scenarios
```

- [ ] **Step 4: Implement `lawn_rain_model/simulation/runner.py`**

```python
# lawn_rain_model/simulation/runner.py
"""Model-agnostic scenario runner."""
from __future__ import annotations
from typing import Any
from lawn_rain_model.models.protocol import LawnModel
from lawn_rain_model.calibration.scenarios import Scenario, WeatherConditions
from lawn_rain_model.simulation.weather import WeatherStep
from lawn_rain_model.simulation.solar import sun_elevation


def _build_weather_steps(scenario: Scenario) -> list[WeatherStep]:
    """Build hourly WeatherStep list from fixed conditions + solar model."""
    w: WeatherConditions = scenario.weather  # type: ignore[assignment]
    steps: list[WeatherStep] = []
    rain_map = {e.hour: e.inches for e in scenario.rain_events}

    for h in range(scenario.duration_hours):
        tod = (scenario.start_hour + h) % 24
        if scenario.use_solar_model:
            elev = sun_elevation(tod, scenario.day_of_year, scenario.latitude)
        else:
            elev = w.elevation
        steps.append(WeatherStep(
            hour=h, tod=tod,
            temp=w.temp, rh=w.rh, wind=w.wind, clouds=w.clouds,
            elevation=elev,
            rain_inches=rain_map.get(h, 0.0),
        ))
    return steps


def run_scenario(
    scenario: Scenario,
    model: LawnModel,
    params: dict[str, float],
    weather_steps: list[WeatherStep] | None = None,
) -> list[dict[str, Any]]:
    """
    Run a scenario for its full duration.

    weather_steps: pre-built list (from history resampler). If None, steps
                   are generated from scenario.weather + solar model.
    """
    if weather_steps is None:
        weather_steps = _build_weather_steps(scenario)

    state = model.initial_state(scenario.initial_wetness)
    rows: list[dict[str, Any]] = []

    for ws in weather_steps:
        wetness_in  = model.surface_wetness(state)
        result      = model.step(state, ws, params)
        wetness_out = result["wetness_out"]

        rows.append({
            "hour":        ws.hour,
            "tod":         ws.tod,
            "elevation":   ws.elevation,
            "rain_inches": ws.rain_inches,
            "wetness_in":  wetness_in,
            "wetness_out": wetness_out,
            "drying_rate": result["drying_rate"],
            "can_mow":     wetness_out <= scenario.mow_threshold,
            "diagnostics": result["diagnostics"],
        })
        state = model.initial_state(wetness_out)

    return rows


def hours_to_mow(rows: list[dict[str, Any]], threshold: float) -> int | None:
    """Return the first hour where wetness_out ≤ threshold, or None."""
    for r in rows:
        if r["wetness_out"] <= threshold:
            return r["hour"]
    return None
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_runner.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add lawn_rain_model/simulation/runner.py lawn_rain_model/calibration/scenarios.py \
        tests/test_runner.py
git commit -m "feat: model-agnostic runner + Scenario/ScenarioLoader"
```

---

## Task 6: Loss Function

**Files:**
- Create: `lawn_rain_model/calibration/loss.py`
- Create: `tests/test_loss.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_loss.py -v 2>&1 | head -5
```

Expected: `ModuleNotFoundError: No module named 'lawn_rain_model.calibration.loss'`

- [ ] **Step 3: Implement `lawn_rain_model/calibration/loss.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_loss.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add lawn_rain_model/calibration/loss.py tests/test_loss.py
git commit -m "feat: scenario_loss handles range + point targets"
```

---

## Task 7: Scenario Loader Tests

**Files:**
- Modify: `tests/test_scenarios.py` (new file)

The `ScenarioLoader` was already implemented in Task 5. This task adds its test coverage.

- [ ] **Step 1: Write tests**

```python
# tests/test_scenarios.py
from __future__ import annotations
import textwrap
import pytest
from pathlib import Path
from lawn_rain_model.calibration.scenarios import ScenarioLoader


SAMPLE_YAML = textwrap.dedent("""\
    scenarios:
      - name: range_target
        duration_hours: 48
        rain_events:
          - hour: 0
            inches: 1.0
        weather:
          temp: 75
          rh: 60
          wind: 5
          clouds: 30
        calibration:
          target_hours_min: 3
          target_hours_max: 6
          weight: 1.5
          note: "range scenario"

      - name: point_target
        duration_hours: 72
        rain_events:
          - hour: 0
            inches: 1.0
        weather:
          temp: 65
          rh: 60
          wind: 5
          clouds: 50
        calibration:
          target_hours: 14.0
          weight: 2.0
          note: "point scenario"

      - name: no_cal
        duration_hours: 24
        rain_events: []
        weather:
          temp: 70
          rh: 65
          wind: 5
          clouds: 40
""")


@pytest.fixture
def yaml_file(tmp_path: Path) -> Path:
    p = tmp_path / "scenarios.yaml"
    p.write_text(SAMPLE_YAML)
    return p


def test_loads_all_scenarios(yaml_file: Path) -> None:
    scenarios = ScenarioLoader.load(yaml_file)
    assert len(scenarios) == 3


def test_range_target_bounds(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    r = next(x for x in s if x.name == "range_target")
    assert r.calibration is not None
    assert r.calibration.target_hours_min == 3
    assert r.calibration.target_hours_max == 6
    assert r.calibration.weight == 1.5


def test_point_target_min_equals_max(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    p = next(x for x in s if x.name == "point_target")
    assert p.calibration is not None
    assert p.calibration.target_hours_min == 14.0
    assert p.calibration.target_hours_max == 14.0
    assert p.calibration.weight == 2.0


def test_no_calibration_is_none(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    n = next(x for x in s if x.name == "no_cal")
    assert n.calibration is None


def test_skip_calibration_flag(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file, include_calibration=False)
    for scenario in s:
        assert scenario.calibration is None


def test_rain_events_loaded(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    r = next(x for x in s if x.name == "range_target")
    assert len(r.rain_events) == 1
    assert r.rain_events[0].hour == 0
    assert r.rain_events[0].inches == 1.0


def test_weather_conditions_loaded(yaml_file: Path) -> None:
    s = ScenarioLoader.load(yaml_file)
    r = next(x for x in s if x.name == "range_target")
    assert r.weather is not None
    assert r.weather.temp == 75
    assert r.weather.rh == 60


def test_existing_scenarios_yaml_loads() -> None:
    """The project's actual scenarios.yaml must load without error."""
    scenarios = ScenarioLoader.load("scenarios.yaml")
    assert len(scenarios) > 0
    names = [s.name for s in scenarios]
    assert "calib_hot_sunny" in names
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_scenarios.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_scenarios.py
git commit -m "test: ScenarioLoader — range/point targets, calibration flag, real YAML"
```

---

## Task 8: Optimizer

**Files:**
- Create: `lawn_rain_model/calibration/optimizer.py`

No new tests — the optimizer's correctness is validated by the existing calibration scenario
targets. A smoke test is added in Task 13.

- [ ] **Step 1: Implement `lawn_rain_model/calibration/optimizer.py`**

```python
# lawn_rain_model/calibration/optimizer.py
"""Differential evolution optimizer for model parameter fitting."""
from __future__ import annotations
from typing import Any
from scipy.optimize import differential_evolution
from lawn_rain_model.models.protocol import LawnModel
from lawn_rain_model.calibration.scenarios import Scenario
from lawn_rain_model.calibration.loss import scenario_loss
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow

_iter_count: list[int] = [0]


def _progress_cb(xk: Any, convergence: float) -> None:
    _iter_count[0] += 1
    if _iter_count[0] % 50 == 0:
        print(f"  iter={_iter_count[0]:>5}  convergence={convergence:.8f}", end="\r", flush=True)


def build_objective(
    calibration_scenarios: list[Scenario],
    model: LawnModel,
    base_params: dict[str, float],
    tunable_keys: list[str],
) -> Any:
    def objective(vec: Any) -> float:
        p = base_params.copy()
        for k, v in zip(tunable_keys, vec):
            p[k] = v
        # Hard constraint: stage_thresh must be below pool_thresh
        if p["stage_thresh"] >= p["pool_thresh"]:
            return 1e6
        total = 0.0
        for s in calibration_scenarios:
            rows = run_scenario(s, model, p)
            h2m  = hours_to_mow(rows, s.mow_threshold)
            loss = scenario_loss(h2m, s.calibration, s.duration_hours)  # type: ignore[arg-type]
            total += loss * s.calibration.weight  # type: ignore[union-attr]
        return total
    return objective


def run_optimizer(
    calibration_scenarios: list[Scenario],
    model: LawnModel,
    frozen: dict[str, float] | None = None,
    maxiter: int = 2000,
    popsize: int = 20,
    tol: float = 1e-5,
    seed: int = 42,
) -> dict[str, Any]:
    frozen = frozen or {}
    bounds_map = model.param_bounds
    tunable_keys = [k for k in bounds_map if k not in frozen]
    bounds       = [bounds_map[k] for k in tunable_keys]

    base_params = model.default_params
    base_params.update(frozen)

    print(f"\nOptimizing {len(tunable_keys)} parameters across "
          f"{len(calibration_scenarios)} calibration scenarios")
    print(f"Frozen: {list(frozen.keys()) or 'none'}")
    print(f"Popsize={popsize}  maxiter={maxiter}  tol={tol}\n")

    _iter_count[0] = 0
    result = differential_evolution(
        build_objective(calibration_scenarios, model, base_params, tunable_keys),
        bounds,
        seed=seed,
        maxiter=maxiter,
        popsize=popsize,
        tol=tol,
        polish=True,
        updating="deferred",
        workers=1,
        callback=_progress_cb,
    )
    print()

    best_params = base_params.copy()
    for k, v in zip(tunable_keys, result.x):
        best_params[k] = v

    return {
        "params":       best_params,
        "loss":         result.fun,
        "success":      result.success,
        "message":      result.message,
        "iterations":   result.nit,
        "tunable_keys": tunable_keys,
    }
```

- [ ] **Step 2: Commit**

```bash
git add lawn_rain_model/calibration/optimizer.py
git commit -m "feat: port optimizer to model-agnostic interface"
```

---

## Task 9: Display

**Files:**
- Create: `lawn_rain_model/cli/display.py`

Display is model-aware for `SingleLayerModel`'s `diagnostics` keys. Unknown keys are skipped
gracefully so that a future multi-layer model doesn't crash the display.

- [ ] **Step 1: Implement `lawn_rain_model/cli/display.py`**

```python
# lawn_rain_model/cli/display.py
"""Terminal display helpers. Reads SingleLayerModel diagnostics by known key names."""
from __future__ import annotations
from typing import Any
from lawn_rain_model.calibration.scenarios import Scenario
from lawn_rain_model.simulation.runner import hours_to_mow

BAR_WIDTH = 40


def sparkline(value: float, stage_thresh: float = 18.0, pool_thresh: float = 40.0) -> str:
    filled = max(0, min(BAR_WIDTH, int(round(value / 100.0 * BAR_WIDTH))))
    bar = list("█" * filled + "·" * (BAR_WIDTH - filled))
    for thresh in [stage_thresh, pool_thresh]:
        idx = int(thresh / 100.0 * BAR_WIDTH)
        if 0 <= idx < BAR_WIDTH and bar[idx] == "·":
            bar[idx] = "|"
    return "".join(bar)


def print_table(rows: list[dict[str, Any]], scenario: Scenario, params: dict[str, float]) -> None:
    stage_thresh = params.get("stage_thresh", 18.0)
    pool_thresh  = params.get("pool_thresh", 40.0)
    rain_col = 'Rain"'
    hdr = (f"{'Hr':>3}  {'ToD':>5}  {rain_col:>5}  "
           f"{'Wet':>5}  {'Evap':>5}  {'Pool':>5}  {'Cap':>5}  {'Visc':>4}  {'Dry':>5}  "
           f"{'VPD':>4}  {'Elev':>5}  {'Index':>{BAR_WIDTH+2}}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        d   = r.get("diagnostics", {})
        w   = r["wetness_out"]
        pre = r.get("diagnostics", {}).get("pre_dry", w)
        regime = (
            "pool" if pre > pool_thresh else
            "sat " if pre > stage_thresh else
            "dry "
        )
        mow = "  [MOW]" if r["can_mow"] else ""
        bar = sparkline(w, stage_thresh, pool_thresh)
        rs  = f"{r['rain_inches']:.2f}" if r["rain_inches"] > 0 else "     "
        print(
            f"{r['hour']:>3}  {r['tod']:>02d}:00  {rs:>5}  "
            f"{w:>5.1f}  {d.get('evap_rate', 0.0):>5.3f}  "
            f"{d.get('pool_drain_rate', 0.0):>5.3f}  "
            f"{d.get('capillary_sink', 0.0):>5.3f}  "
            f"{d.get('visc_factor', 1.0):>4.2f}  "
            f"{r['drying_rate']:>5.3f}  "
            f"{d.get('vpd_norm', 0.0):>4.2f}  "
            f"{r['elevation']:>+5.1f}  "
            f"[{bar}] {regime}{mow}"
        )


def print_summary(rows: list[dict[str, Any]], scenario: Scenario) -> None:
    first_mow = hours_to_mow(rows, scenario.mow_threshold)
    max_wet   = max(r["wetness_out"] for r in rows)
    mw_hr     = next(r["hour"] for r in rows if r["wetness_out"] == max_wet)

    cal_line = ""
    if scenario.calibration:
        t = scenario.calibration
        if first_mow is None:
            cal_line = f"  MISS  target={t.target_hours_min:.0f}-{t.target_hours_max:.0f}h  got=>{scenario.duration_hours}h"
        elif t.target_hours_min <= first_mow <= t.target_hours_max:
            cal_line = f"  HIT   target={t.target_hours_min:.0f}-{t.target_hours_max:.0f}h  got={first_mow}h"
        else:
            d = "FAST" if first_mow < t.target_hours_min else "SLOW"
            cal_line = f"  {d}  target={t.target_hours_min:.0f}-{t.target_hours_max:.0f}h  got={first_mow}h"

    print(f"\n{'-'*60}")
    print(f"  Scenario   : {scenario.name}")
    if cal_line:
        print(f"  Calibration:{cal_line}")
    print(f"  Peak index : {max_wet:.1f} @ hour {mw_hr}")
    if first_mow is not None:
        print(f"  First mow  : hour {first_mow}  "
              f"(ToD {(scenario.start_hour + first_mow) % 24:02d}:00)")
    else:
        print(f"  First mow  : never within {scenario.duration_hours}h window")
    print(f"  Total rain : {sum(r['rain_inches'] for r in rows):.2f}\"")
    print(f"{'-'*60}\n")


def print_jinja2(params: dict[str, float]) -> None:
    p = params
    print(f"\n{'='*72}")
    print("  JINJA2 CONSTANTS (drop into your template)")
    print("=" * 72)
    print(f"""
{{%- set _base_evap       = {p['base_evap']:.5f} %}}
{{%- set _vpd_denom       = {p['vpd_norm_denom']:.5f} %}}
{{%- set _e_sat_base      = {p['e_sat_base']:.6f} %}}
{{%- set _vpd_min         = {p['vpd_min']:.5f} %}}
{{%- set _sun_coeff       = {p['sun_coeff']:.5f} %}}
{{%- set _cloud_exp       = {p['cloud_exp']:.5f} %}}
{{%- set _solar_exp       = {p['solar_exp']:.5f} %}}
{{%- set _wind_coeff      = {p['wind_coeff']:.5f} %}}
{{%- set _wind_cap        = {p['wind_cap']:.5f} %}}
{{%- set _stage_thresh    = {p['stage_thresh']:.3f} %}}
{{%- set _pool_thresh     = {p['pool_thresh']:.3f} %}}
{{%- set _capillary_rate  = {p['capillary_rate']:.5f} %}}
{{%- set _pool_drain_coef = {p['pool_drain_coef']:.5f} %}}
{{%- set _rain_mult       = {p['rain_mult']:.3f} %}}
{{%- set _visc_slope      = {p['visc_slope']:.5f} %}}
{{%- set _visc_floor      = {p['visc_floor']:.5f} %}}

{{# Viscosity-corrected capillary sink #}}
{{%- set _visc_factor     = [1.0 - (70.0 - temp) * _visc_slope, _visc_floor] | max %}}
{{%- set capillary_sink   = soil_wetness * _capillary_rate * _visc_factor %}}
""")


def print_optimizer_report(
    opt: dict[str, Any],
    calibration_scenarios: list[Scenario],
    model: Any,
) -> None:
    from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow
    from lawn_rain_model.calibration.loss import scenario_loss

    p       = opt["params"]
    tunable = set(opt["tunable_keys"])
    default = model.default_params

    print(f"\n{'='*72}")
    print(f"  OPTIMIZER RESULT  loss={opt['loss']:.6f}  "
          f"iter={opt['iterations']}  "
          f"{'converged' if opt['success'] else 'DID NOT CONVERGE'}")
    print(f"{'='*72}")

    print(f"\n  {'Parameter':<20} {'Default':>10} {'Optimized':>12} {'Delta':>10}  Frozen")
    print("  " + "-" * 58)
    for k, dv in default.items():
        ov     = p[k]
        delta  = ov - dv
        frozen = "yes" if k not in tunable else ""
        big    = "  <--" if abs(delta / max(abs(dv), 1e-9)) > 0.20 and not frozen else ""
        print(f"  {k:<20} {dv:>10.4f} {ov:>12.5f} {delta:>+10.4f}  {frozen:>5}{big}")

    print(f"\n  {'Scenario':<35} {'Target':>10} {'Got':>6} {'Loss':>8}  Status")
    print("  " + "-" * 65)
    for s in calibration_scenarios:
        rows = run_scenario(s, model, p)
        h2m  = hours_to_mow(rows, s.mow_threshold)
        loss = scenario_loss(h2m, s.calibration, s.duration_hours)  # type: ignore[arg-type]
        t    = s.calibration
        assert t is not None
        tstr = f"{t.target_hours_min:.0f}-{t.target_hours_max:.0f}h"
        gstr = f"{h2m}h" if h2m is not None else f">{s.duration_hours}h"
        status = "OK" if loss == 0 else ("TOO FAST" if (h2m or 999) < t.target_hours_min else "TOO SLOW")
        note = f"  [{t.note}]" if t.note else ""
        print(f"  {s.name:<35} {tstr:>10} {gstr:>6} {loss:>8.4f}  {status}{note}")

    print(f"\n  Total weighted loss: {opt['loss']:.6f}")
    print_jinja2(p)
```

- [ ] **Step 2: Commit**

```bash
git add lawn_rain_model/cli/display.py
git commit -m "feat: port display helpers to new StepResult shape"
```

---

## Task 10: CLI + Entry Point

**Files:**
- Create: `lawn_rain_model/cli/commands.py`
- Modify: `simulator.py`

- [ ] **Step 1: Implement `lawn_rain_model/cli/commands.py`**

```python
# lawn_rain_model/cli/commands.py
"""CLI commands: simulate, sweep, optimize."""
from __future__ import annotations
import argparse
import csv as csv_mod
import sys
from pathlib import Path
from typing import Any
import yaml

from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.calibration.scenarios import Scenario, ScenarioLoader, WeatherConditions, RainEvent
from lawn_rain_model.calibration.optimizer import run_optimizer
from lawn_rain_model.calibration.loss import scenario_loss
from lawn_rain_model.simulation.runner import run_scenario, hours_to_mow
from lawn_rain_model.cli.display import (
    print_table, print_summary, print_jinja2, print_optimizer_report,
)


def _load_params(params_file: str | None, model: SingleLayerModel) -> dict[str, float]:
    p = model.default_params
    if params_file:
        override = yaml.safe_load(Path(params_file).read_text()).get("params", {})
        p.update(override)
    return p


def _mow_cell(h2m: int | None, scenario: Scenario) -> str:
    return f">{scenario.duration_hours}h" if h2m is None else f"{h2m}h"


def _hit_marker(h2m: int | None, scenario: Scenario) -> str:
    if scenario.calibration is None:
        return ""
    t = scenario.calibration
    actual = scenario.duration_hours if h2m is None else h2m
    if t.target_hours_min <= actual <= t.target_hours_max:
        return "✓"
    return "FAST" if actual < t.target_hours_min else "SLOW"


def build_compare_table(
    scenarios: list[Scenario],
    param_sets: list[tuple[str, dict[str, float]]],
    model: SingleLayerModel,
) -> str:
    target_col = "Target"
    labels = [label for label, _ in param_sets]

    results: list[list[str]] = []
    for s in scenarios:
        row: list[str] = []
        for _, p in param_sets:
            rows = run_scenario(s, model, p)
            h2m  = hours_to_mow(rows, s.mow_threshold)
            marker = _hit_marker(h2m, s)
            cell = _mow_cell(h2m, s)
            if marker:
                cell = f"{cell} {marker}"
            row.append(cell)
        results.append(row)

    target_strs = []
    for s in scenarios:
        if s.calibration:
            t = s.calibration
            target_strs.append(f"{t.target_hours_min:.0f}-{t.target_hours_max:.0f}h")
        else:
            target_strs.append("")

    name_w   = max(len("Scenario"), max(len(s.name) for s in scenarios))
    target_w = max(len(target_col), max(len(t) for t in target_strs))
    ps_widths = [
        max(len(labels[i]), max(len(results[si][i]) for si in range(len(scenarios))))
        for i in range(len(param_sets))
    ]

    def row_str(name: str, target: str, cells: list[str]) -> str:
        parts = [f"| {name:<{name_w}} ", f"| {target:^{target_w}} "]
        for cell, w in zip(cells, ps_widths):
            parts.append(f"| {cell:^{w}} ")
        return "".join(parts) + "|"

    def sep_str() -> str:
        parts = [f"|{'-'*(name_w+2)}", f"|{'-'*(target_w+2)}"]
        for w in ps_widths:
            parts.append(f"|{'-'*(w+2)}")
        return "".join(parts) + "|"

    lines: list[str] = []
    lines.append(row_str("Scenario", target_col,
                         [f"{lb:^{w}}" for lb, w in zip(labels, ps_widths)]))
    lines.append(sep_str())

    cal_rows   = [(i, s) for i, s in enumerate(scenarios) if s.calibration is not None]
    explo_rows = [(i, s) for i, s in enumerate(scenarios) if s.calibration is None]

    if cal_rows:
        lines.append(row_str("**CALIBRATION**", "", [""] * len(param_sets)))
        for i, s in cal_rows:
            lines.append(row_str(s.name, target_strs[i], results[i]))
    if explo_rows:
        lines.append(row_str("**EXPLORATION**", "", [""] * len(param_sets)))
        for i, s in explo_rows:
            lines.append(row_str(s.name, target_strs[i], results[i]))

    return "\n".join(lines)


def cmd_simulate(args: argparse.Namespace) -> None:
    model = SingleLayerModel()
    param_files: list[str] = args.params_file or []

    if param_files:
        param_sets: list[tuple[str, dict[str, float]]] = []
        for pf in param_files:
            p = _load_params(pf, model)
            param_sets.append((Path(pf).stem, p))
        params = param_sets[0][1]
    else:
        params = _load_params(None, model)
        param_sets = []

    if args.scenario_file:
        scenarios = ScenarioLoader.load(args.scenario_file)
        if args.name:
            scenarios = [s for s in scenarios if s.name == args.name]
            if not scenarios:
                sys.exit(f"No scenario '{args.name}'")
    else:
        rain_events = []
        for spec in (args.rain or []):
            h_s, i_s = spec.split(":")
            rain_events.append(RainEvent(int(h_s), float(i_s)))
        scenarios = [Scenario(
            name="cli",
            duration_hours=args.hours,
            rain_events=rain_events,
            weather=WeatherConditions(
                temp=args.temp, rh=args.rh,
                wind=args.wind, clouds=args.clouds,
            ),
            mow_threshold=args.threshold,
            initial_wetness=args.initial,
            use_solar_model=not args.no_solar,
            start_hour=args.start_hour,
            day_of_year=args.day_of_year,
            latitude=args.lat,
        )]

    for s in scenarios:
        rows = run_scenario(s, model, params)
        print(f"\n{'='*80}\n  {s.name.upper()}\n{'='*80}")
        if not args.summary_only:
            print_table(rows, s, params)
        print_summary(rows, s)

        if args.csv:
            csv_path = (Path(args.csv) if len(scenarios) == 1
                        else Path(f"{s.name}.csv"))
            with open(csv_path, "w", newline="") as f:
                # Flatten diagnostics into top-level columns for CSV
                flat_rows = []
                for r in rows:
                    flat = {k: v for k, v in r.items() if k != "diagnostics"}
                    flat.update(r.get("diagnostics", {}))
                    flat_rows.append(flat)
                w_csv = csv_mod.DictWriter(f, fieldnames=flat_rows[0].keys())
                w_csv.writeheader()
                w_csv.writerows(flat_rows)
            print(f"  CSV -> {csv_path}")

    print_jinja2(params)

    if args.save_params:
        out = {"params": {k: float(round(v, 6)) for k, v in params.items()}}
        Path(args.save_params).write_text(yaml.dump(out, default_flow_style=False))
        print(f"\n  Params saved -> {args.save_params}")

    if len(param_sets) >= 2:
        table = build_compare_table(scenarios, param_sets, model)
        print(f"\n{'='*80}\n  PARAMETER SET COMPARISON\n{'='*80}\n")
        print(table)
        if args.compare_md:
            md_path = Path(args.compare_md)
            header = "# Parameter Set Comparison\n\n"
            legend = (
                "> ✓ = within target range  "
                "· FAST = below target min  "
                "· SLOW = above target max\n\n"
            )
            md_path.write_text(header + legend + table + "\n")
            print(f"  Comparison table -> {md_path}")


def cmd_sweep(args: argparse.Namespace) -> None:
    model = SingleLayerModel()
    params = _load_params(args.params_file, model)
    rain_vals = [float(x) for x in args.rain_inches.split(",")]

    print(f"\nDrying sweep  threshold={args.threshold}  "
          f"[{args.temp}F  RH={args.rh}%  wind={args.wind}mph  clouds={args.clouds}%]")
    print(f"{'Rain':>8}  {'Peak':>6}  {'Mow@':>6}")
    print("-" * 28)

    for rain in rain_vals:
        s = Scenario(
            name=f"{rain}in",
            duration_hours=args.hours,
            rain_events=[RainEvent(0, rain)],
            weather=WeatherConditions(
                temp=args.temp, rh=args.rh,
                wind=args.wind, clouds=args.clouds,
            ),
            mow_threshold=args.threshold,
            use_solar_model=not args.no_solar,
            start_hour=args.start_hour,
            day_of_year=args.day_of_year,
            latitude=args.lat,
        )
        rows = run_scenario(s, model, params)
        h2m  = hours_to_mow(rows, args.threshold)
        peak = max(r["wetness_out"] for r in rows)
        print(f"  {rain:>5.2f}\"  peak={peak:>5.1f}  "
              f"{str(h2m)+'h' if h2m is not None else '>'+str(args.hours)+'h'}")


def cmd_optimize(args: argparse.Namespace) -> None:
    model = SingleLayerModel()
    all_scenarios = ScenarioLoader.load(args.scenario_file, include_calibration=True)
    cal_scenarios = [s for s in all_scenarios if s.calibration is not None
                     and s.calibration.weight > 0]

    if not cal_scenarios:
        sys.exit("No calibration targets with weight>0 found in YAML.")

    if args.only:
        names = {n.strip() for n in args.only.split(",")}
        cal_scenarios = [s for s in cal_scenarios if s.name in names]

    frozen: dict[str, float] = {}
    for spec in (args.freeze or []):
        k, v = spec.split("=")
        frozen[k.strip()] = float(v.strip())

    opt = run_optimizer(
        cal_scenarios, model, frozen=frozen,
        maxiter=args.maxiter, popsize=args.popsize,
        tol=args.tol, seed=args.seed,
    )

    print_optimizer_report(opt, cal_scenarios, model)

    if args.save_params:
        out = {"params": {k: float(round(v, 6)) for k, v in opt["params"].items()}}
        Path(args.save_params).write_text(yaml.dump(out, default_flow_style=False))
        print(f"\n  Params saved -> {args.save_params}")


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="lawn_rain_model")
    sub  = root.add_subparsers(dest="cmd", required=True)

    sim = sub.add_parser("simulate")
    sim.add_argument("-f", "--scenario-file")
    sim.add_argument("-n", "--name")
    sim.add_argument("-P", "--params-file", nargs="*", metavar="FILE")
    sim.add_argument("--compare-md", metavar="FILE")
    sim.add_argument("--rain", nargs="*", metavar="H:IN")
    sim.add_argument("--hours",        type=int,   default=72)
    sim.add_argument("--threshold",    type=float, default=5.0)
    sim.add_argument("--initial",      type=float, default=0.0)
    sim.add_argument("--temp",         type=float, default=75.0)
    sim.add_argument("--rh",           type=float, default=60.0)
    sim.add_argument("--wind",         type=float, default=5.0)
    sim.add_argument("--clouds",       type=float, default=30.0)
    sim.add_argument("--start-hour",   type=int,   default=6)
    sim.add_argument("--day-of-year",  type=int,   default=172)
    sim.add_argument("--lat",          type=float, default=39.0)
    sim.add_argument("--no-solar",     action="store_true")
    sim.add_argument("--summary-only", action="store_true")
    sim.add_argument("--save-params",  metavar="FILE")
    sim.add_argument("--csv")

    sw = sub.add_parser("sweep")
    sw.add_argument("-P", "--params-file")
    sw.add_argument("--rain-inches", default="0.1,0.25,0.5,0.75,1.0,1.5,2.0,2.5")
    sw.add_argument("--hours",       type=int,   default=96)
    sw.add_argument("--threshold",   type=float, default=5.0)
    sw.add_argument("--temp",        type=float, default=75.0)
    sw.add_argument("--rh",          type=float, default=60.0)
    sw.add_argument("--wind",        type=float, default=5.0)
    sw.add_argument("--clouds",      type=float, default=30.0)
    sw.add_argument("--start-hour",  type=int,   default=6)
    sw.add_argument("--day-of-year", type=int,   default=172)
    sw.add_argument("--lat",         type=float, default=39.0)
    sw.add_argument("--no-solar",    action="store_true")

    opt = sub.add_parser("optimize")
    opt.add_argument("-f", "--scenario-file", required=True)
    opt.add_argument("--only")
    opt.add_argument("--freeze",      nargs="*", metavar="PARAM=VALUE")
    opt.add_argument("--save-params", metavar="FILE")
    opt.add_argument("--maxiter",     type=int,   default=2000)
    opt.add_argument("--popsize",     type=int,   default=20)
    opt.add_argument("--tol",         type=float, default=1e-5)
    opt.add_argument("--seed",        type=int,   default=42)

    return root


def main() -> None:
    args = build_parser().parse_args()
    {"simulate": cmd_simulate, "sweep": cmd_sweep, "optimize": cmd_optimize}[args.cmd](args)
```

- [ ] **Step 2: Replace `simulator.py` with thin entry point**

```python
#!/usr/bin/env python3
"""Entry point — delegates to lawn_rain_model package."""
from lawn_rain_model.cli.commands import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test the CLI**

```bash
python simulator.py simulate -f scenarios.yaml -n calib_hot_sunny --summary-only
```

Expected: summary block showing `HIT   target=3-6h  got=Xh`.

```bash
python simulator.py sweep --temp 75 --rh 60
```

Expected: table of rain amounts and mow times.

- [ ] **Step 4: Commit**

```bash
git add lawn_rain_model/cli/commands.py simulator.py
git commit -m "feat: CLI commands ported to new package; simulator.py is now a thin entry point"
```

---

## Task 11: History Resampler

**Files:**
- Modify: `lawn_rain_model/simulation/weather.py` (add `resample_history()`)
- Create: `tests/fixtures/history_simple.csv`
- Create: `tests/fixtures/history_midnight.csv`
- Create: `tests/test_resampler.py`

- [ ] **Step 1: Create fixture files**

`tests/fixtures/history_simple.csv`:
```csv
entity_id,state,last_changed
sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z
sensor.pirateweather_temperature_0h,76.0,2026-04-24T10:30:00.000Z
sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:30:00.000Z
sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z
sensor.pirateweather_current_day_liquid_accumulation,0.5,2026-04-24T10:45:00.000Z
sensor.pirateweather_current_day_liquid_accumulation,0.8,2026-04-24T11:30:00.000Z
sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z
sensor.pirateweather_humidity_0h,62,2026-04-24T11:15:00.000Z
sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z
sensor.pirateweather_wind_speed,6.0,2026-04-24T11:00:00.000Z
sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z
sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z
sensor.sun_elevation,45.0,2026-04-24T10:30:00.000Z
sensor.sun_elevation,40.0,2026-04-24T11:00:00.000Z
sensor.sun_elevation,35.0,2026-04-24T11:30:00.000Z
```

`tests/fixtures/history_midnight.csv`:
```csv
entity_id,state,last_changed
sensor.pirateweather_temperature_0h,70.0,2026-04-24T23:00:00.000Z
sensor.pirateweather_current_day_liquid_accumulation,0.9,2026-04-24T23:00:00.000Z
sensor.pirateweather_current_day_liquid_accumulation,0.1,2026-04-25T00:30:00.000Z
sensor.pirateweather_humidity_0h,60,2026-04-24T23:00:00.000Z
sensor.pirateweather_wind_speed,5.0,2026-04-24T23:00:00.000Z
sensor.pirateweather_cloud_coverage,30,2026-04-24T23:00:00.000Z
sensor.sun_elevation,-5.0,2026-04-24T23:00:00.000Z
sensor.sun_elevation,-8.0,2026-04-25T00:00:00.000Z
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_resampler.py
from __future__ import annotations
from pathlib import Path
import pytest
from lawn_rain_model.simulation.weather import resample_history, DEFAULT_SENSOR_MAP

FIXTURES = Path(__file__).parent / "fixtures"


def test_simple_output_length() -> None:
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert len(steps) == 2  # hours 10 and 11


def test_hour_indices_sequential() -> None:
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    for i, s in enumerate(steps):
        assert s.hour == i


def test_tod_hour_10() -> None:
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert steps[0].tod == 10


def test_rain_hour_10() -> None:
    """Accumulation goes from 0.0 → 0.5 during hour 10: rain = 0.5"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert abs(steps[0].rain_inches - 0.5) < 0.001


def test_rain_hour_11() -> None:
    """Accumulation goes from 0.5 → 0.8 during hour 11: rain = 0.3"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert abs(steps[1].rain_inches - 0.3) < 0.001


def test_temp_forward_fill_hour_10() -> None:
    """Last temp reading in hour 10 is 76.0 at 10:30"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert steps[0].temp == 76.0


def test_temp_forward_fill_hour_11() -> None:
    """Last temp reading in hour 11 is 74.0 at 11:30"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert steps[1].temp == 74.0


def test_elevation_last_in_hour() -> None:
    """sun_elevation: last reading in hour 10 is 45.0 at 10:30"""
    steps = resample_history(FIXTURES / "history_simple.csv", DEFAULT_SENSOR_MAP)
    assert steps[0].elevation == 45.0


def test_midnight_reset_rain() -> None:
    """
    Hour 23: accum goes from 0.9 → 0.1 (midnight reset).
    Delta = -0.8 → rain = post-reset value = 0.1
    """
    steps = resample_history(FIXTURES / "history_midnight.csv", DEFAULT_SENSOR_MAP)
    hour_23 = next(s for s in steps if s.tod == 23)
    assert abs(hour_23.rain_inches - 0.1) < 0.001


def test_custom_sensor_map(tmp_path: Path) -> None:
    """A scenario-level sensor_map override renames entity IDs."""
    csv_text = (
        "entity_id,state,last_changed\n"
        "my.temp_sensor,72.0,2026-04-24T08:00:00.000Z\n"
        "my.accum_sensor,0.0,2026-04-24T08:00:00.000Z\n"
        "my.accum_sensor,0.2,2026-04-24T08:45:00.000Z\n"
        "my.rh_sensor,55,2026-04-24T08:00:00.000Z\n"
        "my.wind_sensor,3.0,2026-04-24T08:00:00.000Z\n"
        "my.cloud_sensor,20,2026-04-24T08:00:00.000Z\n"
        "my.elev_sensor,30.0,2026-04-24T08:00:00.000Z\n"
    )
    p = tmp_path / "custom.csv"
    p.write_text(csv_text)
    custom_map = {
        "temp":                "my.temp_sensor",
        "rh":                  "my.rh_sensor",
        "wind":                "my.wind_sensor",
        "clouds":              "my.cloud_sensor",
        "elevation":           "my.elev_sensor",
        "liquid_accumulation": "my.accum_sensor",
    }
    steps = resample_history(p, custom_map)
    assert len(steps) == 1
    assert steps[0].temp == 72.0
    assert abs(steps[0].rain_inches - 0.2) < 0.001
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_resampler.py -v 2>&1 | head -5
```

Expected: `ImportError: cannot import name 'resample_history' from 'lawn_rain_model.simulation.weather'`

- [ ] **Step 4: Add `resample_history()` to `lawn_rain_model/simulation/weather.py`**

Append to the existing file (after the `WeatherStep` dataclass):

```python
# lawn_rain_model/simulation/weather.py  (additions — append after WeatherStep)
from __future__ import annotations
from pathlib import Path
import pandas as pd


def resample_history(
    csv_path: Path | str,
    sensor_map: dict[str, str],
) -> list[WeatherStep]:
    """
    Convert a narrow-format HA history CSV into hourly WeatherStep objects.

    Resampling rules:
    - Slow sensors (temp, rh, wind, clouds, elevation): last observation
      carried forward (LOCF) to hourly boundaries.
    - Rain: positive delta of liquid_accumulation between hour boundaries.
      Negative deltas indicate a midnight reset; in that case rain equals
      the post-reset accumulation value for that period.

    Returns one WeatherStep per complete or partial clock hour present in
    the data, indexed 0, 1, 2, ... with tod set to the actual hour of day.
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, parse_dates=["last_changed"])
    df["last_changed"] = pd.to_datetime(df["last_changed"], utc=True)
    df["state"] = pd.to_numeric(df["state"], errors="coerce")
    df = df.dropna(subset=["state"])
    df = df.set_index("last_changed").sort_index()

    def _hourly_last(entity_id: str) -> pd.Series:
        sub = df[df["entity_id"] == entity_id]["state"]
        if sub.empty:
            return pd.Series(dtype=float)
        return sub.resample("h").last().ffill()

    temp_h  = _hourly_last(sensor_map["temp"])
    rh_h    = _hourly_last(sensor_map["rh"])
    wind_h  = _hourly_last(sensor_map["wind"])
    clouds_h = _hourly_last(sensor_map["clouds"])
    elev_h  = _hourly_last(sensor_map["elevation"])
    accum_h = _hourly_last(sensor_map["liquid_accumulation"])

    # Rain = diff of accumulation; handle midnight reset (negative delta)
    rain_h = accum_h.diff()
    midnight_reset = rain_h < 0
    rain_h[midnight_reset] = accum_h[midnight_reset]
    rain_h = rain_h.fillna(0.0)

    # Align all series to a common hourly index
    combined = pd.DataFrame({
        "temp":   temp_h,
        "rh":     rh_h,
        "wind":   wind_h,
        "clouds": clouds_h,
        "elev":   elev_h,
        "rain":   rain_h,
    }).dropna(subset=["temp"])  # require at least temp data each hour

    steps: list[WeatherStep] = []
    for idx, (ts, row) in enumerate(combined.iterrows()):
        steps.append(WeatherStep(
            hour=idx,
            tod=ts.hour,  # type: ignore[union-attr]
            temp=float(row["temp"]),
            rh=float(row["rh"]),
            wind=float(row["wind"]),
            clouds=float(row["clouds"]),
            elevation=float(row["elev"]),
            rain_inches=float(row["rain"]),
        ))

    return steps
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_resampler.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add lawn_rain_model/simulation/weather.py \
        tests/test_resampler.py \
        tests/fixtures/history_simple.csv \
        tests/fixtures/history_midnight.csv
git commit -m "feat: history resampler — HA CSV to hourly WeatherStep list"
```

---

## Task 12: History-Backed Runner + ScenarioLoader Integration

**Files:**
- Modify: `lawn_rain_model/simulation/runner.py` (add `run_scenario_from_history()` helper)
- Modify: `lawn_rain_model/cli/commands.py` (wire history_file into cmd_simulate)
- Create: `tests/test_history_runner.py`

The runner already accepts a `weather_steps` argument. This task adds:
1. A `build_weather_steps()` dispatcher that detects `history_file` and calls the resampler.
2. YAML scenario support: a scenario with `history_file` set ignores `rain_events`/`weather`.
3. Tests using the real `history.csv` from the project.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_history_runner.py
"""Integration tests: history CSV → WeatherStep → run_scenario."""
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.calibration.scenarios import Scenario, ScenarioLoader
from lawn_rain_model.simulation.runner import run_scenario, build_weather_steps, hours_to_mow
from lawn_rain_model.simulation.weather import DEFAULT_SENSOR_MAP

PROJECT_HISTORY = Path("history.csv")


@pytest.mark.skipif(
    not PROJECT_HISTORY.exists(),
    reason="history.csv not present",
)
def test_real_history_produces_steps() -> None:
    steps = build_weather_steps(
        Scenario(
            name="real",
            duration_hours=0,   # ignored when history_file is set
            rain_events=[],
            weather=None,
            history_file=str(PROJECT_HISTORY),
        ),
        base_path=Path("."),
    )
    assert len(steps) > 0


@pytest.mark.skipif(
    not PROJECT_HISTORY.exists(),
    reason="history.csv not present",
)
def test_real_history_runner_completes() -> None:
    model = SingleLayerModel()
    s = Scenario(
        name="real",
        duration_hours=0,
        rain_events=[],
        weather=None,
        history_file=str(PROJECT_HISTORY),
        mow_threshold=5.0,
    )
    steps = build_weather_steps(s, base_path=Path("."))
    rows = run_scenario(s, model, model.default_params, weather_steps=steps)
    assert len(rows) == len(steps)
    assert all("wetness_out" in r for r in rows)


def test_history_scenario_from_yaml(tmp_path: Path) -> None:
    """ScenarioLoader populates history_file and sensor_map correctly."""
    hist_csv = tmp_path / "test_history.csv"
    hist_csv.write_text(
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:30:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.5,2026-04-24T10:45:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,40.0,2026-04-24T11:00:00.000Z\n"
    )

    yaml_text = textwrap.dedent(f"""\
        scenarios:
          - name: history_test
            history_file: {hist_csv}
            mow_threshold: 5.0
            calibration:
              target_hours: 12.0
              weight: 1.0
    """)
    yaml_file = tmp_path / "scenarios.yaml"
    yaml_file.write_text(yaml_text)

    scenarios = ScenarioLoader.load(yaml_file)
    assert len(scenarios) == 1
    s = scenarios[0]
    assert s.history_file == str(hist_csv)
    assert s.calibration is not None
    assert s.calibration.target_hours_min == 12.0
    assert s.calibration.target_hours_max == 12.0


def test_history_scenario_runs_end_to_end(tmp_path: Path) -> None:
    """Full pipeline: YAML → ScenarioLoader → build_weather_steps → run_scenario."""
    hist_csv = tmp_path / "hist.csv"
    hist_csv.write_text(
        "entity_id,state,last_changed\n"
        "sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_temperature_0h,74.0,2026-04-24T11:30:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_current_day_liquid_accumulation,0.3,2026-04-24T10:30:00.000Z\n"
        "sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z\n"
        "sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z\n"
        "sensor.sun_elevation,40.0,2026-04-24T11:00:00.000Z\n"
    )
    model = SingleLayerModel()
    s = Scenario(
        name="e2e",
        duration_hours=0,
        rain_events=[],
        weather=None,
        history_file=str(hist_csv),
        mow_threshold=5.0,
    )
    steps = build_weather_steps(s, base_path=tmp_path)
    rows = run_scenario(s, model, model.default_params, weather_steps=steps)
    assert len(rows) > 0
    assert rows[0]["rain_inches"] > 0   # 0.3" fell in hour 10
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_history_runner.py -v 2>&1 | head -10
```

Expected: `ImportError: cannot import name 'build_weather_steps'`

- [ ] **Step 3: Add `build_weather_steps()` dispatcher to `lawn_rain_model/simulation/runner.py`**

Replace the private `_build_weather_steps` with a public dispatcher:

```python
# lawn_rain_model/simulation/runner.py — replace _build_weather_steps with:

def build_weather_steps(
    scenario: Scenario,
    base_path: Path | None = None,
) -> list[WeatherStep]:
    """
    Build the hourly WeatherStep list for a scenario.

    If scenario.history_file is set, resample the CSV.
    Otherwise, generate steps from scenario.weather + solar model.
    """
    from pathlib import Path as _Path
    if scenario.history_file:
        from lawn_rain_model.simulation.weather import resample_history, DEFAULT_SENSOR_MAP
        csv_path = _Path(scenario.history_file)
        if base_path and not csv_path.is_absolute():
            csv_path = base_path / csv_path
        sensor_map = {**DEFAULT_SENSOR_MAP, **scenario.sensor_map}
        return resample_history(csv_path, sensor_map)
    else:
        assert scenario.weather is not None, (
            f"Scenario '{scenario.name}' has no history_file and no weather block."
        )
        w = scenario.weather
        rain_map = {e.hour: e.inches for e in scenario.rain_events}
        steps: list[WeatherStep] = []
        for h in range(scenario.duration_hours):
            tod = (scenario.start_hour + h) % 24
            elev = (
                sun_elevation(tod, scenario.day_of_year, scenario.latitude)
                if scenario.use_solar_model
                else w.elevation
            )
            steps.append(WeatherStep(
                hour=h, tod=tod,
                temp=w.temp, rh=w.rh, wind=w.wind, clouds=w.clouds,
                elevation=elev,
                rain_inches=rain_map.get(h, 0.0),
            ))
        return steps
```

Also update `run_scenario` to call `build_weather_steps` when `weather_steps` is None:

```python
# In run_scenario(), replace:
#   if weather_steps is None:
#       weather_steps = _build_weather_steps(scenario)
# with:

    if weather_steps is None:
        weather_steps = build_weather_steps(scenario)
```

- [ ] **Step 4: Wire history_file into `cmd_simulate` in `lawn_rain_model/cli/commands.py`**

In `cmd_simulate`, the existing loop already calls `run_scenario(s, model, params)` which
internally calls `build_weather_steps`. No change needed — the Scenario dataclass already
carries `history_file`. Verify by running the smoke test in Step 5.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_history_runner.py -v
```

Expected: all non-skipped tests PASS. The `real_history_*` tests PASS if `history.csv`
is present in the working directory.

- [ ] **Step 6: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add lawn_rain_model/simulation/runner.py lawn_rain_model/cli/commands.py \
        tests/test_history_runner.py
git commit -m "feat: history-backed scenario pipeline — CSV → WeatherStep → run_scenario"
```

---

## Task 13: End-to-End Smoke Tests

These are manual CLI runs to validate the full stack. Run from the project root.

- [ ] **Step 1: Simulate a YAML scenario**

```bash
python simulator.py simulate -f scenarios.yaml -n calib_warm_partly_cloudy --summary-only
```

Expected output includes: `HIT   target=10-16h  got=Xh` where X is 10–16.

- [ ] **Step 2: Simulate with history file**

Create `scenarios_history_test.yaml`:

```yaml
scenarios:
  - name: real_event_2026_04_24
    history_file: history.csv
    mow_threshold: 5.0
    initial_wetness: 0.0
    calibration:
      target_hours: 12
      weight: 1.0
      note: "observed dry at hour 12 — update with your actual observation"
```

```bash
python simulator.py simulate -f scenarios_history_test.yaml --summary-only
```

Expected: simulation runs for N hours (length of history.csv), prints summary with mow time.

- [ ] **Step 3: Run optimizer**

```bash
python simulator.py optimize -f scenarios.yaml --save-params params_optimized.yaml
```

Expected: converges (or reports partial convergence), saves `params_optimized.yaml`.

- [ ] **Step 4: Compare default vs optimized params**

```bash
python simulator.py simulate -f scenarios.yaml \
    -P params_default.yaml params_optimized.yaml \
    --summary-only
```

Expected: markdown comparison table printed showing ✓/FAST/SLOW for each scenario.

- [ ] **Step 5: Type-check**

```bash
mypy lawn_rain_model/ --ignore-missing-imports
```

Expected: zero errors (or only `[no-untyped-def]` from scipy stubs — acceptable).

- [ ] **Step 6: Full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 7: Final commit**

```bash
git add scenarios_history_test.yaml params_optimized.yaml
git commit -m "chore: smoke test artifacts + final integration verified"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Task |
|---|---|
| Package refactor with clear module boundaries | Tasks 1–10 |
| Type hints throughout | All implementation tasks (typed signatures) |
| Unit tests for core logic | Tasks 3–7, 11–12 |
| Protocol-based model interface (structural subtyping) | Task 2 |
| Multi-layer model extensibility (can plug in new model) | Task 2 — Protocol contract, runner is model-agnostic |
| Point target (`target_hours`) in scenarios.yaml | Tasks 6–7 |
| Range target (`target_hours_min/max`) preserved | Tasks 6–7 |
| History CSV → simulation | Tasks 11–12 |
| Midnight reset handling | Task 11 |
| Custom sensor map per scenario | Tasks 11–12 |
| `history_file` in YAML scenarios | Task 12 |
| Full CLI parity with original `simulator.py` | Task 10 |
| Optimizer uses new interface | Task 8 |
| `params_default.yaml` still loads cleanly | Task 10 (`_load_params`) |
| Existing `scenarios.yaml` loads without modification | Task 7 (test_existing_scenarios_yaml_loads) |

**Placeholder scan:** None found. All code blocks are complete.

**Type consistency check:**
- `WeatherStep` defined in Task 2, used in Tasks 3, 5, 11, 12 ✓
- `LawnModel` Protocol defined in Task 2; `SingleLayerModel.step()` returns `dict[str, float]`
  matching the Protocol's declared return type ✓
- `StepResult` shape (runner dict keys): `hour`, `tod`, `can_mow`, `elevation`, `rain_inches`,
  `wetness_in`, `wetness_out`, `drying_rate`, `diagnostics` — consistent across runner (Task 5),
  display (Task 9), CSV output (Task 10) ✓
- `build_weather_steps()` introduced in Task 12, referenced in Task 13 smoke test ✓
- `run_scenario()` signature: `(scenario, model, params, weather_steps=None)` — consistent
  across Tasks 5, 12, 13 ✓
- `scenario_loss(h2m, target, duration)` — consistent across Tasks 6, 7, 8, 9 ✓
