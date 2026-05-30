## ADDED Requirements

### Requirement: Users can upload Home Assistant history CSV files
The system SHALL accept CSV file uploads in the Home Assistant history narrow format.

#### Scenario: Upload valid CSV file
- **WHEN** the user drags and drops or selects a CSV file in the History Importer
- **THEN** the file is uploaded to the server and the weather data is parsed

#### Scenario: Reject invalid CSV format
- **WHEN** the user uploads a CSV that does not match the expected format
- **THEN** the system displays an error message listing the required columns and format expectations

#### Scenario: Reject oversized CSV files
- **WHEN** the user uploads a CSV file larger than 5MB
- **THEN** the system rejects the upload and displays a size limit error

#### Scenario: Upload multiple CSV files
- **WHEN** the user uploads multiple CSV files
- **THEN** each file is processed and listed as a separate importable weather dataset

### Requirement: Automatic sensor entity mapping
The system SHALL detect and map Home Assistant sensor entity IDs to logical weather variables.

#### Scenario: Auto-detect standard sensor names
- **WHEN** the uploaded CSV contains standard Pirate Weather sensor entity IDs
- **THEN** the system automatically maps them: `sensor.pirateweather_temperature_0h` → temp, `sensor.pirateweather_humidity_0h` → rh, etc.

#### Scenario: Custom sensor entity mapping
- **WHEN** the uploaded CSV uses non-standard sensor entity IDs
- **THEN** the user is presented with a mapping interface to assign each entity to a logical variable (temp, rh, wind, clouds, elevation, liquid_accumulation)

#### Scenario: Missing required sensors
- **WHEN** the uploaded CSV is missing one or more required sensors
- **THEN** the system warns the user and allows them to proceed with available data only

### Requirement: Weather data preview
The system SHALL display a preview of the parsed weather data before running simulation.

#### Scenario: Weather data table preview
- **WHEN** the user uploads a valid CSV
- **THEN** a table shows the first 20 rows of parsed weather data with hour, time-of-day, temperature, humidity, wind, clouds, and rain

#### Scenario: Weather data chart preview
- **WHEN** the user uploads a valid CSV
- **THEN** a multi-axis chart displays temperature, humidity, and wind over the time period

#### Scenario: Rain event summary
- **WHEN** the user uploads a CSV with rain data
- **THEN** a summary shows total rainfall, number of rain events, and peak rainfall rate

### Requirement: History-backed simulation
The system SHALL run a simulation using the uploaded CSV's weather data.

#### Scenario: Run simulation with history weather
- **WHEN** the user clicks "Simulate" after uploading a CSV
- **THEN** the system runs `run_scenario()` using the weather steps from the CSV and displays the wetness curve

#### Scenario: Add rain events on top of history weather
- **WHEN** the user adds rain events to a history-backed scenario
- **THEN** the simulation applies the additional rain events at the specified hours on top of the CSV weather data

#### Scenario: Set calibration target for history scenario
- **WHEN** the user sets a calibration target on a history scenario
- **THEN** the system displays the predicted mow time and whether it falls within the target range

### Requirement: Save history-imported scenarios
The system SHALL allow users to save history-backed scenarios for future use.

#### Scenario: Save history scenario
- **WHEN** the user clicks "Save Scenario" after a history simulation
- **THEN** the scenario is saved to a YAML file with the `history_file` reference and calibration target

#### Scenario: History file stored with scenario
- **WHEN** the user saves a history-backed scenario
- **THEN** the CSV file is copied to the `scenarios/history/` directory and referenced by the YAML

#### Scenario: Re-load saved history scenario
- **WHEN** the user opens a saved history scenario
- **THEN** the system re-runs the simulation with the original CSV data
