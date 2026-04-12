from __future__ import annotations

import pint

from .atmosphere import Atmosphere
from .illumination import BaseIllumination
from .measurement import MeasurementRegistry
from .object import Object
from .surface import BaseSurface


class Experiment(Object):
    pass


class AtmosphereExperiment(Experiment):
    """
    Base configuration for an Experiment that contains an atmosphere.
    """

    geometry: BaseGeometry
    atmosphere: Atmosphere | None
    illumination: BaseIllumination | None
    surface: BaseSurface | None
    measurements: MeasurementRegistry


class BaseGeometry(Object):
    pass


class PlaneParallelGeometry(BaseGeometry):
    pass


class SphericalShellGeometry(BaseGeometry):
    planet_radius: pint.Quantity
