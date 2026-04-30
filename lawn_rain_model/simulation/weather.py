# lawn_rain_model/simulation/weather.py
"""WeatherStep and history resampling."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

# Mapping from logical field name → HA entity_id.
# Override per-scenario in YAML under history_sensor_map:.
DEFAULT_SENSOR_MAP: dict[str, str] = {
    "temp":               "sensor.pirateweather_temperature_0h",
    "rh":                 "sensor.pirateweather_humidity_0h",
    "wind":               "sensor.pirateweather_wind_speed",
    "clouds":             "sensor.pirateweather_cloud_coverage",
    "elevation":          "sensor.sun_elevation",
    "liquid_accumulation": "sensor.pirateweather_current_day_liquid_accumulation",
}


@dataclass(frozen=True)
class WeatherStep:
    """One sub-step of weather conditions fed to the model.

    For hourly resolution, sub_step=0 and hour=step_index.
    For sub-hourly resolution, each clock hour produces multiple
    steps with sub_step=0..steps_per_hour-1.
    """
    hour: int           # clock hour index (0, 1, 2, ...)
    sub_step: int       # position within the hour (0..steps_per_hour-1)
    steps_per_hour: int = 1  # number of sub-steps per clock hour
    tod: int            # time of day 0–23
    temp: float         # °F
    rh: float           # relative humidity 0–100
    wind: float         # mph
    clouds: float       # 0–100
    elevation: float    # solar elevation angle, degrees
    rain_inches: float  # rain that fell during this sub-step


def resample_history(
    csv_path: Path | str,
    sensor_map: dict[str, str],
) -> list[WeatherStep]:
    """
    Convert a narrow-format HA history CSV into hourly WeatherStep objects.

    Resampling rules:
    - Slow sensors (temp, rh, wind, clouds, elevation): last observation
      carried forward (LOCF) to hourly boundaries.
    - Rain: positive delta of liquid_accumulation between hour boundaries.
      Negative deltas indicate a midnight reset; in that case rain equals
      the post-reset accumulation value for that period.

    Returns one WeatherStep per complete or partial clock hour present in
    the data, indexed 0, 1, 2, ... with tod set to the actual hour of day.
    """
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, parse_dates=["last_changed"])
    df["last_changed"] = pd.to_datetime(df["last_changed"], utc=True)
    df["state"] = pd.to_numeric(df["state"], errors="coerce")
    df = df.dropna(subset=["state"])
    df = df.set_index("last_changed").sort_index()

    def _hourly_last(entity_id: str) -> pd.Series:
        sub = df[df["entity_id"] == entity_id]["state"]
        if sub.empty:
            return pd.Series(dtype=float)
        return sub.resample("h").last().ffill()

    temp_h  = _hourly_last(sensor_map["temp"])
    rh_h    = _hourly_last(sensor_map["rh"])
    wind_h  = _hourly_last(sensor_map["wind"])
    clouds_h = _hourly_last(sensor_map["clouds"])
    elev_h  = _hourly_last(sensor_map["elevation"])
    accum_h = _hourly_last(sensor_map["liquid_accumulation"])

    # Rain = diff of accumulation; handle midnight reset (negative delta)
    rain_h = accum_h.diff()
    midnight_reset = rain_h < 0
    rain_h[midnight_reset] = accum_h[midnight_reset]
    # First bucket: no previous bucket to diff from; use accumulation value
    # (assumes accumulation started at 0 before the first hour)
    rain_h = rain_h.fillna(accum_h)
    rain_h = rain_h.fillna(0.0)

    # Align all series to a common hourly index
    combined = pd.DataFrame({
        "temp":   temp_h,
        "rh":     rh_h,
        "wind":   wind_h,
        "clouds": clouds_h,
        "elev":   elev_h,
        "rain":   rain_h,
    }).dropna(subset=["temp"])  # require at least temp data each hour

    # Fill any remaining NaN in rain (e.g. past last accumulation sensor reading)
    combined["rain"] = combined["rain"].fillna(0.0)

    steps: list[WeatherStep] = []
    for idx, ts in enumerate(combined.index):
        row = combined.iloc[idx]
        # ts is a pandas Timestamp; .hour gives the clock hour
        steps.append(WeatherStep(
            hour=idx,
            tod=ts.hour,
            temp=float(row["temp"]),
            rh=float(row["rh"]),
            wind=float(row["wind"]),
            clouds=float(row["clouds"]),
            elevation=float(row["elev"]),
            rain_inches=float(row["rain"]),
        ))

    return steps
