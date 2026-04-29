# TODO: Scoring Module for Code1

## Goal
Add a scoring module to Code1 that evaluates model predictions against ground truth for history-backed calibration scenarios, following TDD practices and integrating with the existing CLI.

## Tasks

### 1. Write tests first (TDD)

- [ ] 1.1 Write `tests/test_scoring.py` with tests for:
  - `score_scenario()` with a history scenario that has a calibration target (returns score dict with predicted/target/error/loss/status)
  - `score_scenario()` with a scenario that has NO calibration target (returns status="NO_TARGET")
  - `score_scenario()` with a scenario where the lawn never dries below threshold (returns status="NEVER_DRIED")
  - `score_all_scenarios()` with multiple scenarios (returns list of score dicts)
  - Use `tmp_path` for CSV fixtures (follows pattern from `test_history_runner.py`)
  - Use `pytest` fixtures from `conftest.py` (model, default_params)

### 2. Implement scoring module

- [ ] 2.1 Create `lawn_rain_model/calibration/scoring.py` with:
  - `score_scenario(scenario, model, params)` — runs scenario, computes hours_to_mow, compares against `scenario.calibration`, returns dict with keys: `name`, `predicted_hours`, `target_hours`, `error_hours`, `loss`, `status`
  - `score_all_scenarios(scenarios, model, params)` — maps `score_scenario` over list
  - `print_score_report(scores)` — formatted terminal table (Scenario | Predicted | Target | Error | Loss | Status)
  - Status labels: `CLOSE` (error < 1h), `MODERATE` (error < 3h), `POOR` (error >= 3h), `NO_TARGET` (no calibration), `NEVER_DRIED` (lawn never dries)
  - Adapt from Code2's `scoring.py` but use Code1's `CalibrationTarget` (not `target_hours`), always-dict `params`, and Code1's `hours_to_mow` (became_wet logic)

### 3. Add CLI command

- [ ] 3.1 Add `score` subcommand to `cli/commands.py`:
  - `lawn_rain_model score -f scenarios.yaml [--params-file params.yaml]`
  - Loads scenarios via `ScenarioLoader`, filters to those with calibration targets
  - Runs `score_all_scenarios`, prints report via `print_score_report`
  - Add argparse args: `--scenario-file` (required), `--params-file` (optional), `--name` (optional filter)
  - Follow existing command patterns (cmd_simulate, cmd_optimize, etc.)

### 4. Integration and documentation

- [ ] 4.1 Update `README.md` with scoring section:
  - How to use `lawn_rain_model score` command
  - What the output means (status labels, loss interpretation)
  - Example usage with a history scenario YAML

### 5. Verify and commit

- [ ] 5.1 Run `pytest tests/test_scoring.py` — all pass
- [ ] 5.2 Run `pytest` (full suite) — nothing broken
- [ ] 5.3 Run `mypy` — no type errors
- [ ] 5.4 Test CLI end-to-end: `lawn_rain_model score -f scenarios/scenarios_history.yaml`

## Notes

- **Adaptation from Code2**: Code1's `Scenario` uses `calibration: CalibrationTarget` (with `target_hours_min`/`max`) instead of a bare `target_hours` field. The scoring logic must check `scenario.calibration` instead of `scenario.target_hours`.
- **Params handling**: Code1's `params` is always `dict[str, float]` (never `None`), so no defensive `(params or {}).get()` pattern needed.
- **hours_to_mow**: Code1 uses "became_wet" logic (skips initial dry period) — more correct for history CSVs that start dry.
- **Loss function**: Code1 already has `calibration/loss.py` with `scenario_loss()` — scoring module reuses this.
- **TDD discipline**: Write all tests in Task 1 BEFORE implementing scoring.py in Task 2. Tests must fail first.
- **Atomic commits**: Each task group should be a separate commit.
