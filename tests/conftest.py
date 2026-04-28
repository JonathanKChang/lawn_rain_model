# tests/conftest.py
import pytest
from lawn_rain_model.models.single_layer import SingleLayerModel
from lawn_rain_model.simulation.weather import WeatherStep


@pytest.fixture
def model() -> SingleLayerModel:
    return SingleLayerModel()


@pytest.fixture
def default_params(model: SingleLayerModel) -> dict[str, float]:
    return model.default_params


@pytest.fixture
def dry_step() -> WeatherStep:
    return WeatherStep(
        hour=0, tod=12, temp=75.0, rh=60.0,
        wind=5.0, clouds=30.0, elevation=45.0, rain_inches=0.0,
    )


@pytest.fixture
def rainy_step() -> WeatherStep:
    return WeatherStep(
        hour=0, tod=12, temp=70.0, rh=80.0,
        wind=3.0, clouds=70.0, elevation=30.0, rain_inches=1.0,
    )
