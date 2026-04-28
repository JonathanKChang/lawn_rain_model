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
        return "\u2713"
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
                "> \u2713 = within target range  "
                "\u00b7 FAST = below target min  "
                "\u00b7 SLOW = above target max\n\n"
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
