from __future__ import annotations

from pydantic import model_validator

from ._factory import Registry
from .object import Object

measurement_registry: Registry["BaseMeasurement"] = Registry("measurement")


class BaseMeasurement(Object):
    """
    Abstract base class for measurement configuration objects.

    Backends register their concrete measurement types at import time::

        from eradiate.two.core import measurement_registry

        @measurement_registry.register("my_sensor")
        class MySensor(BaseMeasurement):
            type: Literal["my_sensor"] = "my_sensor"
            ...
    """

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not BaseMeasurement:
            return handler(value)
        return measurement_registry.dispatch(value, handler, BaseMeasurement)
