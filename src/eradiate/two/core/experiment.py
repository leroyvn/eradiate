from __future__ import annotations

from .atmosphere import Atmosphere
from .illumination import Illumination
from .measurement import MeasurementRegistry
from .object import Object
from .surface import Surface


class Experiment(Object):
    pass


class AtmosphereExperiment(Experiment):
    """
    Base configuration for an Experiment that contains an atmosphere.
    """

    atmosphere: Atmosphere | None
    illumination: Illumination | None
    surface: Surface | None
    measurements: MeasurementRegistry
