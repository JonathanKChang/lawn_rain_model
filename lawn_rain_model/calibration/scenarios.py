# lawn_rain_model/calibration/scenarios.py
"""Scenario and CalibrationTarget dataclasses, and YAML loader."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


def _deduplicate_rain_events(
    rain_events: list[RainEvent],
    scenario_name: str,
) -> list[RainEvent]:
    """Merge rain events sharing the same hour; raise on truly duplicate entries.

    When multiple RainEvents target the same hour, their inches are summed
    (this is the physically correct behavior — rain accumulates within an hour).

    If two events have identical hour *and* identical inches, this is almost
    certainly a YAML copy/paste mistake and we raise to catch it early.
    """
    hour_totals: dict[int, float] = {}
    dup_keys: list[tuple[int, float]] = []
    seen: set[tuple[int, float]] = set()

    for ev in rain_events:
        key = (ev.hour, ev.inches)
        if key in seen:
            dup_keys.append(key)
        seen.add(key)
        hour_totals[ev.hour] = hour_totals.get(ev.hour, 0.0) + ev.inches

    if dup_keys:
        dup_str = ", ".join(f"h={h} {i:.2f}\"" for h, i in dup_keys)
        raise ValueError(
            f"Scenario '{scenario_name}' contains duplicate rain events "
            f"(same hour+inches): {dup_str}. Each event must be unique."
        )

    return [RainEvent(hour=h, inches=v) for h, v in sorted(hour_totals.items())]


@dataclass
class WeatherConditions:
    temp:      float = 75.0
    rh:        float = 60.0
    wind:      float = 5.0
    clouds:    float = 30.0
    elevation: float = 45.0   # used only when use_solar_model=False


@dataclass
class RainEvent:
    hour:   int
    inches: float


@dataclass
class CalibrationTarget:
    target_hours_min: float
    target_hours_max: float   # == target_hours_min for point targets
    weight:           float = 1.0
    note:             str   = ""


VALID_TIME_STEPS = {5, 10, 15, 20, 30, 60}


@dataclass
class Scenario:
    name:            str
    duration_hours:  int
    rain_events:     list[RainEvent]
    weather:         Optional[WeatherConditions]   # None when history_file is set
    initial_wetness: float                = 0.0
    use_solar_model: bool                 = True
    start_hour:      int                  = 6
    day_of_year:     int                  = 172
    latitude:        float                = 39.0
    time_step_minutes: int                = 15
    calibration:     Optional[CalibrationTarget] = None
    history_file:    Optional[str]        = None   # path relative to scenarios YAML
    sensor_map:      dict[str, str]       = field(default_factory=dict)

    @property
    def steps_per_hour(self) -> int:
        """Number of simulation sub-steps per clock hour."""
        if self.time_step_minutes not in VALID_TIME_STEPS:
            raise ValueError(
                f"time_step_minutes={self.time_step_minutes} must be one of "
                f"{sorted(VALID_TIME_STEPS)}"
            )
        return 60 // self.time_step_minutes


class ScenarioLoader:
    @staticmethod
    def load(path: Path | str, include_calibration: bool = True) -> list[Scenario]:
        path = Path(path)
        raw  = yaml.safe_load(path.read_text())
        scenarios: list[Scenario] = []

        for s in raw.get("scenarios", []):
            w_raw = s.get("weather") or {}
            weather: Optional[WeatherConditions] = None
            if w_raw:
                weather = WeatherConditions(
                    temp=w_raw.get("temp", 75.0),
                    rh=w_raw.get("rh", 60.0),
                    wind=w_raw.get("wind", 5.0),
                    clouds=w_raw.get("clouds", 30.0),
                    elevation=w_raw.get("elevation", 45.0),
                )

            raw_rain_events = [
                RainEvent(e["hour"], e["inches"])
                for e in s.get("rain_events", [])
            ]
            rain_events = _deduplicate_rain_events(
                raw_rain_events, s.get("name", "unnamed"),
            )

            cal: Optional[CalibrationTarget] = None
            if "calibration" in s and include_calibration:
                c = s["calibration"]
                if "target_hours" in c:
                    # Point target
                    t = float(c["target_hours"])
                    cal = CalibrationTarget(
                        target_hours_min=t,
                        target_hours_max=t,
                        weight=c.get("weight", 1.0),
                        note=c.get("note", ""),
                    )
                else:
                    cal = CalibrationTarget(
                        target_hours_min=c["target_hours_min"],
                        target_hours_max=c["target_hours_max"],
                        weight=c.get("weight", 1.0),
                        note=c.get("note", ""),
                    )

            scenarios.append(Scenario(
                name=s.get("name", "unnamed"),
                duration_hours=s.get("duration_hours", 96),
                rain_events=rain_events,
                weather=weather,
                initial_wetness=s.get("initial_wetness", 0.0),
                use_solar_model=s.get("use_solar_model", True),
                start_hour=s.get("start_hour", 6),
                day_of_year=s.get("day_of_year", 172),
                latitude=s.get("latitude", 39.0),
                time_step_minutes=s.get("time_step_minutes", 15),
                calibration=cal,
                history_file=s.get("history_file"),
                sensor_map=s.get("history_sensor_map", {}),
            ))

        return scenarios
