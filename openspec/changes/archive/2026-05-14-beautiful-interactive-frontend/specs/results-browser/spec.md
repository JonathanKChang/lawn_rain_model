## ADDED Requirements

### Requirement: Users can browse all saved simulation results
The system SHALL display a browsable list of all saved simulation results.

#### Scenario: Results list shows all results
- **WHEN** the user opens the Results Browser
- **THEN** all saved results are displayed in a table showing scenario name, parameter set name, timestamp, mow time, and peak wetness

#### Scenario: Filter results by scenario
- **WHEN** the user selects a scenario filter
- **THEN** only results matching that scenario are displayed

#### Scenario: Filter results by parameter preset
- **WHEN** the user selects a parameter preset filter
- **THEN** only results using that parameter set are displayed

#### Scenario: Sort results by column
- **WHEN** the user clicks a table column header
- **THEN** the results are sorted by that column (timestamp ascending/descending, mow time, peak wetness)

### Requirement: Users can view detailed result information
The system SHALL display full details for any saved simulation result.

#### Scenario: View result details
- **WHEN** the user clicks on a result in the list
- **THEN** a detail view shows the wetness curve chart, weather conditions, parameter values used, and calibration target

#### Scenario: View diagnostics breakdown
- **WHEN** the user expands the diagnostics section
- **THEN** a table shows the per-hour breakdown of evaporation rate, pool drain, capillary sink, and viscosity factor

#### Scenario: View mow-readiness timeline
- **WHEN** the user views the result details
- **THEN** a visual timeline shows the wetness curve with the mow threshold line and the predicted mow time marked

### Requirement: Users can compare multiple results
The system SHALL overlay multiple simulation results on the same chart for comparison.

#### Scenario: Select results to compare
- **WHEN** the user selects multiple results using checkboxes
- **THEN** a comparison chart displays all selected wetness curves overlaid with distinct colors

#### Scenario: Compare with calibration targets
- **WHEN** the comparison chart is active and results have calibration targets
- **THEN** the calibration target ranges are shown as shaded bands on the chart

### Requirement: Users can export results
The system SHALL allow exporting simulation results in multiple formats.

#### Scenario: Export single result as CSV
- **WHEN** the user clicks "Export CSV" on a result
- **THEN** a CSV file is downloaded containing all simulation data points (hour, sub_step, wetness, diagnostics)

#### Scenario: Export comparison as CSV
- **WHEN** the user exports a comparison of multiple results
- **THEN** a CSV file is downloaded with all comparison data points labeled by result

#### Scenario: Export result as YAML scenario
- **WHEN** the user clicks "Save as Scenario" on a result
- **THEN** a YAML file is downloaded with the scenario definition that produced the result

### Requirement: Results are persisted across sessions
The system SHALL persist simulation results in the browser so they survive page reloads.

#### Scenario: Results persist after page reload
- **WHEN** the user saves a result and reloads the page
- **THEN** the result is still present in the Results Browser

#### Scenario: Results survive browser restart
- **WHEN** the user closes and reopens the browser
- **THEN** all previously saved results are still available

#### Scenario: Clear all results
- **WHEN** the user clicks "Clear All Results"
- **THEN** all saved results are removed from localStorage with a confirmation dialog
