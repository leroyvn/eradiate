from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from ._factory import Registry
from .object import Object
from .spectrum import BaseSpectrum

material_registry: Registry["BaseMaterial"] = Registry("material")


class BaseMaterial(Object):
    """
    Abstract base class for material configuration objects.
    """

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not BaseMaterial:
            return handler(value)
        return material_registry.dispatch(value, handler, BaseMaterial)


class DiffuseMaterial(BaseMaterial):
    """
    Lambertian (perfectly diffuse) material.

    Parameters
    ----------
    reflectance : BaseSpectrum
        Reflectance spectrum.
    """

    type: Literal["diffuse"] = "diffuse"
    reflectance: BaseSpectrum


# ---------------------------------------------------------------------------
# Registry population
# ---------------------------------------------------------------------------

material_registry.register("diffuse", DiffuseMaterial)
