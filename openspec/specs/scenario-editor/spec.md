# scenario-editor Specification

## Purpose
TBD - created by archiving change beautiful-interactive-frontend. Update Purpose after archive.
## Requirements
### Requirement: Users can view existing scenarios
The system SHALL display all loaded scenarios in a browsable list with key metadata.

#### Scenario: Scenario list shows all scenarios
- **WHEN** the user opens the Scenario Builder page
- **THEN** all scenarios from discovered YAML files are displayed in a scrollable list showing name, weather conditions, rain events, and calibration target

#### Scenario: User filters scenarios by name
- **WHEN** the user types in the search filter
- **THEN** only scenarios matching the search term are displayed

#### Scenario: User selects a scenario to edit
- **WHEN** the user clicks on a scenario in the list
- **THEN** the scenario details are loaded into the editor form

### Requirement: Users can construct weather scenarios interactively
The system SHALL provide a form for building weather scenarios with all configurable fields.

#### Scenario: Weather parameter inputs
- **WHEN** the user opens the scenario editor
- **THEN** they see input controls for temperature (°F), relative humidity (%), wind speed (mph), cloud coverage (%), and rain events with hour/inches pairs

#### Scenario: Rain event management
- **WHEN** the user is editing a scenario's rain events
- **THEN** they can add, remove, and reorder rain events, each with an hour offset and rainfall depth

#### Scenario: Solar model configuration
- **WHEN** the user is editing a scenario
- **THEN** they can toggle the solar model on/off and set start hour, day of year, and latitude

#### Scenario: Initial wetness setting
- **WHEN** the user is editing a scenario
- **THEN** they can set a custom initial wetness value (0–100)

### Requirement: Live simulation preview updates
The system SHALL run a simulation preview as the user modifies scenario parameters.

#### Scenario: Preview updates on parameter change
- **WHEN** the user changes any weather parameter in the editor
- **THEN** the wetness curve chart updates within 500ms to reflect the new scenario

#### Scenario: Preview shows mow-readiness indicator
- **WHEN** a simulation preview is rendered
- **THEN** a visual mow-readiness indicator shows the predicted mow time (or "never" if it doesn't dry)

#### Scenario: Preview handles no-rain scenarios
- **WHEN** the user creates a scenario with no rain events
- **THEN** the preview shows a flat wetness curve at the initial wetness level

### Requirement: Users can save and export scenarios
The system SHALL allow users to save scenarios to YAML files and export them.

#### Scenario: Save scenario to YAML
- **WHEN** the user clicks "Save" in the scenario editor
- **THEN** the scenario is written to the appropriate YAML file in the `scenarios/` directory

#### Scenario: Export scenario as standalone YAML
- **WHEN** the user clicks "Export" on a scenario
- **THEN** a YAML file containing only that scenario is downloaded to the user's browser

#### Scenario: Create scenario from template
- **WHEN** the user clicks "New Scenario" and selects a template (e.g., "Hot Sunny", "Cold Rainy")
- **THEN** the editor pre-fills the form with the template's weather conditions

### Requirement: Scenario comparison view
The system SHALL allow side-by-side comparison of multiple scenarios.

#### Scenario: Select scenarios to compare
- **WHEN** the user selects multiple scenarios from the list
- **THEN** a comparison view displays all selected scenarios' wetness curves overlaid on a single chart

#### Scenario: Comparison shows mow times
- **WHEN** the comparison view is active
- **THEN** each scenario's mow time is displayed as a labeled marker on the chart

