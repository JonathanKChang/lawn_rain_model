# lawn_rain_model/simulation/solar.py
"""Solar elevation angle model and sensor normalization."""
import math


def normalize_elevation(raw: float) -> float:
    """Normalize elevation from a sensor to [-90, 90] degrees.

    Handles wrap-around values (e.g. 350° → -10°, 450° → 90°) and
    negative values. The Taylor expansion below is symmetric around 0,
    so the sign naturally encodes above/below horizon.
    """
    # Wrap to [0, 360)
    v = raw % 360.0
    # Map to [-180, 180], then clamp to [-90, 90] for elevation
    if v > 180.0:
        v -= 360.0
    return max(min(v, 90.0), -90.0)


def solar_intensity_taylor(elevation_deg: float) -> float:
    """Compute solar intensity from elevation using Taylor expansion of sin(x).

    sin(x) ≈ x - x³/3! + x⁵/5!   where x = elevation in radians.

    The elevation is first normalized to [-90, 90]° to handle sensor
    wrap-around. Below-horizon values (negative after normalization)
    are clamped to 0.
    """
    e = normalize_elevation(elevation_deg)
    if e <= 0.0:
        return 0.0
    x = math.radians(e)  # radians, x ∈ (0, π/2]
    # 3-term Taylor: sin(x) ≈ x - x³/6 + x⁵/120
    x2 = x * x
    return x - x2 * x / 6.0 + x2 * x2 * x / 120.0


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
