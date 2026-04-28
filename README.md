# Lawn Rain Model

A physics-based **lawn wetness index** simulator and parameter optimizer for delaying robot mowers after rain. Models surface slip risk (not bulk soil moisture) using evaporation, solar radiation, wind, VPD, pooling, and capillary drainage — all calibrated to USDA loam reference drying times.

## Quick Start

### Install with `uv`

`uv` is the recommended way to install and develop this project. It's a fast Python package installer and resolver.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment and install dependencies
uv venv
source .venv/bin/activate          # or: .venv\Scripts\activate  on Windows
uv sync --extra dev                # install package + dev deps from pyproject.toml
```

### Install with `pip` (alternative)

```bash
pip install -e ".[dev]"
```

### Run with `uv run` (no activation needed)

```bash
uv run python simulator.py simulate -f scenarios.yaml -n calib_hot_sunny --summary-only
uv run python simulator.py sweep --temp 75 --rh 60
uv run python simulator.py optimize -f scenarios.yaml --save-params params_optimized.yaml
uv run python simulator.py simulate -f scenarios.yaml \
    -P params_default.yaml params_optimized.yaml --summary-only
```

### Develop with `uv`

```bash
# Install the project in editable mode (one-shot)
uv sync --extra dev

# Run the package script directly
uv run lawn_rain_model

# Run tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ -v --cov=lawn_rain_model --cov-report=term-missing

# Type checking
uv run mypy lawn_rain_model/ --ignore-missing-imports

# Sync dependencies (keeps .venv in sync with pyproject.toml)
uv sync --all-extras
```

## What It Models

The wetness index is a scalar value **0–100** representing surface water saturation. When it drops below a configurable threshold (default 5.0), the lawn is considered mowable.

### Three Physical Regimes

| Index Range | State | Dominant Drying Mechanism |
|---|---|---|
| 0 → `stage_thresh` (18) | Below field capacity | Stage 2 evaporation (soil-limited) |
| `stage_thresh` → `pool_thresh` (40) | Saturated surface, no pooling | Stage 1 evaporation (atmosphere-limited) |
| `pool_thresh` → 100 | Standing water in undulations | Pool drainage + Stage 1 evaporation |

### Drying Mechanisms

- **VPD-based evaporation** — Clausius-Clapeyron vapor pressure deficit couples temperature and humidity into a single drying driver. Calibration point: 60°F, 60% RH → VPD normalization = 1.0.
- **Solar radiation** — Sun elevation angle drives solar intensity: `(elevation/90)^solar_exp`. Automatically handles night (negative elevation → zero), winter, and dawn/dusk.
- **Wind** — Linear gain capped at `wind_cap`: `min(wind * wind_coeff, wind_cap)`.
- **Pool drainage** — Standing water above `pool_thresh` drains at `pool_drain_coef` per hour.
- **Capillary sink** — Soil wicks moisture downward, attenuated by a **viscosity correction** for cold temperatures (water viscosity increases ~60% at 38°F vs 70°F).

### Rain Input

Rain adds wetness: `wetness + rain_inches * rain_mult`, capped at 100. Above ~0.3" the surface saturates; additional rain extends drying via pooling rather than further increasing surface saturation.

## Architecture

```
lawn_rain_model/
├── models/
│   ├── protocol.py          # LawnModel Protocol (PEP 544) — model contract
│   └── single_layer.py      # SingleLayerModel — the wetness physics
├── simulation/
│   ├── solar.py             # Solar elevation angle model
│   ├── weather.py           # WeatherStep dataclass + history resampler
│   └── runner.py            # Model-agnostic scenario runner
├── calibration/
│   ├── scenarios.py         # Scenario, CalibrationTarget, ScenarioLoader
│   ├── loss.py              # scenario_loss() — range + point targets
│   └── optimizer.py         # Differential evolution parameter fitting
└── cli/
    ├── display.py           # Terminal tables, sparklines, summaries
    └── commands.py          # CLI: simulate, sweep, optimize
```

### Protocol-Based Models

The `LawnModel` Protocol (PEP 544) defines the contract any model must satisfy:

```python
class LawnModel(Protocol):
    @property
    def default_params(self) -> dict[str, float]: ...
    @property
    def param_bounds(self) -> dict[str, tuple[float, float]]: ...
    def initial_state(self, initial_wetness: float) -> Any: ...
    def surface_wetness(self, state: Any) -> float: ...
    def step(self, state, weather: WeatherStep, params) -> dict[str, float]: ...
```

Any class with these five attributes satisfies `LawnModel` — no inheritance required. The runner is model-agnostic: it consumes `WeatherStep` objects regardless of model internals. A future multi-layer model (e.g., `list[float]` state) can be plugged in without touching the runner.

## CLI Reference

### `simulate` — Run Scenario(s)

```bash
python simulator.py simulate -f scenarios.yaml -n calib_hot_sunny --summary-only
```

| Flag | Description | Default |
|---|---|---|
| `-f, --scenario-file` | YAML scenarios file | — |
| `-n, --name` | Filter to single scenario | all |
| `-P, --params-file` | Parameter override file(s) for comparison | default params |
| `--csv` | Output CSV file | — |
| `--summary-only` | Skip the detailed table | false |
| `--save-params FILE` | Save current params to file | — |
| `--compare-md FILE` | Write comparison table as markdown | — |

**Inline scenario** (no YAML file):
```bash
python simulator.py simulate \
    --rain 0:1.0 \
    --hours 48 --temp 85 --rh 30 --wind 10 --clouds 10 \
    --start-hour 8 --day-of-year 172 --lat 39.0 --summary-only
```

### `sweep` — Dryness Sweep

Tests how different rain amounts affect drying time:

```bash
python simulator.py sweep --temp 75 --rh 60 --wind 5 --clouds 30
```

```
Drying sweep  threshold=5.0  [75.0F  RH=60.0%  wind=5.0mph  clouds=30.0%]
    Rain    Peak    Mow@
----------------------------
   0.10"  peak=  3.7  0h
   0.25"  peak=  9.3  8h
   0.50"  peak= 18.6  17h
   0.75"  peak= 28.0  23h
   1.00"  peak= 37.5  28h
   1.50"  peak= 55.1  33h
   2.00"  peak= 72.7  36h
   2.50"  peak= 90.3  38h
```

### `optimize` — Parameter Fitting

```bash
python simulator.py optimize -f scenarios.yaml --save-params params_optimized.yaml
```

| Flag | Description | Default |
|---|---|---|
| `--only` | Comma-separated scenario names to include | all with weight > 0 |
| `--freeze PARAM=VALUE` | Freeze parameter (can repeat) | none |
| `--maxiter` | Max differential evolution iterations | 2000 |
| `--popsize` | Population size | 20 |
| `--tol` | Convergence tolerance | 1e-5 |
| `--seed` | Random seed | 42 |

The optimizer prints a comparison table showing each scenario's target range, actual mow time, and loss. Parameters that changed >20% from defaults are flagged with `<!--`.

## Scenario YAML

Scenarios are defined in YAML. Each scenario specifies weather conditions, rain events, and optionally a calibration target.

### Full Scenario Example

```yaml
scenarios:
  - name: calib_hot_sunny
    duration_hours: 48
    rain_events:
      - hour: 0        # hour offset from simulation start
        inches: 1.0    # rain depth in inches
    weather:
      temp: 85         # °F
      rh: 30           # relative humidity 0–100
      wind: 10         # mph
      clouds: 10       # 0–100
    use_solar_model: true    # use sun_elevation() vs fixed elevation
    start_hour: 8            # simulation start time (0–23)
    day_of_year: 172         # 172 = June 21 (summer solstice)
    latitude: 39.0           # degrees (e.g., 39.0 = mid-Atlantic US)
    initial_wetness: 0.0     # starting wetness (0–100)
    calibration:
      target_hours_min: 3
      target_hours_max: 6
      weight: 1.5            # 0 = observe only, don't fit
      note: "USDA loam: hot/sunny"
```

### Calibration Targets

Two formats:

**Range target** (most common):
```yaml
calibration:
  target_hours_min: 3
  target_hours_max: 6
  weight: 1.5
```

**Point target** (exact hour):
```yaml
calibration:
  target_hours: 14.0
  weight: 2.0
```

### History-Backed Scenarios

Use real weather data from a Home Assistant history export CSV:

```yaml
scenarios:
  - name: real_event_2026_04_24
    history_file: history.csv    # path relative to scenarios YAML
    calibration:
      target_hours: 12
      weight: 1.0
      note: "observed dry at hour 12"
    # Optional: override sensor entity IDs
    history_sensor_map:
      temp: sensor.my_temperature
      rh: sensor.my_humidity
```

## History CSV Format

The resampler expects a **narrow-format** Home Assistant history CSV:

```csv
entity_id,state,last_changed
sensor.pirateweather_temperature_0h,75.0,2026-04-24T10:00:00.000Z
sensor.pirateweather_temperature_0h,76.0,2026-04-24T10:30:00.000Z
sensor.pirateweather_current_day_liquid_accumulation,0.0,2026-04-24T10:00:00.000Z
sensor.pirateweather_current_day_liquid_accumulation,0.5,2026-04-24T10:45:00.000Z
sensor.pirateweather_humidity_0h,60,2026-04-24T10:00:00.000Z
sensor.pirateweather_wind_speed,5.0,2026-04-24T10:00:00.000Z
sensor.pirateweather_cloud_coverage,30,2026-04-24T10:00:00.000Z
sensor.sun_elevation,50.0,2026-04-24T10:00:00.000Z
sensor.sun_elevation,45.0,2026-04-24T10:30:00.000Z
```

**Resampling rules:**
- **Slow sensors** (temp, rh, wind, clouds, elevation): last observation carried forward (LOCF) to hourly boundaries.
- **Rain**: positive delta of `liquid_accumulation` between hour boundaries. Negative deltas indicate a midnight reset; rain equals the post-reset accumulation value.
- One `WeatherStep` per clock hour present in the data, indexed 0, 1, 2, ….

**Required sensors** (customizable via `history_sensor_map`):

| Logical Name | Default Entity ID |
|---|---|
| `temp` | `sensor.pirateweather_temperature_0h` |
| `rh` | `sensor.pirateweather_humidity_0h` |
| `wind` | `sensor.pirateweather_wind_speed` |
| `clouds` | `sensor.pirateweather_cloud_coverage` |
| `elevation` | `sensor.sun_elevation` |
| `liquid_accumulation` | `sensor.pirateweather_current_day_liquid_accumulation` |

## Parameters

All 16 parameters live in `params_default.yaml` (or any YAML with a `params:` key):

| Parameter | Default | Range | Description |
|---|---|---|---|
| `base_evap` | 0.060 | 0.01–0.20 | Base evaporation rate at calibration point (60°F, 60% RH) |
| `vpd_norm_denom` | 0.400 | 0.15–0.80 | VPD normalization denominator |
| `e_sat_base` | 1.0393 | 1.020–1.060 | Clausius-Clapeyron per-degree saturation multiplier |
| `vpd_min` | 0.020 | 0.005–0.050 | VPD floor to prevent zero-VPD stall |
| `sun_coeff` | 0.180 | 0.05–0.50 | Maximum solar contribution to evaporation |
| `cloud_exp` | 1.400 | 0.50–2.50 | Exponent on `(1 - cloud_fraction)` |
| `solar_exp` | 0.700 | 0.30–1.20 | Exponent on `(elevation/90)` |
| `wind_coeff` | 0.022 | 0.005–0.060 | Evaporation gain per mph |
| `wind_cap` | 0.500 | 0.20–1.00 | Maximum wind contribution |
| `stage_thresh` | 18.0 | 8.0–30.0 | Index where Stage 2 → Stage 1 evaporation transitions |
| `pool_thresh` | 40.0 | 25.0–60.0 | Index where standing water begins |
| `capillary_rate` | 0.050 | 0.02–0.35 | Fraction per hour drained by capillary action |
| `pool_drain_coef` | 0.120 | 0.05–0.40 | Fraction per hour drained from pool depth |
| `rain_mult` | 40.0 | 20.0–70.0 | Inches-to-index multiplier for rain input |
| `visc_slope` | 0.015 | 0.005–0.030 | Temperature sensitivity of capillary viscosity |
| `visc_floor` | 0.350 | 0.20–0.60 | Minimum viscosity factor (cold-temperature floor) |

## Extending with Custom Models

To add a new model (e.g., multi-layer soil profile):

1. Create a class with the five `LawnModel` Protocol methods.
2. Implement `step()` returning `{"wetness_out": ..., "drying_rate": ..., "diagnostics": {...}}`.
3. Pass it to `run_scenario()` instead of `SingleLayerModel`.

```python
from lawn_rain_model.models.protocol import LawnModel
from lawn_rain_model.simulation.weather import WeatherStep
from lawn_rain_model.simulation.runner import run_scenario

class MultiLayerModel:
    @property
    def default_params(self) -> dict[str, float]:
        return {...}

    @property
    def param_bounds(self) -> dict[str, tuple[float, float]]:
        return {...}

    def initial_state(self, initial_wetness: float) -> list[float]:
        return [initial_wetness, 0.0]  # surface + soil layers

    def surface_wetness(self, state: list[float]) -> float:
        return state[0]

    def step(self, state, weather: WeatherStep, params) -> dict[str, float]:
        # ... physics ...
        return {"wetness_out": surface_wetness, "drying_rate": total, "diagnostics": {...}}

model = MultiLayerModel()
rows = run_scenario(scenario, model, model.default_params)
```

## Testing

```bash
# Run all tests (with uv)
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ -v --cov=lawn_rain_model --cov-report=term-missing

# Type checking
uv run mypy lawn_rain_model/ --ignore-missing-imports

# Or with pip/activation:
pytest tests/ -v
```

**Test data:** The `tests/fixtures/` directory contains sample CSV and YAML files used by integration tests. See `test_history_runner.py` and `test_scenarios.py`.

**Test coverage:**
| Module | Tests |
|---|---|
| `test_single_layer.py` | 13 — physics correctness, Protocol compliance |
| `test_solar.py` | 5 — solar elevation angle |
| `test_runner.py` | 11 — scenario execution, weather generation |
| `test_loss.py` | 11 — range and point target loss |
| `test_scenarios.py` | 8 — YAML loading, calibration targets |
| `test_resampler.py` | 10 — HA CSV → WeatherStep, midnight reset |
| `test_history_runner.py` | 4 — end-to-end history pipeline |

## Parameter Optimization Notes

The optimizer uses scipy's `differential_evolution` with 16 tunable parameters across 6 calibration scenarios (weight > 0). The cold/night drainage scenario has weight=0 and is not used for fitting.

**Known parameter shifts from optimization:**
- `rain_mult` often drops from 40 → ~23 — consider freezing at 40 as a deliberate design choice
- `pool_thresh` often rises from 40 → ~58 — validate against your yard's actual pooling behavior
- `visc_floor` may rise from 0.35 → ~0.58 — physically suspect; the optimizer may be compensating elsewhere

To freeze parameters during optimization:
```bash
python simulator.py optimize -f scenarios.yaml \
    --freeze rain_mult=40 pool_thresh=40 \
    --save-params params_frozen.yaml
```


