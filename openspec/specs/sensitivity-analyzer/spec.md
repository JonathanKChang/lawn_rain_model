# sensitivity-analyzer Specification

## Purpose
TBD - created by archiving change beautiful-interactive-frontend. Update Purpose after archive.
## Requirements
### Requirement: Users can run single-parameter sweeps
The system SHALL allow users to sweep one parameter across its range while holding all others constant.

#### Scenario: Select parameter to sweep
- **WHEN** the user opens the Sensitivity Analyzer
- **THEN** they can select any of the 16 parameters to sweep from a dropdown

#### Scenario: Configure sweep range and steps
- **WHEN** the user configures a sweep
- **THEN** they can set the number of steps (default 21, range 5–100) and the min/max values (defaulting to the parameter's bounds)

#### Scenario: Run single-parameter sweep
- **WHEN** the user clicks "Run Sweep"
- **THEN** the system runs a simulation for each parameter value and returns the results

### Requirement: Sensitivity results are displayed visually
The system SHALL display sweep results as interactive charts.

#### Scenario: Wetness curve overlay for sweep
- **WHEN** the user views sweep results
- **THEN** a chart displays all wetness curves from the sweep, with each curve labeled by its parameter value

#### Scenario: Mow time vs parameter value chart
- **WHEN** the user views sweep results
- **THEN** a scatter plot shows mow time (y-axis) versus the swept parameter value (x-axis), with a trend line

#### Scenario: Peak wetness vs parameter value chart
- **WHEN** the user views sweep results
- **THEN** a scatter plot shows peak wetness (y-axis) versus the swept parameter value (x-axis)

### Requirement: Users can compare sensitivity across multiple parameters
The system SHALL allow running and comparing sweeps for different parameters.

#### Scenario: Run multiple sweeps
- **WHEN** the user runs sweeps for multiple parameters
- **THEN** all sweep results are saved and can be viewed together

#### Scenario: Compare parameter sensitivities
- **WHEN** the user compares multiple sweeps
- **THEN** a normalized sensitivity chart shows the relative impact of each parameter on mow time (ranked by effect size)

### Requirement: Users can save and export sweep results
The system SHALL allow saving sweep results for later reference.

#### Scenario: Save sweep result
- **WHEN** the user clicks "Save Sweep"
- **THEN** the sweep configuration and results are saved to localStorage with a user-defined name

#### Scenario: Export sweep as CSV
- **WHEN** the user clicks "Export CSV" on a sweep result
- **THEN** a CSV file is downloaded with columns: parameter, parameter_value, mow_time, peak_wetness, total_loss

#### Scenario: Re-run saved sweep
- **WHEN** the user selects a saved sweep from the list
- **THEN** the sweep configuration is loaded and can be re-run with modified parameters

### Requirement: Sensitivity analysis guides parameter optimization
The system SHALL highlight parameters that have the greatest impact on mow time.

#### Scenario: Identify most influential parameters
- **WHEN** the user views the sensitivity analysis summary
- **THEN** parameters are ranked by their effect on mow time, with the top 3 highlighted

#### Scenario: Flag insensitive parameters
- **WHEN** a parameter's sweep produces less than 10% change in mow time across its full range
- **THEN** the parameter is flagged as "low sensitivity" suggesting it may be safely frozen during optimization

