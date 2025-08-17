from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Any

import attrs
import mitsuba as mi

from . import spectra
from .scene_object import SceneObject
from .. import KernelContext


class Material(SceneObject, metaclass=ABCMeta):
    @abstractmethod
    def _updating_children(self) -> list[SceneObject]:
        """
        Return a list of child scene objects that must be updated upon a call to
        :meth:`.update`.
        """
        pass

    def update(
        self, ctx: KernelContext, return_dict: bool = False, children: bool = True
    ) -> dict | None:
        """
        Update kernel scene parameters based on the passed context.

        Parameters
        ----------
        ctx : KernelContext
            Context data used to evaluate the update protocols.

        return_dict : bool, default: False
            Debugging tool: If ``True``, do not perform the update, but instead
            return the dictionary containing the updated scene parameters.

        children : bool, default: True
            If ``True``, update child scene objects as well.

        Returns
        -------
        dict or None
        """
        if children and not return_dict:
            for child in self._updating_children():
                # TODO: Add logging debug message
                child.update(ctx)
        return super().update(ctx, return_dict)


@attrs.define(init=False)
class DiffuseMaterial(Material):
    reflectance: spectra.Spectrum = attrs.field(kw_only=True)

    def __init__(self, reflectance: Any):
        reflectance = spectra.convert(reflectance)
        object = mi.load_dict({"type": "diffuse", "reflectance": reflectance()})
        self.__attrs_init__(object, reflectance=reflectance)

    def _updating_children(self) -> list[SceneObject]:
        return [self.reflectance]
