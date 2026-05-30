# Design: Beautiful Interactive Frontend for Lawn Rain Model

## Context

The Lawn Rain Model is a Python package with a physics-based wetness simulator, parameter optimizer, and CLI interface. It has no existing web layer. The codebase uses:
- **Python 3.14** with a `.venv` (virtual environment)
- **Flask** is already installed in the venv (visible in `.venv/bin/flask`)
- **Core modules**: `simulation/runner.py`, `models/single_layer.py`, `calibration/optimizer.py`, `calibration/scenarios.py`
- **Configuration**: `params_default.yaml`, `scenarios/scenarios.yaml`
- **No Node.js, no build step** — the project is pure Python

The user wants a rich interactive experience: scenario building, parameter tuning, optimization, CSV import, result browsing, and sensitivity analysis — all visually compelling.

## Goals / Non-Goals

**Goals:**
- Zero friction to start: `python simulator.py serve` launches the full application
- No build step, no npm, no bundler — pure HTML/CSS/JS + Flask
- Real-time simulation feedback as parameters change
- Persistent state via browser localStorage (scenarios, parameter presets, results)
- Beautiful, distinctive visual design matching the outdoor/nature domain
- Full parity with CLI capabilities (simulate, optimize, sweep, score, import)

**Non-Goals:**
- Real-time WebSocket updates (HTTP polling/synchronous is fine for this domain)
- User authentication or multi-user support (single-user personal tool)
- Mobile-first responsive design (desktop-first, but usable on tablets)
- Docker packaging or deployment infrastructure
- Plugin architecture or third-party integrations

## Decisions

### 1. Backend: Flask (not FastAPI)
**Decision**: Use Flask as the HTTP server.
**Rationale**: Flask is already installed in the venv. The project is lightweight, synchronous, and doesn't need async I/O. Flask's simplicity matches the scope. FastAPI would require additional dependencies and async refactoring.
**Alternatives considered**:
- FastAPI: Better for large APIs, but adds async complexity and uvicorn dependency
- Static file server + Python script: Too limited for optimization and file upload

### 2. Frontend: Vanilla HTML/CSS/JS + Chart.js (no framework)
**Decision**: Pure HTML/CSS/JavaScript with Chart.js for visualizations.
**Rationale**: No build step requirement. Chart.js provides excellent time-series charts for wetness curves. The app is interactive but doesn't need a component framework's complexity. Vanilla JS keeps the dependency count at zero for the frontend.
**Alternatives considered**:
- React/Vue: Would require a build step (Vite/Webpack), adding complexity
- Alpine.js: Lightweight but Chart.js integration is more complex
- D3.js: Overkill for the chart types needed (line charts, bar charts, scatter plots)

### 3. State Management: localStorage + server-side optimization
**Decision**: Browser localStorage for scenarios, presets, and results. Server-side for long-running optimization jobs.
**Rationale**: Scenarios and parameter presets are small enough for localStorage. Optimization runs (which can take minutes) must be server-side to avoid browser timeouts.
**Data flow**:
- Scenarios, presets, results → localStorage (persistent across sessions)
- Optimization state → Flask session + in-memory job tracker
- File uploads → server temp directory → processed → results stored in localStorage as summary

### 4. API Design: REST endpoints wrapping existing Python modules
**Decision**: New Flask routes that directly call existing functions.
**Rationale**: Zero refactoring of core code. The existing `run_scenario()`, `optimize()`, `score_all_scenarios()` functions are the source of truth.
**Endpoints**:
```
POST   /api/simulate          — Run scenario, return wetness curve data
GET    /api/scenarios         — List all scenarios from YAML files
POST   /api/scenarios         — Save new/edited scenario to YAML
GET    /api/params            — Get current parameter set
POST   /api/params            — Update parameters, return new simulation
POST   /api/optimize          — Start optimization job
GET    /api/optimize/status   — Check optimization progress
GET    /api/optimize/result   — Get optimization result
POST   /api/import-history    — Upload CSV, return simulation data
GET    /api/results           — List saved results
GET    /api/results/<id>      — Get result details
POST   /api/sweep             — Run parameter sweep
GET    /api/params-default    — Get default parameter definitions (with bounds)
```

### 5. Visual Design: Organic/earthy aesthetic
**Decision**: Design language inspired by nature, weather, and outdoor landscapes.
**Rationale**: The domain is lawn wetness and weather — the visual identity should feel grounded, natural, and calm. Think dew on grass, overcast skies drying in the sun, rain puddles evaporating.
**Palette**: Deep forest greens, warm earth tones, sky blues, rain-grays. Accent color: amber (sunlight).
**Typography**: A distinctive serif for headings (evoking field guides, botanical illustrations) paired with a clean geometric sans-serif for data.
**Key visual metaphor**: The wetness curve is the hero — a large, beautiful time-series chart that fills the center of the screen, with controls around it.

### 6. File Structure
```
frontend/
├── server.py                 # Flask app, all API routes
├── static/
│   ├── css/
│   │   └── style.css         # All styling, CSS variables, animations
│   ├── js/
│   │   ├── app.js            # Main app controller, routing
│   │   ├── charts.js         # Chart.js initialization and updates
│   │   ├── scenarios.js      # Scenario builder logic
│   │   ├── parameters.js     # Parameter slider logic
│   │   ├── optimization.js   # Optimization dashboard logic
│   │   ├── history.js        # CSV import and results browser
│   │   └── sensitivity.js    # Parameter sweep logic
│   └── lib/
│       └── chart.umd.js      # Chart.js CDN reference (no download needed)
└── templates/
    └── index.html            # Single-page app shell
```

### 7. Simulation Engine Integration
**Decision**: Import and use existing modules directly in Flask routes.
**Rationale**: The existing modules are well-structured and don't need modification. The Flask server acts as a thin adapter layer.
**Import pattern**:
```python
from lawn_rain_model.simulation.runner import run_scenario, build_weather_steps
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.calibration.scenarios import ScenarioLoader
from lawn_rain_model.calibration.optimizer import optimize_parameters
from lawn_rain_model.calibration.scoring import score_all_scenarios
```

### 8. Result Persistence
**Decision**: Store results as JSON in localStorage with a structured key format.
**Rationale**: Results are small (a few KB per simulation). localStorage avoids any server-side storage complexity. Results include: simulation data, parameters used, scenario name, timestamp, and mow time.
**Key format**: `lrm_result_<timestamp>_<scenario_name>`

### 9. Optimization Job Handling
**Decision**: Synchronous execution with progress callbacks, running in a background thread.
**Rationale**: Optimization can take 1-5 minutes. A background thread prevents blocking the Flask request. Progress is checked via a polling endpoint.
**Implementation**: `concurrent.futures.ThreadPoolExecutor` with a shared job registry.

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large CSV files (10k+ rows) could slow simulation | Medium | Limit history file size to 5MB; chunk processing |
| Browser localStorage has ~5-10MB limit | Low | Store only summaries in localStorage; simulation data is transient |
| Optimization running in Flask thread could block other requests | Medium | Use ThreadPoolExecutor; limit to one optimization at a time |
| No auth means anyone on the network can access | Low | Designed as a single-user local tool; runs on localhost only |
| Chart.js bundle size on first load | Low | Use CDN; the library is ~200KB gzipped |
| CSS-only animations may not work in very old browsers | Low | Target modern browsers; graceful degradation |

## Migration Plan

This is a greenfield addition — no migration needed. The existing CLI continues to work unchanged.

1. **Phase 1**: Implement core server + simulate endpoint + wetness chart
2. **Phase 2**: Add scenario editor, parameter explorer, and comparison view
3. **Phase 3**: Add optimization dashboard, CSV import, and results browser
4. **Phase 4**: Add sensitivity analyzer, polish, and documentation

Each phase is independently testable. Users can start using the frontend after Phase 1.

## Open Questions

1. **Should the server auto-discover YAML files** in the `scenarios/` directory, or should users explicitly configure the path? → Auto-discover with configurable base path via query parameter.
2. **How many optimization iterations should run by default?** → Default to 500 iterations (vs CLI default 2000), with adjustable slider.
3. **Should parameter presets be saved server-side or client-side only?** → Client-side (localStorage) — simpler, no server state to manage.
