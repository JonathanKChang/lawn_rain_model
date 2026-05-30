## ADDED Requirements

### Requirement: Flask server serves the frontend application
The system SHALL run a Flask HTTP server that serves the single-page frontend application on localhost.

#### Scenario: Server starts on default port
- **WHEN** user runs `python simulator.py serve`
- **THEN** the Flask server starts on `http://localhost:5000` and serves the frontend application

#### Scenario: Server starts on custom port
- **WHEN** user runs `python simulator.py serve --port 8080`
- **THEN** the Flask server starts on `http://localhost:8080`

#### Scenario: Server discovers YAML files automatically
- **WHEN** the server starts
- **THEN** it scans the `scenarios/` directory for YAML files and makes them available via the API

### Requirement: REST API provides simulation endpoints
The system SHALL expose REST API endpoints that wrap existing Python simulation modules.

#### Scenario: POST /api/simulate returns wetness curve
- **WHEN** a client POSTs a scenario definition to `/api/simulate`
- **THEN** the server runs `run_scenario()` and returns a JSON response with the wetness curve data points (hour, wetness, diagnostics)

#### Scenario: POST /api/simulate with parameter overrides
- **WHEN** a client POSTs a scenario with custom parameters to `/api/simulate`
- **THEN** the server applies the parameter overrides and returns the simulation result using those parameters

#### Scenario: GET /api/params returns parameter definitions
- **WHEN** a client GETs `/api/params`
- **THEN** the server returns all 16 parameter names, their default values, and their valid bounds

### Requirement: REST API provides optimization endpoints
The system SHALL expose REST API endpoints that wrap the differential evolution optimizer.

#### Scenario: POST /api/optimize starts optimization
- **WHEN** a client POSTs optimization parameters (scenario names, max iterations, population size, frozen parameters) to `/api/optimize`
- **THEN** the server starts the optimization in a background thread and returns a job ID

#### Scenario: GET /api/optimize/status checks progress
- **WHEN** a client GETs `/api/optimize/status?job=<id>`
- **THEN** the server returns the current iteration, best loss, and completion status

#### Scenario: GET /api/optimize/result returns final parameters
- **WHEN** a client GETs `/api/optimize/result?job=<id>` after optimization completes
- **THEN** the server returns the optimized parameter set and the comparison score report

### Requirement: REST API provides file operation endpoints
The system SHALL expose REST API endpoints for file upload, download, and YAML management.

#### Scenario: POST /api/import-history uploads CSV
- **WHEN** a client POSTs a CSV file to `/api/import-history`
- **THEN** the server processes the CSV using the existing resampler and returns the weather steps summary

#### Scenario: POST /api/scenarios saves scenario YAML
- **WHEN** a client POSTs a scenario definition to `/api/scenarios`
- **THEN** the server appends or updates the scenario in the appropriate YAML file

#### Scenario: GET /api/scenarios lists available scenarios
- **WHEN** a client GETs `/api/scenarios`
- **THEN** the server returns all scenarios from all discovered YAML files with their names, weather conditions, and calibration targets

### Requirement: Server handles concurrent requests safely
The system SHALL serve the frontend and API endpoints concurrently without blocking.

#### Scenario: Frontend serves while API processes
- **WHEN** a client is loading the frontend while another client triggers a simulation
- **THEN** both requests are handled without blocking each other

#### Scenario: Optimization does not block other requests
- **WHEN** an optimization job is running in the background
- **THEN** other API requests (simulate, list scenarios) are processed normally
