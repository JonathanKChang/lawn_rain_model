# lawn_rain_model/models/protocol.py
"""
LawnModel structural Protocol (PEP 544).

Any class with these five attributes/methods satisfies LawnModel — no inheritance required.
State is model-defined: SingleLayerModel uses float; a future multi-layer model uses
list[float] or np.ndarray. The Protocol does not constrain state shape.
"""
from __future__ import annotations
from typing import Any, Protocol
from lawn_rain_model.simulation.weather import WeatherStep


class LawnModel(Protocol):
    @property
    def default_params(self) -> dict[str, float]:
        """Parameter dict used when none is supplied by the caller."""
        ...

    @property
    def param_bounds(self) -> dict[str, tuple[float, float]]:
        """Optimizer search bounds keyed by the same names as default_params."""
        ...

    def initial_state(self, initial_wetness: float) -> Any:
        """Construct the model's state from a scalar wetness value (0–100)."""
        ...

    def surface_wetness(self, state: Any) -> float:
        """Extract the mow-relevant surface wetness scalar from state (0–100)."""
        ...

    def step(
        self,
        state: Any,
        weather: WeatherStep,
        params: dict[str, float],
    ) -> dict[str, float]:
        """
        Advance state by one hour.

        Must include in the returned dict:
          wetness_out  float   surface wetness after this step (0–100)
          drying_rate  float   total drying applied this step
          diagnostics  dict[str, float]   model-specific breakdown for display/CSV
        """
        ...
