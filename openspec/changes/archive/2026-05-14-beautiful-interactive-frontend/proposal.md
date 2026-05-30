# Proposal: Beautiful Interactive Frontend for Lawn Rain Model

## Why

The Lawn Rain Model is a sophisticated physics-based simulator with 16 tunable parameters, 6+ calibration scenarios, and rich visualization potential — but it is entirely CLI-driven. Users must edit YAML files, run commands, and parse terminal output to explore scenarios, tune parameters, and compare results. This creates a high barrier to experimentation and makes the model inaccessible to non-technical users. A beautiful interactive frontend would transform this from a developer tool into a powerful visual sandbox for understanding lawn drying dynamics.

## What Changes

- **Web-based frontend** served via a lightweight Python HTTP server (no Node.js build step required)
- **Scenario Builder** — visually construct weather scenarios (temp, humidity, wind, clouds, rain events, timing) with live preview
- **Interactive Parameter Explorer** — adjust all 16 model parameters via sliders with real-time wetness curve updates
- **Model Comparison** — side-by-side parameter sets (default vs optimized vs custom) with overlaid wetness curves
- **Optimization Dashboard** — run differential evolution optimization from the UI, watch convergence, freeze individual parameters, compare pre/post results
- **History CSV Import** — upload Home Assistant history CSV files and instantly simulate with real weather data
- **Result Browser** — browse simulation history, filter by scenario/params, export results as CSV
- **Parameter Sensitivity Matrix** — sweep one parameter at a time to see its effect on mow time and peak wetness
- **Mow-Readiness Timeline** — prominent visual indicator showing when the lawn becomes mowable for any scenario
- **Export** — save scenarios as YAML, export parameter sets, download simulation results as CSV

## Capabilities

### New Capabilities

- `frontend-server`: Python backend HTTP server that serves the SPA and exposes REST API endpoints for simulation, optimization, scenario management, and file operations
- `scenario-editor`: Interactive UI for building and editing weather scenarios with real-time simulation preview
- `parameter-explorer`: Visual parameter tuning interface with sliders, bounds control, and live wetness curve updates
- `optimization-dashboard`: UI for running and monitoring differential evolution optimization with parameter freezing and comparison
- `history-importer`: File upload interface for Home Assistant CSV history files with automatic sensor mapping and simulation
- `results-browser`: Browse, filter, compare, and export simulation results with persistent storage
- `sensitivity-analyzer`: Parameter sweep tool for sensitivity analysis with visual output

### Modified Capabilities

<!-- None — this is a new capability layer on top of the existing Python backend -->

## Impact

- **New dependencies**: Flask (or FastAPI) for the backend API, no frontend build toolchain needed — pure HTML/CSS/JS served statically
- **New files**: `frontend/` directory with `server.py`, static assets, and API routes
- **Existing code**: No changes to core simulation, calibration, or model code — the frontend consumes the existing Python modules via direct imports
- **API surface**: New REST endpoints wrapping existing `run_scenario()`, `optimize()`, `score_all_scenarios()`, and CSV import logic
- **Backwards compatibility**: CLI interface remains unchanged; frontend is an additive layer
