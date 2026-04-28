#!/usr/bin/env python3
"""
Lawn Wetness Index Simulator + Optimizer
Mirrors the Home Assistant Jinja2 model exactly.
All rate constants assume a 1-hour update interval.
"""

import argparse
import csv as csv_mod
import math
import sys
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import differential_evolution


# ---------------------------------------------------------------------------
# Default model parameters (all tunable by the optimizer)
# ---------------------------------------------------------------------------

DEFAULT_PARAMS = {
    # Evaporation
    "base_evap":       0.06,    # base evap rate at calibration point (60F, 60% RH)
    "vpd_norm_denom":  0.40,    # VPD normalization denominator
    "e_sat_base":      1.0393,  # Clausius-Clapeyron per-degree multiplier
    "vpd_min":         0.02,    # floor to prevent zero-VPD stall

    # Solar
    "sun_coeff":       0.18,    # max solar contribution to evap
    "cloud_exp":       1.40,    # exponent on (1 - cloud_fraction)
    "solar_exp":       0.70,    # exponent on (elevation/90)

    # Wind
    "wind_coeff":      0.022,   # evap gain per mph
    "wind_cap":        0.50,    # max wind contribution

    # Soil regimes
    "stage_thresh":    18.0,    # index where stage 2 -> stage 1 completes
    "pool_thresh":     40.0,    # index where standing water begins
    "capillary_rate":  0.05,    # fraction/hr drained by capillary from soil portion
    "pool_drain_coef": 0.12,    # fraction/hr drained from pool depth

    # Rain input
    "rain_mult":       40.0,    # inches -> index multiplier

    # Viscosity correction on capillary rate
    # Water viscosity rises ~1.5%/degF below 70F, slowing capillary wicking.
    # visc_factor = max(1.0 - (70 - temp) * visc_slope, visc_floor)
    "visc_slope":      0.015,   # fractional rate reduction per degF below 70
    "visc_floor":      0.35,    # minimum visc_factor (near-freezing floor)
}

PARAM_BOUNDS = {
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


# ---------------------------------------------------------------------------
# Core model -- parameterized
# ---------------------------------------------------------------------------

def step(wetness, temp, rh, wind, clouds, elevation, rain_inches=0.0, p=None):
    if p is None:
        p = DEFAULT_PARAMS

    # Rain input
    pre_dry = min(wetness + rain_inches * p["rain_mult"], 100.0)

    # VPD
    e_sat_rel = p["e_sat_base"] ** (temp - 60)
    vpd_raw   = e_sat_rel * ((100 - rh) / 100.0)
    vpd       = max(vpd_raw, p["vpd_min"])
    vpd_norm  = vpd / p["vpd_norm_denom"]

    # Solar
    cloud_factor    = ((100 - clouds) / 100) ** p["cloud_exp"]
    solar_intensity = (max(elevation, 0.0) / 90) ** p["solar_exp"] if elevation > 0 else 0.0
    sun_factor      = p["sun_coeff"] * cloud_factor * solar_intensity

    # Wind
    wind_factor = min(wind * p["wind_coeff"], p["wind_cap"])

    # Stage 1/2 transition
    stage_factor = min(pre_dry / p["stage_thresh"], 1.0)

    # Evaporation
    evap_rate = (p["base_evap"] + wind_factor + sun_factor) * vpd_norm * stage_factor

    # Pooling
    pool_depth = max(pre_dry - p["pool_thresh"], 0.0)
    pool_drain = pool_depth * p["pool_drain_coef"]

    # Capillary sink (soil portion only) with viscosity correction.
    # Cold water is more viscous: capillary flow slows proportionally.
    # visc_factor=1.0 at 70F, attenuates linearly below that, floored at visc_floor.
    soil_wetness   = min(pre_dry, p["pool_thresh"])
    visc_factor    = max(1.0 - (70.0 - temp) * p["visc_slope"], p["visc_floor"])
    capillary_sink = soil_wetness * p["capillary_rate"] * visc_factor

    drying_rate = pool_drain + capillary_sink + evap_rate
    new_wetness = max(pre_dry - drying_rate, 0.0)

    return {
        "wetness_in":      wetness,
        "rain_inches":     rain_inches,
        "pre_dry":         pre_dry,
        "vpd_norm":        vpd_norm,
        "sun_factor":      sun_factor,
        "wind_factor":     wind_factor,
        "stage_factor":    stage_factor,
        "evap_rate":       evap_rate,
        "pool_drain_rate": pool_drain,
        "capillary_sink":  capillary_sink,
        "visc_factor":     visc_factor,
        "drying_rate":     drying_rate,
        "wetness_out":     new_wetness,
    }


# ---------------------------------------------------------------------------
# Solar model
# ---------------------------------------------------------------------------

def sun_elevation(hour_of_day, day_of_year=172, lat=39.0):
    declination = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
    hour_angle  = 15.0 * (hour_of_day - 12.0)
    lat_r       = math.radians(lat)
    dec_r       = math.radians(declination)
    ha_r        = math.radians(hour_angle)
    sin_elev    = (math.sin(lat_r) * math.sin(dec_r)
                   + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r))
    return math.degrees(math.asin(max(min(sin_elev, 1.0), -1.0)))


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WeatherConditions:
    temp:      float = 75.0
    rh:        float = 60.0
    wind:      float = 5.0
    clouds:    float = 30.0
    elevation: float = 45.0


@dataclass
class RainEvent:
    hour:   int
    inches: float


@dataclass
class CalibrationTarget:
    target_hours_min: float
    target_hours_max: float
    weight:           float = 1.0
    note:             str   = ""


@dataclass
class Scenario:
    name:            str
    duration_hours:  int
    rain_events:     list
    weather:         WeatherConditions
    mow_threshold:   float = 5.0
    initial_wetness: float = 0.0
    use_solar_model: bool  = True
    start_hour:      int   = 6
    day_of_year:     int   = 172
    latitude:        float = 39.0
    calibration:     Optional[CalibrationTarget] = None


# ---------------------------------------------------------------------------
# Simulation runner
# ---------------------------------------------------------------------------

def run_scenario(scenario, p=None):
    if p is None:
        p = DEFAULT_PARAMS

    rain_map = {e.hour: e.inches for e in scenario.rain_events}
    wetness  = scenario.initial_wetness

    elev_profile = None
    if scenario.use_solar_model:
        elev_profile = [
            sun_elevation((scenario.start_hour + h) % 24, scenario.day_of_year, scenario.latitude)
            for h in range(scenario.duration_hours)
        ]

    rows = []
    for h in range(scenario.duration_hours):
        rain      = rain_map.get(h, 0.0)
        elevation = elev_profile[h] if scenario.use_solar_model else scenario.weather.elevation

        result              = step(wetness, scenario.weather.temp, scenario.weather.rh,
                                   scenario.weather.wind, scenario.weather.clouds,
                                   elevation, rain, p)
        result["hour"]      = h
        result["tod"]       = (scenario.start_hour + h) % 24
        result["can_mow"]   = result["wetness_out"] <= scenario.mow_threshold
        result["elevation"] = elevation
        rows.append(result)
        wetness = result["wetness_out"]

    return rows


def hours_to_mow(rows, threshold):
    for r in rows:
        if r["wetness_out"] <= threshold:
            return r["hour"]
    return None


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def scenario_loss(h2m, target, duration):
    """
    Returns squared normalized distance outside [target_min, target_max].
    0.0 if within range.  Penalizes 'never' as if h2m == duration.
    """
    if h2m is None:
        h2m = duration
    t_min = target.target_hours_min
    t_max = target.target_hours_max
    span  = t_max - t_min
    if t_min <= h2m <= t_max:
        return 0.0
    elif h2m < t_min:
        return ((t_min - h2m) / span) ** 2
    else:
        return ((h2m - t_max) / span) ** 2


def build_objective(calibration_scenarios, base_p, tunable_keys):
    def objective(vec):
        p = base_p.copy()
        for k, v in zip(tunable_keys, vec):
            p[k] = v
        if p["stage_thresh"] >= p["pool_thresh"]:
            return 1e6
        total = 0.0
        for s in calibration_scenarios:
            rows = run_scenario(s, p)
            h2m  = hours_to_mow(rows, s.mow_threshold)
            loss = scenario_loss(h2m, s.calibration, s.duration_hours)
            total += loss * s.calibration.weight
        return total
    return objective


_iter_count = [0]

def _progress_cb(xk, convergence):
    _iter_count[0] += 1
    if _iter_count[0] % 50 == 0:
        print(f"  iter={_iter_count[0]:>5}  convergence={convergence:.8f}", end="\r", flush=True)


def run_optimizer(calibration_scenarios, frozen=None, maxiter=2000,
                  popsize=20, tol=1e-5, seed=42):
    frozen = frozen or {}
    tunable_keys = [k for k in PARAM_BOUNDS if k not in frozen]
    bounds       = [PARAM_BOUNDS[k] for k in tunable_keys]

    base_p = DEFAULT_PARAMS.copy()
    base_p.update(frozen)

    print(f"\nOptimizing {len(tunable_keys)} parameters across "
          f"{len(calibration_scenarios)} calibration scenarios")
    print(f"Frozen: {list(frozen.keys()) or 'none'}")
    print(f"Popsize={popsize}  maxiter={maxiter}  tol={tol}\n")

    _iter_count[0] = 0
    result = differential_evolution(
        build_objective(calibration_scenarios, base_p, tunable_keys),
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
    print()  # newline after progress

    best_p = base_p.copy()
    for k, v in zip(tunable_keys, result.x):
        best_p[k] = v

    return {
        "params":       best_p,
        "loss":         result.fun,
        "success":      result.success,
        "message":      result.message,
        "iterations":   result.nit,
        "tunable_keys": tunable_keys,
    }


def print_optimizer_report(opt, calibration_scenarios):
    p       = opt["params"]
    tunable = set(opt["tunable_keys"])

    print(f"\n{'='*72}")
    print(f"  OPTIMIZER RESULT  loss={opt['loss']:.6f}  "
          f"iter={opt['iterations']}  "
          f"{'converged' if opt['success'] else 'DID NOT CONVERGE'}")
    print(f"{'='*72}")

    print(f"\n  {'Parameter':<20} {'Default':>10} {'Optimized':>12} {'Delta':>10}  Frozen")
    print("  " + "-" * 58)
    for k, dv in DEFAULT_PARAMS.items():
        ov     = p[k]
        delta  = ov - dv
        frozen = "yes" if k not in tunable else ""
        big    = "  <--" if abs(delta / max(abs(dv), 1e-9)) > 0.20 and not frozen else ""
        print(f"  {k:<20} {dv:>10.4f} {ov:>12.5f} {delta:>+10.4f}  {frozen:>5}{big}")

    print(f"\n  {'Scenario':<35} {'Target':>10} {'Got':>6} {'Loss':>8}  Status")
    print("  " + "-" * 65)
    for s in calibration_scenarios:
        rows = run_scenario(s, p)
        h2m  = hours_to_mow(rows, s.mow_threshold)
        loss = scenario_loss(h2m, s.calibration, s.duration_hours)
        t    = s.calibration
        tstr = f"{t.target_hours_min:.0f}-{t.target_hours_max:.0f}h"
        gstr = f"{h2m}h" if h2m is not None else f">{s.duration_hours}h"
        if loss == 0:
            status = "OK"
        elif (h2m or 999) < t.target_hours_min:
            status = "TOO FAST"
        else:
            status = "TOO SLOW"
        note = f"  [{t.note}]" if t.note else ""
        print(f"  {s.name:<35} {tstr:>10} {gstr:>6} {loss:>8.4f}  {status}{note}")

    print(f"\n  Total weighted loss: {opt['loss']:.6f}")

    # Jinja2 snippet
    print(f"\n{'='*72}")
    print("  JINJA2 CONSTANTS (drop into your template)")
    print("=" * 72)
    print(f"""
{{#- Optimized params (loss={opt['loss']:.5f}) -#}}
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


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

def load_scenarios(path, include_calibration=True):
    raw = yaml.safe_load(Path(path).read_text())
    out = []
    for s in raw.get("scenarios", []):
        w = s.get("weather", {})
        weather = WeatherConditions(
            temp=w.get("temp", 75.0), rh=w.get("rh", 60.0),
            wind=w.get("wind", 5.0),  clouds=w.get("clouds", 30.0),
            elevation=w.get("elevation", 45.0),
        )
        rain_events = [RainEvent(e["hour"], e["inches"])
                       for e in s.get("rain_events", [])]

        cal = None
        if "calibration" in s and include_calibration:
            c   = s["calibration"]
            cal = CalibrationTarget(
                target_hours_min=c["target_hours_min"],
                target_hours_max=c["target_hours_max"],
                weight=c.get("weight", 1.0),
                note=c.get("note", ""),
            )

        out.append(Scenario(
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
        ))
    return out


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

BAR_WIDTH = 40

def sparkline(value, p=None):
    if p is None:
        p = DEFAULT_PARAMS
    filled = max(0, min(BAR_WIDTH, int(round(value / 100.0 * BAR_WIDTH))))
    bar    = list("█" * filled + "·" * (BAR_WIDTH - filled))
    for thresh in [p["stage_thresh"], p["pool_thresh"]]:
        idx = int(thresh / 100.0 * BAR_WIDTH)
        if 0 <= idx < BAR_WIDTH and bar[idx] == "·":
            bar[idx] = "|"
    return "".join(bar)


def print_table(rows, scenario, p=None):
    if p is None:
        p = DEFAULT_PARAMS
    rain_col = 'Rain"'
    hdr = (f"{'Hr':>3}  {'ToD':>5}  {rain_col:>5}  "
           f"{'Wet':>5}  {'Evap':>5}  {'Pool':>5}  {'Cap':>5}  {'Visc':>4}  {'Dry':>5}  "
           f"{'VPD':>4}  {'Elev':>5}  {'Index':>{BAR_WIDTH+2}}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        w      = r["wetness_out"]
        regime = ("pool" if r["pre_dry"] > p["pool_thresh"] else
                  "sat " if r["pre_dry"] > p["stage_thresh"] else "dry ")
        mow    = "  [MOW]" if r["can_mow"] else ""
        bar    = sparkline(w, p)
        rs     = f"{r['rain_inches']:.2f}" if r["rain_inches"] > 0 else "     "
        print(f"{r['hour']:>3}  {r['tod']:>02d}:00  {rs:>5}  "
              f"{w:>5.1f}  {r['evap_rate']:>5.3f}  {r['pool_drain_rate']:>5.3f}  "
              f"{r['capillary_sink']:>5.3f}  {r['visc_factor']:>4.2f}  {r['drying_rate']:>5.3f}  "
              f"{r['vpd_norm']:>4.2f}  {r['elevation']:>+5.1f}  "
              f"[{bar}] {regime}{mow}")


def print_summary(rows, scenario, p=None):
    if p is None:
        p = DEFAULT_PARAMS
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


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_simulate(args):
    p = DEFAULT_PARAMS.copy()
    if args.params_file:
        override = yaml.safe_load(Path(args.params_file).read_text()).get("params", {})
        p.update(override)

    if args.scenario_file:
        scenarios = load_scenarios(args.scenario_file)
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
            name="cli", duration_hours=args.hours, rain_events=rain_events,
            mow_threshold=args.threshold, initial_wetness=args.initial,
            weather=WeatherConditions(temp=args.temp, rh=args.rh,
                                      wind=args.wind, clouds=args.clouds),
            use_solar_model=not args.no_solar,
            start_hour=args.start_hour, day_of_year=args.day_of_year, latitude=args.lat,
        )]

    for s in scenarios:
        rows = run_scenario(s, p)
        print(f"\n{'='*80}\n  {s.name.upper()}\n{'='*80}")
        if not args.summary_only:
            print_table(rows, s, p)
        print_summary(rows, s, p)

        if args.csv:
            csv_path = Path(args.csv) if len(scenarios) == 1 else Path(f"{s.name}.csv")
            with open(csv_path, "w", newline="") as f:
                w = csv_mod.DictWriter(f, fieldnames=rows[0].keys())
                w.writeheader()
                w.writerows(rows)
            print(f"  CSV -> {csv_path}")


def cmd_sweep(args):
    p = DEFAULT_PARAMS.copy()
    if args.params_file:
        override = yaml.safe_load(Path(args.params_file).read_text()).get("params", {})
        p.update(override)

    rain_vals = [float(x) for x in args.rain_inches.split(",")]
    print(f"\nDrying sweep  threshold={args.threshold}  "
          f"[{args.temp}F  RH={args.rh}%  wind={args.wind}mph  clouds={args.clouds}%]")
    print(f"{'Rain':>8}  {'Peak':>6}  {'Mow@':>6}")
    print("-" * 28)

    for rain in rain_vals:
        s = Scenario(
            name=f"{rain}in", duration_hours=args.hours,
            rain_events=[RainEvent(0, rain)],
            weather=WeatherConditions(temp=args.temp, rh=args.rh,
                                      wind=args.wind, clouds=args.clouds),
            mow_threshold=args.threshold, use_solar_model=not args.no_solar,
            start_hour=args.start_hour, day_of_year=args.day_of_year, latitude=args.lat,
        )
        rows  = run_scenario(s, p)
        h2m   = hours_to_mow(rows, args.threshold)
        peak  = max(r["wetness_out"] for r in rows)
        print(f"  {rain:>5.2f}\"  peak={peak:>5.1f}  "
              f"{str(h2m)+'h' if h2m is not None else '>'+str(args.hours)+'h'}")


def cmd_optimize(args):
    all_scenarios = load_scenarios(args.scenario_file, include_calibration=True)
    cal_scenarios = [s for s in all_scenarios if s.calibration is not None]

    if not cal_scenarios:
        sys.exit("No calibration targets found in YAML. Add 'calibration:' blocks.")

    if args.only:
        names = {n.strip() for n in args.only.split(",")}
        cal_scenarios = [s for s in cal_scenarios if s.name in names]

    frozen = {}
    for spec in (args.freeze or []):
        k, v = spec.split("=")
        frozen[k.strip()] = float(v.strip())

    opt = run_optimizer(
        cal_scenarios, frozen=frozen,
        maxiter=args.maxiter, popsize=args.popsize,
        tol=args.tol, seed=args.seed,
    )

    print_optimizer_report(opt, cal_scenarios)

    if args.save_params:
        out = {"params": {k: float(round(v, 6)) for k, v in opt["params"].items()}}
        Path(args.save_params).write_text(yaml.dump(out, default_flow_style=False))
        print(f"\n  Params saved -> {args.save_params}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser():
    root = argparse.ArgumentParser(prog="lawn_sim")
    sub  = root.add_subparsers(dest="cmd", required=True)

    # simulate
    sim = sub.add_parser("simulate")
    sim.add_argument("-f", "--scenario-file")
    sim.add_argument("-n", "--name")
    sim.add_argument("-P", "--params-file")
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
    sim.add_argument("--csv")

    # sweep
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

    # optimize
    opt = sub.add_parser("optimize")
    opt.add_argument("-f", "--scenario-file", required=True)
    opt.add_argument("--only",        help="Comma-separated scenario names to use")
    opt.add_argument("--freeze",      nargs="*", metavar="PARAM=VALUE")
    opt.add_argument("--save-params", metavar="FILE")
    opt.add_argument("--maxiter",     type=int,   default=2000)
    opt.add_argument("--popsize",     type=int,   default=20)
    opt.add_argument("--tol",         type=float, default=1e-5)
    opt.add_argument("--seed",        type=int,   default=42)

    return root


def main():
    args = build_parser().parse_args()
    {"simulate": cmd_simulate, "sweep": cmd_sweep, "optimize": cmd_optimize}[args.cmd](args)


if __name__ == "__main__":
    main()
