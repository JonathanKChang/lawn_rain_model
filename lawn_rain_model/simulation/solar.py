# lawn_rain_model/simulation/solar.py
"""Solar elevation angle model. Ported unchanged from simulator.py."""
import math


def sun_elevation(hour_of_day: float, day_of_year: int = 172, lat: float = 39.0) -> float:
    """Return sun elevation in degrees. Negative = below horizon."""
    declination = 23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81)))
    hour_angle  = 15.0 * (hour_of_day - 12.0)
    lat_r = math.radians(lat)
    dec_r = math.radians(declination)
    ha_r  = math.radians(hour_angle)
    sin_elev = (
        math.sin(lat_r) * math.sin(dec_r)
        + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r)
    )
    return math.degrees(math.asin(max(min(sin_elev, 1.0), -1.0)))
