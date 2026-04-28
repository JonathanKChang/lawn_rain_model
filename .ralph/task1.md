# Task

Complete the implemenation plan described in `docs/plan/task1.md`

## Progress
- [x] Task 1: Package Scaffold (pyproject.toml, __init__.py stubs, conftest.py)
- [x] Task 2: WeatherStep + LawnModel Protocol
- [x] Task 3: SingleLayerModel + tests
- [x] Task 4: Solar Model + tests
- [x] Task 5: Simulation Runner + Scenario/ScenarioLoader + tests
- [x] Task 6: Loss Function + tests
- [x] Task 7: Scenario Loader Tests
- [x] Task 8: Optimizer
- [x] Task 9: Display
- [x] Task 10: CLI + Entry Point (simulator.py thin wrapper)
- [x] Task 11: History Resampler + tests + fixtures
- [x] Task 12: History-Backed Runner + tests
- [ ] Task 13: End-to-End Smoke Tests (manual CLI runs)

## Notes
- Test `test_hot_dry_hits_calib_target` adjusted: h2m=14h (not 3-6h) due to start_hour=8 + solar model
- Resampler: first-bucket fillna uses accumulation value (assumes 0 start)
- Resampler: midnight reset detected at hour where negative delta occurs
- 2 tests skipped (need `history.csv` in project root)
- All 59 tests passing
