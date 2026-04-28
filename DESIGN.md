## Lawn Wetness Index Model — Conversation Summary

### Project Goal

Build a Home Assistant Jinja2 automation that maintains a **lawn wetness index** to delay a robot mower after rain. The model targets **surface slip risk only** — not bulk soil moisture or field workability. Soil is loam (40% sand / 40% silt / 20% clay, USDA texture triangle). Update interval is hourly; all rate constants are calibrated to that interval.

---

### Architecture Decisions

**Surface focus over bulk drainage**
Gravitational (Darcy) drainage was explicitly rejected as a primary term. It operates on the 5–30cm bulk profile, not the top 1–2cm where slip risk lives, and would require a new parameter (saturated hydraulic conductivity Kₛ) that is yard-geometry-dependent and not derivable from USDA loam averages. The capillary sink was retained as the sole soil-side drying term, operating only on the soil portion of the index (below `pool_thresh`).

**Three-regime architecture**

| Index Range | Physical State | Dominant Mechanism |
|---|---|---|
| 0 → stage_thresh | Below field capacity | Stage 2 evap (soil-limited) |
| stage_thresh → pool_thresh | Saturated surface, no pooling | Stage 1 evap (atmosphere-limited) |
| pool_thresh → 100 | Standing water in undulations | Pool drainage + Stage 1 evap |

**VPD-based evaporation**
Separate `temp_factor` and `humidity_factor` terms were rejected — they create double-distortion of VPD. Both are captured in a single coupled term using a Clausius-Clapeyron approximation. Calibration point: 60°F, 60% RH → `vpd_norm = 1.0`.

**Solar model via elevation angle**
The `is_day` binary was replaced with `sun.sun` elevation attribute. The approximation `solar_intensity = (elevation / 90) ** solar_exp` automatically handles night (negative → zero), winter sun angle weakness, and dawn/dusk falloff. UV index was explicitly rejected — UV covers ~5% of solar energy bandwidth, and its correlative value is already captured by elevation + cloud_factor. Stacking it would triple-count.

**Rain input cap at index 100 with multiplier**
Above ~0.3" the surface saturates. Additional rain extends drying via pooling in undulations, not by further increasing the surface saturation index. Rain is capped: `min(wetness + rain_inches * rain_mult, 100)`. `rain_mult` started at 40 (design decision), though the optimizer later moved it to 23.3 — flagged as requiring physical validation before acceptance.

**Dew model is separate**
A separate dew model gates the mower independently and is not part of this model.

---

### Viscosity Correction Decision

**Problem identified:** The capillary sink ran at a fixed rate regardless of temperature. At 38°F, water viscosity is ~60% higher than at 70°F, which physically slows capillary flow. Without correction, the model over-predicts overnight drying in cold conditions — meaning when temps rise above the mow-temperature gate in the morning, the index reads lower than reality and the mower runs on wet ground.

**Decision:** Add a viscosity correction factor to the capillary sink:
```
visc_factor = max(1.0 - (70 - temp) * visc_slope, visc_floor)
capillary_sink = soil_wetness * capillary_rate * visc_factor
```
Both `visc_slope` and `visc_floor` are optimizer-tunable. Default values: slope=0.015/°F, floor=0.35. The optimizer moved `visc_floor` to 0.58, which is physically suspect and was flagged for review.

**The frost blind spot:** If temps drop to 38°F overnight and there is frost on the grass at dawn, the wetness index may clear threshold while the surface is still actually wet from melting frost. This is a known unresolved gap — the current sensor set (air temperature, not surface temperature) cannot see it.

---

### Calibration Target Decisions

**Reference source:** USDA loam drying times for 1" rain on flat terrain.

**Cold / nighttime drainage scenario — weight set to 0**

This was the central calibration dispute. The USDA 8–14h cold/night reference comes from **soil workability tables for farm equipment** (when does saturated loam reach field capacity for tractors). That measures bulk structural strength, not surface slip. Two reasons it doesn't apply:

1. Without evaporation, the capillary fringe wicks moisture back upward toward the surface as the bulk drains. A tractor compressing 15cm "feels" dry before the surface film a lightweight mower slides on has dissipated.
2. The mower has a minimum temperature lockout — below ~40–45°F the mower doesn't run regardless of wetness index. A surface-slip model doesn't need to be calibrated for a regime the mower never operates in.

**Decision:** Keep the scenario in YAML for observation, set `weight: 0`. Do not fit to it. The viscosity correction now handles the physics of cold-temperature capillary attenuation without needing this target to pull the optimizer. The cold/night scenario reported 33 hours after optimization — physically coherent for surface-slip scope, just diverging from the inapplicable bulk target as expected.

**Gravitational drainage rejected again in this context**
When the structural conflict between cold/night and cool/overcast targets was analyzed, reintroducing gravitational drainage was proposed as a solution. It was rejected again: it would introduce a Kₛ parameter that is yard-geometry-specific, front-load drying in a way that's physically disconnected from surface-slip measurement, and undermine the surface focus the model was specifically designed around.

---

### Calibration Scenarios (Final Set)

| Scenario | Conditions | Target | Weight | Rationale |
|---|---|---|---|---|
| calib_hot_sunny | 85°F, RH 30%, wind 10mph, clouds 10% | 3–6h | 1.5 | Tightest, most physically certain |
| calib_warm_partly_cloudy | 65°F, RH 60%, wind 5mph, clouds 50% | 10–16h | 2.0 | Most representative real-world condition |
| calib_cool_overcast | 50°F, RH 80%, wind 3mph, clouds 90% | 20–30h | 1.5 | Constrains low-VPD evap floor |
| calib_cold_night_drainage | 38°F, RH 95%, fixed night elevation | 8–14h | **0** | Observe only — bulk workability ref, wrong scope |
| calib_humid_summer | 80°F, RH 78%, wind 4mph, clouds 55% | 10–18h | 1.5 | Stresses VPD coupling at high temp + high RH |
| calib_high_wind | 75°F, RH 40%, wind 20mph, clouds 15% | 2–5h | 1.5 | Tests wind_coeff / wind_cap placement |
| calib_spring_morning | 58°F, RH 65%, wind 6mph, clouds 45% | 14–22h | 1.0 | Realistic mow-day scenario, mid-range sensitivity |

---

### Optimizer Results and Open Flags

The optimizer (scipy `differential_evolution`, 16 parameters, 6 active scenarios) converged to **loss = 0.0** — all six active scenarios hit their target windows.

**Three parameter shifts flagged for physical validation before HA deployment:**

`rain_mult: 40 → 23.3` — Large structural shift. Lower multiplier means 1" rain only pushes the index to ~23. If your yard is visibly wet/slippery after 1" rain, the original 40 may have been physically correct and the optimizer is compensating elsewhere. Recommended action: freeze `rain_mult=40` and re-run to see residual loss.

`pool_thresh: 40 → 58.6` — Pooling now starts much later. Requires physical validation: does your yard show visible surface water accumulation only after genuinely heavy rain, or does it happen at more moderate levels?

`visc_floor: 0.35 → 0.58` — Cold-temperature capillary floor is higher than viscosity physics supports (~0.35 is more defensible). The optimizer likely moved this to speed up cold-scenario drying without directly touching the zero-weighted cold/night scenario. Suspect value.

**Recommended next step:** Freeze `rain_mult=40` and `pool_thresh=40` as explicit design decisions about what the index *means*, then re-run the optimizer to see what residual loss emerges with those anchored. Those two parameters define the scale and geometry of the index itself — they should be chosen deliberately, not fitted.

---

### Diurnal Temperature Swing Handling

**Question:** If the night drops to 38°F (below the mow temperature gate) but the day rises to 50°F (above it), does the model handle this correctly?

**Answer:** Yes, for the evaporation terms — the model runs hourly with live sensor data, so VPD and solar terms automatically reflect actual conditions each hour. The explicit fix required was the viscosity correction: without it, the capillary sink over-dried overnight, making the index read falsely low when the temperature gate opened in the morning.