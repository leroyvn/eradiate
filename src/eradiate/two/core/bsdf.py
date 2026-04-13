from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from ._factory import Registry
from .object import Object
from .spectrum import BaseSpectrum

bsdf_registry: Registry["BaseBSDF"] = Registry("bsdf")


class BaseBSDF(Object):
    """
    Abstract base class for BSDF configuration objects.
    """

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not BaseBSDF:
            return handler(value)
        return bsdf_registry.dispatch(value, handler, BaseBSDF)


class DiffuseBSDF(BaseBSDF):
    """
    Lambertian (perfectly diffuse) BSDF.

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

bsdf_registry.register("diffuse", DiffuseBSDF)
