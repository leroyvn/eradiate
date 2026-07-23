from __future__ import annotations

import pint
from pydantic import ConfigDict, model_validator

from ._factory import Registry
from .material import BaseMaterial
from .object import Object

surface_registry: Registry["BaseSurface"] = Registry("surface")


class BaseSurface(Object):
    """
    Abstract base class for a uniform flat surface.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    material: BaseMaterial
    elevation: pint.Quantity

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not BaseSurface:
            return handler(value)
        return surface_registry.dispatch(value, handler, BaseSurface)
