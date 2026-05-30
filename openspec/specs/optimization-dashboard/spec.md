# optimization-dashboard Specification

## Purpose
TBD - created by archiving change beautiful-interactive-frontend. Update Purpose after archive.
## Requirements
### Requirement: Users can configure optimization parameters
The system SHALL provide controls for all differential evolution optimization settings.

#### Scenario: Set max iterations
- **WHEN** the user opens the Optimization Dashboard
- **THEN** they can set the maximum number of iterations (default 500, range 50–5000)

#### Scenario: Set population size
- **WHEN** the user opens the Optimization Dashboard
- **THEN** they can set the population size (default 20, range 10–100)

#### Scenario: Set convergence tolerance
- **WHEN** the user opens the Optimization Dashboard
- **THEN** they can set the convergence tolerance (default 1e-5)

#### Scenario: Set random seed
- **WHEN** the user opens the Optimization Dashboard
- **THEN** they can set a random seed for reproducible optimization runs

### Requirement: Users can freeze individual parameters during optimization
The system SHALL allow users to lock specific parameters so the optimizer cannot change them.

#### Scenario: Freeze a parameter
- **WHEN** the user toggles the freeze control next to a parameter
- **THEN** that parameter is excluded from the optimization search space

#### Scenario: Freeze with specific value
- **WHEN** the user freezes a parameter and sets a specific value
- **THEN** the optimizer uses that value instead of searching that dimension

#### Scenario: View frozen parameters summary
- **WHEN** the user reviews the optimization configuration
- **THEN** all frozen parameters are listed with their frozen values

### Requirement: Users can select scenarios for optimization
The system SHALL allow users to choose which scenarios participate in the optimization.

#### Scenario: Select scenarios to include
- **WHEN** the user opens the Optimization Dashboard
- **THEN** all scenarios with weight > 0 are listed with checkboxes for inclusion

#### Scenario: Exclude scenarios from optimization
- **WHEN** the user unchecks a scenario
- **THEN** that scenario is excluded from the optimization but still included in the comparison output

#### Scenario: Optimize with only specific scenarios
- **WHEN** the user selects only one or two scenarios
- **THEN** the optimization runs using only those scenarios' calibration targets

### Requirement: Real-time optimization progress visualization
The system SHALL display optimization progress in real-time as the solver runs.

#### Scenario: Progress bar shows iteration count
- **WHEN** an optimization job is running
- **THEN** a progress bar shows the current iteration out of the maximum, along with elapsed time

#### Scenario: Best loss chart updates live
- **WHEN** an optimization job is running
- **THEN** a chart displays the best loss value at each iteration, showing convergence behavior

#### Scenario: Parameter convergence display
- **WHEN** an optimization job is running
- **THEN** a table shows each parameter's current best value, its default value, and the percentage change

### Requirement: Optimization result comparison
The system SHALL display a detailed comparison of default vs optimized parameters.

#### Scenario: Parameter comparison table
- **WHEN** the user views the optimization result
- **THEN** a table shows each parameter's default value, optimized value, bounds, and percentage change

#### Scenario: Highlight significant changes
- **WHEN** a parameter changed more than 20% from its default
- **THEN** the change is highlighted with a warning indicator (matching the CLI's `<!--` flag behavior)

#### Scenario: Score report display
- **WHEN** the user views the optimization result
- **THEN** a score report shows each scenario's predicted mow time, target range, error, loss, and status (CLOSE/MODERATE/POOR)

#### Scenario: Export optimized parameters
- **WHEN** the user clicks "Export Parameters"
- **THEN** the optimized parameter set is downloaded as a YAML file compatible with the CLI's `-P` flag

### Requirement: Optimization job management
The system SHALL manage long-running optimization jobs safely.

#### Scenario: Stop running optimization
- **WHEN** an optimization job is running and the user clicks "Stop"
- **THEN** the optimization is interrupted and the best result found so far is returned

#### Scenario: Resume stopped optimization
- **WHEN** a stopped optimization is resumed
- **THEN** the optimization continues from where it left off using the same random seed

#### Scenario: Multiple optimization jobs are queued
- **WHEN** a new optimization is started while one is already running
- **THEN** the new job is queued and starts after the current job completes or is stopped

