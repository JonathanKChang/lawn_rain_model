# lawn_rain_model/models/single_layer.py
"""
Single-layer surface wetness model.

Mirrors the Home Assistant Jinja2 model exactly.
All rate constants assume a 1-hour update interval; they are divided
by ``steps_per_hour`` (from the WeatherStep) for sub-hourly resolution.

Because all drying mechanisms are linear in wetness
(pool_drain = depth×coef, capillary = soil_wetness×rate,
evaporation = base×factors×stage_factor), linear scaling is
mathematically stable at any step size.
"""
from __future__ import annotations
import math
from lawn_rain_model.simulation.weather import WeatherStep
from lawn_rain_model.simulation.solar import solar_intensity_taylor

_DEFAULT_PARAMS: dict[str, float] = {
    "base_evap":       0.06,
    "vpd_norm_denom":  0.40,
    "e_sat_base":      1.0393,
    "vpd_min":         0.02,
    "sun_coeff":       0.18,
    "cloud_exp":       1.40,
    "wind_coeff":      0.022,
    "wind_cap":        0.50,
    "stage_thresh":    18.0,
    "pool_thresh":     40.0,
    "capillary_rate":  0.05,
    "pool_drain_coef": 0.12,
    "rain_mult":       40.0,
    "visc_slope":      0.015,
    "visc_floor":      0.35,
    "mow_threshold":   5.0,
}

_PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "base_evap":       (0.01,  0.20),
    "vpd_norm_denom":  (0.15,  0.80),
    "e_sat_base":      (1.020, 1.060),
    "vpd_min":         (0.005, 0.05),
    "sun_coeff":       (0.05,  0.50),
    "cloud_exp":       (0.50,  2.50),
    "wind_coeff":      (0.005, 0.06),
    "wind_cap":        (0.20,  1.00),
    "stage_thresh":    (8.0,   30.0),
    "pool_thresh":     (25.0,  60.0),
    "capillary_rate":  (0.02,  0.35),
    "pool_drain_coef": (0.05,  0.40),
    "rain_mult":       (20.0,  70.0),
    "visc_slope":      (0.005, 0.030),
    "visc_floor":      (0.20,  0.60),
    "mow_threshold":   (1.0,  20.0),
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

        # Time-step scaling: all rates are per-hour, divide by
        # steps_per_hour for sub-hourly resolution.
        sph = weather.steps_per_hour

        # Rain input (capped at 100)
        pre_dry = min(wetness + weather.rain_inches * p["rain_mult"], 100.0)

        # VPD
        e_sat_rel = p["e_sat_base"] ** (weather.temp - 60)
        vpd_raw   = e_sat_rel * ((100 - weather.rh) / 100.0)
        vpd       = max(vpd_raw, p["vpd_min"])
        vpd_norm  = vpd / p["vpd_norm_denom"]

        # Solar — Taylor expansion of sin(elevation) handles wrap-around
        cloud_factor = ((100 - weather.clouds) / 100) ** p["cloud_exp"]
        solar_intensity = solar_intensity_taylor(weather.elevation)
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
        # Scale down for sub-hourly steps; return unscaled for display
        wetness_out = max(pre_dry - drying_rate / sph, 0.0)

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
