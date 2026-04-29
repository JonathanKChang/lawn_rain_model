# lawn_rain_model/cli/display.py
"""Terminal display helpers. Reads SingleLayerModel diagnostics by known key names."""
from __future__ import annotations
from typing import Any
from lawn_rain_model.calibration.scenarios import Scenario
from lawn_rain_model.simulation.runner import hours_to_mow

BAR_WIDTH = 40


def sparkline(value: float, stage_thresh: float = 18.0, pool_thresh: float = 40.0) -> str:
    if value != value:  # NaN check
        return "[????????????????????????????????????????]"
    filled = max(0, min(BAR_WIDTH, int(round(value / 100.0 * BAR_WIDTH))))
    bar = list("\u2588" * filled + "\u00b7" * (BAR_WIDTH - filled))
    for thresh in [stage_thresh, pool_thresh]:
        idx = int(thresh / 100.0 * BAR_WIDTH)
        if 0 <= idx < BAR_WIDTH and bar[idx] == "\u00b7":
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


def print_summary(rows: list[dict[str, Any]], scenario: Scenario, params: dict[str, float]) -> None:
    first_mow = hours_to_mow(rows, params["mow_threshold"])
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
    mow_th  = p["mow_threshold"]

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
        h2m  = hours_to_mow(rows, mow_th)
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
