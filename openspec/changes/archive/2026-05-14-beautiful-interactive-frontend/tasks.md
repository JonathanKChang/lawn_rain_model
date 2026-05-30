## 1. Project scaffolding and server foundation

- [x] 1.1 Create `frontend/` directory structure (server.py, static/, templates/)
- [x] 1.2 Create Flask app in `frontend/server.py` with basic route serving index.html
- [x] 1.3 Add `serve` subcommand to CLI (`simulator.py`) that launches the Flask server
- [x] 1.4 Add `--port` argument to the serve command (default 5000)
- [x] 1.5 Implement YAML file auto-discovery in `scenarios/` directory
- [x] 1.6 Implement `GET /api/params` endpoint returning all 16 parameters with defaults and bounds
- [x] 1.7 Implement `GET /api/scenarios` endpoint returning all scenarios from discovered YAML files

## 2. Core simulation API

- [x] 2.1 Implement `POST /api/simulate` endpoint wrapping `run_scenario()`
- [x] 2.2 Implement parameter override support in the simulate endpoint
- [x] 2.3 Implement `POST /api/optimize` endpoint starting optimization in background thread
- [x] 2.4 Implement `GET /api/optimize/status` endpoint for progress polling
- [x] 2.5 Implement `GET /api/optimize/result` endpoint returning final optimization results
- [x] 2.6 Implement `POST /api/import-history` endpoint for CSV upload and processing
- [x] 2.7 Implement `POST /api/scenarios` endpoint for saving/updating scenario YAML
- [x] 2.8 Implement `POST /api/sweep` endpoint for single-parameter sensitivity sweeps
- [x] 2.9 Implement thread-safe job registry for concurrent optimization jobs

## 3. Frontend shell and navigation

- [x] 3.1 Create `templates/index.html` with SPA shell, navigation sidebar, and main content area
- [x] 3.2 Create `static/css/style.css` with CSS variables, layout, and base typography
- [x] 3.3 Implement client-side routing for 6 pages: Simulate, Parameters, Optimize, Import, Results, Sensitivity
- [x] 3.4 Implement navigation sidebar with active state highlighting
- [x] 3.5 Create responsive layout with CSS Grid (sidebar + main content)
- [x] 3.6 Implement Chart.js integration with CDN loading

## 4. Wetness curve chart component

- [x] 4.1 Create `static/js/charts.js` with reusable chart initialization function
- [x] 4.2 Implement wetness curve time-series chart (x-axis: hours, y-axis: wetness 0–100)
- [x] 4.3 Add mow threshold horizontal line to the chart (configurable, default 5.0)
- [x] 4.4 Add mow time marker annotation on the chart
- [x] 4.5 Implement multi-curve overlay with distinct colors and legend
- [x] 4.6 Add calibration target range as shaded band on the chart
- [x] 4.7 Implement chart tooltip showing hour, wetness, and diagnostics on hover
- [x] 4.8 Add rain event markers (vertical dashed lines) on the chart

## 5. Scenario Builder page

- [x] 5.1 Implement scenario list view with search/filter functionality
- [x] 5.2 Implement scenario detail card showing weather, rain events, and calibration target
- [x] 5.3 Create scenario editor form with weather inputs (temp, rh, wind, clouds)
- [x] 5.4 Implement rain event add/remove/reorder UI
- [x] 5.5 Implement solar model toggle and configuration (start hour, day of year, latitude)
- [x] 5.6 Implement initial wetness input
- [x] 5.7 Wire up live simulation preview (debounced API call on any field change)
- [x] 5.8 Implement mow-readiness indicator component (green/yellow/red status badge)
- [x] 5.9 Implement save scenario to YAML (POST /api/scenarios)
- [x] 5.10 Implement export scenario as standalone YAML download
- [x] 5.11 Implement scenario templates (Hot Sunny, Cold Rainy, etc.)
- [x] 5.12 Implement multi-select comparison view with overlaid wetness curves

## 6. Parameter Explorer page

- [x] 6.1 Implement parameter grid layout showing all 16 parameters
- [x] 6.2 Create custom slider component with min/max bounds and numeric input
- [x] 6.3 Implement parameter tooltips with descriptions and physical meaning
- [x] 6.4 Wire parameter changes to debounced simulation re-run (200ms debounce)
- [x] 6.5 Implement parameter preset save/load/delete with localStorage persistence
- [x] 6.6 Implement preset dropdown selector
- [x] 6.7 Implement comparison mode overlay (default vs current curve)
- [x] 6.8 Highlight parameters that differ from default with delta percentage
- [x] 6.9 Implement "Advanced mode" toggle for bounds editing
- [x] 6.10 Implement bounds adjustment UI and reset-to-defaults button

## 7. Optimization Dashboard page

- [x] 7.1 Implement optimization configuration panel (iterations, population, tolerance, seed)
- [x] 7.2 Implement scenario selection checkboxes for optimization inclusion
- [x] 7.3 Implement parameter freeze controls (toggle + value input for frozen params)
- [x] 7.4 Wire up "Start Optimization" button to POST /api/optimize
- [x] 7.5 Implement progress bar showing iteration count and elapsed time
- [x] 7.6 Implement real-time best-loss convergence chart
- [x] 7.7 Implement parameter convergence table showing current/best/default values
- [x] 7.8 Implement "Stop Optimization" button (interrupt background job)
- [x] 7.9 Implement results display: parameter comparison table with % change
- [x] 7.10 Highlight parameters changed >20% with warning indicator
- [x] 7.11 Implement score report display (mow time, target, error, loss, status per scenario)
- [x] 7.12 Implement "Export Parameters" as YAML download
- [x] 7.13 Implement job queue management (one at a time, queue new jobs)

## 8. History Importer page

- [x] 8.1 Implement drag-and-drop CSV upload zone
- [x] 8.2 Implement file size validation (5MB max) and format validation
- [x] 8.3 Implement multi-file upload support
- [x] 8.4 Implement auto-detection of standard Pirate Weather sensor entity IDs
- [x] 8.5 Implement custom sensor mapping interface for non-standard entities
- [x] 8.6 Implement missing sensor warnings
- [x] 8.7 Implement weather data table preview (first 20 rows)
- [x] 8.8 Implement weather data multi-axis chart (temp, humidity, wind over time)
- [x] 8.9 Implement rain event summary card (total, count, peak rate)
- [x] 8.10 Wire up "Simulate" button to run history-backed simulation
- [x] 8.11 Implement add rain events on top of history weather
- [x] 8.12 Implement calibration target setting for history scenarios
- [x] 8.13 Implement save history scenario to YAML with CSV copy to `scenarios/history/`
- [x] 8.14 Implement re-load saved history scenario

## 9. Results Browser page

- [x] 9.1 Implement results list table (scenario, preset, timestamp, mow time, peak wetness)
- [x] 9.2 Implement filter by scenario and filter by preset
- [x] 9.3 Implement sortable columns (click header to sort)
- [x] 9.4 Implement result detail view with wetness curve chart
- [x] 9.5 Implement diagnostics breakdown table (evap, pool drain, capillary, viscosity)
- [x] 9.6 Implement mow-readiness timeline visualization
- [x] 9.7 Implement multi-select comparison with overlaid curves
- [x] 9.8 Implement calibration target bands on comparison chart
- [x] 9.9 Implement export single result as CSV download
- [x] 9.10 Implement export comparison as CSV download
- [x] 9.11 Implement "Save as Scenario" YAML download
- [x] 9.12 Implement localStorage persistence for results
- [x] 9.13 Implement "Clear All Results" with confirmation dialog

## 10. Sensitivity Analyzer page

- [x] 10.1 Implement parameter selection dropdown (all 16 params)
- [x] 10.2 Implement sweep configuration (step count, min/max overrides)
- [x] 10.3 Wire up "Run Sweep" button to POST /api/sweep
- [x] 10.4 Implement wetness curve overlay chart for sweep results
- [x] 10.5 Implement mow time vs parameter value scatter plot
- [x] 10.6 Implement peak wetness vs parameter value scatter plot
- [x] 10.7 Implement multi-sweep comparison view
- [x] 10.8 Implement normalized sensitivity ranking chart
- [x] 10.9 Implement sensitivity result save to localStorage
- [x] 10.10 Implement export sweep as CSV download
- [x] 10.11 Implement re-run saved sweep from history
- [x] 10.12 Implement most influential parameters summary (top 3 highlighted)
- [x] 10.13 Implement low-sensitivity parameter flagging

## 11. Polish and documentation

- [x] 11.1 Implement loading states and spinners for all async operations
- [x] 11.2 Implement error handling with user-friendly toast notifications
- [x] 11.3 Implement keyboard shortcuts (Ctrl+S to save, Ctrl+R to re-simulate)
- [x] 11.4 Add page title and favicon
- [x] 11.5 Implement smooth transitions between pages
- [x] 11.6 Add `frontend/README.md` with usage instructions
- [x] 11.7 Add `docs/frontend.md` with architecture overview and API reference
- [x] 11.8 Test all endpoints with the existing CLI parameter sets
- [x] 11.9 Test with existing history CSV files in `scenarios/history/`
- [x] 11.10 Add accessibility improvements (ARIA labels, keyboard navigation)
- [x] 11.11 Final visual polish: colors, spacing, typography refinement
