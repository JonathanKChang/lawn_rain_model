"""Simulation engine: weather processing, solar model, scenario runner."""

# NOTE: We intentionally do NOT re-export run_scenario / build_weather_steps
# from simulation.runner here. The models.protocol → simulation.weather import
# chain would create a circular dependency (runner imports LawnModel protocol).
# Import directly from submodules instead:
#   from lawn_rain_model.simulation.runner import run_scenario
#   from lawn_rain_model.simulation.solar import sun_elevation
#   from lawn_rain_model.simulation.weather import WeatherStep
