"""
Core configuration layer.

This package defines the fundamental configuration entries available to the user
when setting up an Experiment. It is independent from the backend that will
perform the radiometric computations.

Registries
----------
Each core type family exposes a module-level registry that backends use to
register their concrete implementations:

.. code-block:: python

    from eradiate.two.core import measurement_registry

    @measurement_registry.register("my_sensor")
    class MySensor(BaseMeasurement):
        type: Literal["my_sensor"] = "my_sensor"
        ...
"""

from .atmosphere import atmosphere_component_registry, atmosphere_registry
from .bsdf import bsdf_registry
from .illumination import illumination_registry
from .measurement import measurement_registry
from .spectrum import spectrum_registry
from .surface import surface_registry

__all__ = [
    "atmosphere_registry",
    "atmosphere_component_registry",
    "bsdf_registry",
    "illumination_registry",
    "measurement_registry",
    "spectrum_registry",
    "surface_registry",
]
