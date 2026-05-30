## ADDED Requirements

### Requirement: Users can view and edit all 16 model parameters
The system SHALL display all 16 model parameters with their current values and valid ranges.

#### Scenario: Parameter list shows all parameters
- **WHEN** the user opens the Parameter Explorer
- **THEN** all 16 parameters are displayed with their name, current value, default value, minimum bound, and maximum bound

#### Scenario: Parameter slider controls
- **WHEN** the user interacts with a parameter control
- **THEN** they can adjust the value using a slider constrained to the parameter's valid bounds, with a numeric input for precise values

#### Scenario: Parameter descriptions and tooltips
- **WHEN** the user hovers over a parameter name
- **THEN** a tooltip displays the parameter's description and physical meaning

### Requirement: Real-time wetness curve updates on parameter change
The system SHALL re-run the simulation and update the wetness curve chart as the user adjusts parameters.

#### Scenario: Single parameter change triggers re-simulation
- **WHEN** the user moves a parameter slider
- **THEN** the simulation re-runs and the wetness curve chart updates within 1 second

#### Scenario: Debounced updates for rapid slider movement
- **WHEN** the user drags a slider continuously
- **THEN** re-simulation is debounced to occur at most once per 200ms to maintain responsiveness

### Requirement: Parameter preset management
The system SHALL allow users to create, save, and load parameter presets.

#### Scenario: Save current parameters as preset
- **WHEN** the user clicks "Save Preset"
- **THEN** the current parameter values are saved to localStorage with a user-defined name

#### Scenario: Load a saved preset
- **WHEN** the user selects a saved preset from the preset list
- **THEN** all parameter sliders update to the preset's values and the simulation re-runs

#### Scenario: Delete a saved preset
- **WHEN** the user clicks "Delete" on a saved preset
- **THEN** the preset is removed from localStorage

#### Scenario: Default preset is always available
- **WHEN** the user opens the Parameter Explorer
- **THEN** a "Default" preset showing the values from `params_default.yaml` is available

### Requirement: Parameter comparison view
The system SHALL overlay wetness curves from different parameter sets on the same chart.

#### Scenario: Compare default vs current parameters
- **WHEN** the user enables comparison mode
- **THEN** the chart displays the default parameter wetness curve alongside the current parameter curve

#### Scenario: Compare multiple presets
- **WHEN** the user selects multiple saved presets for comparison
- **THEN** each preset's wetness curve is displayed with a distinct color and legend entry

#### Scenario: Comparison shows parameter differences
- **WHEN** the comparison view is active
- **THEN** parameters that differ from the default are highlighted with their delta values (e.g., "+12%")

### Requirement: Parameter bounds editing
The system SHALL allow users to modify parameter bounds for custom exploration.

#### Scenario: Adjust parameter bounds
- **WHEN** the user enables "Advanced" mode
- **THEN** they can adjust the minimum and maximum bounds for each parameter independently

#### Scenario: Bounds affect slider range
- **WHEN** the user changes a parameter's bounds
- **THEN** the slider's range updates to reflect the new bounds

#### Scenario: Reset bounds to defaults
- **WHEN** the user clicks "Reset Bounds"
- **THEN** all parameter bounds return to their original values from `param_bounds`
